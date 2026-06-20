"""
SE8 Image Engine — Checkpoint Loading

Handles checkpoint detection, CLIP text encoding, and VAE encode/decode.
Bridges ldm_patched internals with SE8's clean architecture.
Lazy imports from ldm_patched are used to avoid import-time side effects.
"""

from __future__ import annotations
from common.log_utils import get_logger

from dataclasses import dataclass
from typing import Any

logger = get_logger(__name__)

# Lazy imports — resolved on first use
_ldm_modules = None
_ldm_utils = None


def _get_ldm() -> dict[str, Any]:
    """Lazy-load ldm_patched modules."""
    global _ldm_modules, _ldm_utils
    if _ldm_modules is None:
        from ldm_patched.modules import utils as _utils
        from ldm_patched.modules import model_management as _mm
        from ldm_patched.modules import model_detection as _md
        from ldm_patched.modules import sd1_clip as _sd1_clip
        from ldm_patched.modules import sd2_clip as _sd2_clip
        from ldm_patched.modules import sdxl_clip as _sdxl_clip
        from ldm_patched.modules import clip_vision as _cv
        from ldm_patched.modules import model_patcher as _mp
        from ldm_patched.modules import lora as _lora
        from ldm_patched.modules import model_base as _mb
        from ldm_patched.modules import ops as _ops
        from ldm_patched.modules import supported_models_base as _smb
        from ldm_patched.modules import gligen as _gligen
        from ldm_patched.modules import diffusers_convert as _dc
        from ldm_patched.modules import conds as _conds
        from ldm_patched.taesd import taesd as _taesd
        from ldm_patched.ldm.models.autoencoder import AutoencoderKL, AutoencodingEngine

        _ldm_modules = {
            "utils": _utils,
            "model_management": _mm,
            "model_detection": _md,
            "sd1_clip": _sd1_clip,
            "sd2_clip": _sd2_clip,
            "sdxl_clip": _sdxl_clip,
            "clip_vision": _cv,
            "model_patcher": _mp,
            "lora": _lora,
            "model_base": _mb,
            "ops": _ops,
            "supported_models_base": _smb,
            "gligen": _gligen,
            "diffusers_convert": _dc,
            "conds": _conds,
            "taesd": _taesd,
            "AutoencoderKL": AutoencoderKL,
            "AutoencodingEngine": AutoencodingEngine,
        }
    return _ldm_modules


def _get_utils() -> Any:
    global _ldm_utils
    if _ldm_utils is None:
        _ldm_utils = _get_ldm()["utils"]
    return _ldm_utils


# ---------------------------------------------------------------------------
# CLIP wrapper
# ---------------------------------------------------------------------------

class CLIP:
    """Text encoding wrapper around ldm_patched CLIP implementation.
    Handles tokenization and encoding of text prompts.
    """

    def __init__(self, target=None, embedding_directory=None, no_init=False) -> None:
        if no_init:
            return

        from app.services.model_manager import get_model_manager

        ldm = _get_ldm()
        mm = ldm["model_management"]

        params = target.params.copy()
        clip_cls = target.clip
        tokenizer_cls = target.tokenizer

        manager = get_model_manager()
        load_device = manager.text_encoder_device()
        offload_device = manager.text_encoder_offload_device()

        params['device'] = offload_device
        params['dtype'] = manager.text_encoder_dtype(load_device)

        self.cond_stage_model = clip_cls(**(params))
        self.tokenizer = tokenizer_cls(embedding_directory=embedding_directory)
        self.patcher = ldm["model_patcher"].ModelPatcher(
            self.cond_stage_model, load_device=load_device, offload_device=offload_device
        )
        self.layer_idx = None

    def clone(self) -> CLIP:
        n = CLIP(no_init=True)
        n.patcher = self.patcher.clone()
        n.cond_stage_model = self.cond_stage_model
        n.tokenizer = self.tokenizer
        n.layer_idx = self.layer_idx
        return n

    def add_patches(self, patches, strength_patch=1.0, strength_model=1.0) -> Any:
        return self.patcher.add_patches(patches, strength_patch, strength_model)

    def clip_layer(self, layer_idx) -> None:
        self.layer_idx = layer_idx

    def tokenize(self, text, return_word_ids=False) -> Any:
        return self.tokenizer.tokenize_with_weights(text, return_word_ids)

    def encode_from_tokens(self, tokens, return_pooled=False) -> Any:
        if self.layer_idx is not None:
            self.cond_stage_model.clip_layer(self.layer_idx)
        else:
            self.cond_stage_model.reset_clip_layer()
        self.load_model()
        cond, pooled = self.cond_stage_model.encode_token_weights(tokens)
        return (cond, pooled) if return_pooled else cond

    def encode(self, text) -> Any:
        tokens = self.tokenize(text)
        return self.encode_from_tokens(tokens)

    def load_sd(self, sd) -> Any:
        return self.cond_stage_model.load_sd(sd)

    def get_sd(self) -> Any:
        return self.cond_stage_model.state_dict()

    def load_model(self) -> Any:
        from app.services.model_manager import get_model_manager
        get_model_manager().load_models_gpu([self.patcher])
        return self.patcher

    def get_key_patches(self) -> Any:
        return self.patcher.get_key_patches()


# ---------------------------------------------------------------------------
# VAE wrapper
# ---------------------------------------------------------------------------

class VAE:
    """VAE encode/decode wrapper around ldm_patched AutoencoderKL.
    Handles tiled and batched encode/decode with OOM fallback.
    """

    def __init__(self, sd=None, device=None, config=None, dtype=None) -> None:
        from app.services.model_manager import get_model_manager
        ldm = _get_ldm()
        mm = ldm["model_management"]
        manager = get_model_manager()

        # Detect diffusers format
        if 'decoder.up_blocks.0.resnets.0.norm1.weight' in sd.keys():
            sd = ldm["diffusers_convert"].convert_vae_state_dict(sd)

        self.memory_used_encode = lambda shape, dtype_: (1767 * shape[2] * shape[3]) * _dtype_size(dtype_)
        self.memory_used_decode = lambda shape, dtype_: (2178 * shape[2] * shape[3] * 64) * _dtype_size(dtype_)
        self.downscale_ratio = 8
        self.latent_channels = 4

        if config is None:
            if "decoder.mid.block_1.mix_factor" in sd:
                encoder_config = {
                    'double_z': True, 'z_channels': 4, 'resolution': 256,
                    'in_channels': 3, 'out_ch': 3, 'ch': 128,
                    'ch_mult': [1, 2, 4, 4], 'num_res_blocks': 2,
                    'attn_resolutions': [], 'dropout': 0.0,
                }
                decoder_config = encoder_config.copy()
                decoder_config["video_kernel_size"] = [3, 1, 1]
                decoder_config["alpha"] = 0.0
                self.first_stage_model = ldm["AutoencodingEngine"](
                    regularizer_config={
                        'target': "ldm_patched.ldm.models.autoencoder.DiagonalGaussianRegularizer"
                    },
                    encoder_config={
                        'target': "ldm_patched.ldm.modules.diffusionmodules.model.Encoder",
                        'params': encoder_config,
                    },
                    decoder_config={
                        'target': "ldm_patched.ldm.modules.temporal_ae.VideoDecoder",
                        'params': decoder_config,
                    },
                )
            elif "taesd_decoder.1.weight" in sd:
                self.first_stage_model = ldm["taesd"].taesd.TAESD()
            else:
                ddconfig = {
                    'double_z': True, 'z_channels': 4, 'resolution': 256,
                    'in_channels': 3, 'out_ch': 3, 'ch': 128,
                    'ch_mult': [1, 2, 4, 4], 'num_res_blocks': 2,
                    'attn_resolutions': [], 'dropout': 0.0,
                }
                if 'encoder.down.2.downsample.conv.weight' not in sd:
                    ddconfig['ch_mult'] = [1, 2, 4]
                    self.downscale_ratio = 4
                self.first_stage_model = ldm["AutoencoderKL"](ddconfig=ddconfig, embed_dim=4)
        else:
            self.first_stage_model = ldm["AutoencoderKL"](**(config['params']))

        self.first_stage_model = self.first_stage_model.eval()
        m, u = self.first_stage_model.load_state_dict(sd, strict=False)
        if m:
            logger.warning("Missing VAE keys: %s", m)
        if u:
            logger.warning("Leftover VAE keys: %s", u)

        if device is None:
            device = manager.vae_device()
        self.device = device
        offload_device = manager.unet_offload_device()
        if dtype is None:
            dtype = manager.vae_dtype()
        self.vae_dtype = dtype
        self.first_stage_model.to(self.vae_dtype)
        self.output_device = manager.intermediate_device()

        self.patcher = ldm["model_patcher"].ModelPatcher(
            self.first_stage_model, load_device=self.device, offload_device=offload_device
        )

    def decode(self, samples_in) -> Any:
        """Decode latent samples to pixel images. Falls back to tiled on OOM."""
        import torch
        from app.services.model_manager import get_model_manager
        manager = get_model_manager()

        try:
            memory_used = self.memory_used_decode(samples_in.shape, self.vae_dtype)
            manager.load_models_gpu([self.patcher], memory_required=memory_used)
            free_mem = manager.get_free_memory(self.device)
            batch_number = max(1, int(free_mem / memory_used))

            pixel_samples = torch.empty(
                (samples_in.shape[0], 3,
                 round(samples_in.shape[2] * self.downscale_ratio),
                 round(samples_in.shape[3] * self.downscale_ratio)),
                device=self.output_device,
            )
            for x in range(0, samples_in.shape[0], batch_number):
                samples = samples_in[x:x+batch_number].to(self.vae_dtype).to(self.device)
                pixel_samples[x:x+batch_number] = torch.clamp(
                    (self.first_stage_model.decode(samples).to(self.output_device).float() + 1.0) / 2.0,
                    min=0.0, max=1.0,
                )
        except Exception:
            logger.warning("OOM during VAE decode — falling back to tiled decode")
            pixel_samples = self._decode_tiled(samples_in)

        pixel_samples = pixel_samples.to(self.output_device).movedim(1, -1)
        return pixel_samples

    def encode(self, pixel_samples) -> Any:
        """Encode pixel images to latent space."""
        import torch
        from app.services.model_manager import get_model_manager
        manager = get_model_manager()

        try:
            memory_used = self.memory_used_encode(pixel_samples.shape, self.vae_dtype)
            manager.load_models_gpu([self.patcher], memory_required=memory_used)
            free_mem = manager.get_free_memory(self.device)
            batch_number = max(1, int(free_mem / memory_used))

            latent_samples = torch.empty(
                (pixel_samples.shape[0], self.latent_channels,
                 round(pixel_samples.shape[2] / self.downscale_ratio),
                 round(pixel_samples.shape[3] / self.downscale_ratio)),
                device=self.output_device,
            )
            for x in range(0, pixel_samples.shape[0], batch_number):
                samples = pixel_samples[x:x+batch_number].to(self.vae_dtype).to(self.device)
                latent_samples[x:x+batch_number] = self.first_stage_model.encode(
                    (2.0 * samples - 1.0)
                ).to(self.output_device).float()
        except Exception:
            logger.warning("OOM during VAE encode — falling back to tiled encode")
            latent_samples = self._encode_tiled(pixel_samples)

        return latent_samples

    def _decode_tiled(self, samples, tile_x=64, tile_y=64, overlap=16) -> Any:
        """Tiled VAE decode for large images."""
        import torch
        utils = _get_utils()
        decode_fn = lambda a: (
            self.first_stage_model.decode(a.to(self.vae_dtype).to(self.device)) + 1.0
        ).float()
        output = torch.clamp(
            ((utils.tiled_scale(samples, decode_fn, tile_x // 2, tile_y * 2, overlap,
                                upscale_amount=self.downscale_ratio, output_device=self.output_device) +
              utils.tiled_scale(samples, decode_fn, tile_x * 2, tile_y // 2, overlap,
                                upscale_amount=self.downscale_ratio, output_device=self.output_device) +
              utils.tiled_scale(samples, decode_fn, tile_x, tile_y, overlap,
                                upscale_amount=self.downscale_ratio, output_device=self.output_device))
             / 3.0) / 2.0,
            min=0.0, max=1.0,
        )
        return output

    def _encode_tiled(self, pixel_samples, tile_x=512, tile_y=512, overlap=64) -> Any:
        """Tiled VAE encode for large images."""
        utils = _get_utils()
        encode_fn = lambda a: self.first_stage_model.encode((2.0 * a - 1.0).to(self.vae_dtype).to(self.device)).float()
        samples = (
            utils.tiled_scale(pixel_samples, encode_fn, tile_x, tile_y, overlap,
                              upscale_amount=(1 / self.downscale_ratio), out_channels=self.latent_channels,
                              output_device=self.output_device) +
            utils.tiled_scale(pixel_samples, encode_fn, tile_x * 2, tile_y // 2, overlap,
                              upscale_amount=(1 / self.downscale_ratio), out_channels=self.latent_channels,
                              output_device=self.output_device) +
            utils.tiled_scale(pixel_samples, encode_fn, tile_x // 2, tile_y * 2, overlap,
                              upscale_amount=(1 / self.downscale_ratio), out_channels=self.latent_channels,
                              output_device=self.output_device)
        ) / 3.0
        return samples


def _dtype_size(dtype) -> int:
    if dtype in (float, type(float)):
        return 4
    return 4


# ---------------------------------------------------------------------------
# Checkpoint loading
# ---------------------------------------------------------------------------

def load_checkpoint_guess_config(
    ckpt_path: str,
    output_vae: bool = True,
    output_clip: bool = True,
    output_clipvision: bool = False,
    embedding_directory=None,
    output_model: bool = True,
    vae_filename_param=None,
    ) -> tuple[Any, Any, Any, str | None, Any]:
    """
    Load a checkpoint file and auto-detect model type.

    Returns:
        (model_patcher, clip, vae, vae_filename, clipvision)
    """
    import torch
    from app.services.model_manager import get_model_manager

    ldm = _get_ldm()
    utils = ldm["utils"]
    mm = ldm["model_management"]
    md = ldm["model_detection"]

    manager = get_model_manager()

    sd = utils.load_torch_file(ckpt_path)
    clip = None
    clipvision = None
    vae = None
    vae_filename = None
    model = None
    model_patcher = None

    parameters = utils.calculate_parameters(sd, "model.diffusion_model.")
    unet_dtype = manager.unet_dtype(model_params=parameters)
    load_device = manager.device
    manual_cast_dtype = manager.unet_manual_cast(unet_dtype, load_device)

    class WeightsLoader(torch.nn.Module):
        pass

    model_config = md.model_config_from_unet(sd, "model.diffusion_model.", unet_dtype)
    if model_config is None:
        raise RuntimeError(f"ERROR: Could not detect model type of: {ckpt_path}")

    model_config.set_manual_cast(manual_cast_dtype)

    if model_config.clip_vision_prefix is not None and output_clipvision:
        clipvision = ldm["clip_vision"].load_clipvision_from_sd(
            sd, model_config.clip_vision_prefix, True
        )

    if output_model:
        inital_load_device = manager.unet_initial_load_device(parameters, unet_dtype)
        offload_device = manager.unet_offload_device()
        model = model_config.get_model(sd, "model.diffusion_model.", device=inital_load_device)
        model.load_model_weights(sd, "model.diffusion_model.")

    if output_vae:
        if vae_filename_param is None:
            vae_sd = utils.state_dict_prefix_replace(
                sd, {"first_stage_model.": ""}, filter_keys=True
            )
            vae_sd = model_config.process_vae_state_dict(vae_sd)
        else:
            vae_sd = utils.load_torch_file(vae_filename_param)
            vae_filename = vae_filename_param
        vae = VAE(sd=vae_sd)

    if output_clip:
        clip_target = model_config.clip_target()
        if clip_target is not None:
            clip = CLIP(clip_target, embedding_directory=embedding_directory)
            w = WeightsLoader()
            w.cond_stage_model = clip.cond_stage_model
            sd_processed = model_config.process_clip_state_dict(sd)
            _load_model_weights(w, sd_processed)

    left_over = sd.keys()
    if len(left_over) > 0:
        logger.info("Leftover keys: %s", left_over)

    if output_model:
        model_patcher = ldm["model_patcher"].ModelPatcher(
            model, load_device=load_device,
            offload_device=manager.unet_offload_device(),
            current_device=inital_load_device,
        )
        if inital_load_device != torch.device("cpu"):
            logger.info("Loaded straight to GPU")
            manager.load_models_gpu([model_patcher])

    return model_patcher, clip, vae, vae_filename, clipvision


def _load_model_weights(model, sd) -> Any:
    """Load state dict into model, logging missing/unexpected keys."""
    m, u = model.load_state_dict(sd, strict=False)
    if m:
        logger.info("Missing keys: %s", set(m))
    return model


def load_lora_for_models(model, clip, lora_path, strength_model=1.0, strength_clip=1.0) -> tuple[Any, Any]:
    """Load a LoRA file and apply it to model and/or clip."""
    ldm = _get_ldm()

    key_map = {}
    if model is not None:
        key_map = ldm["lora"].model_lora_keys_unet(model.model, key_map)
    if clip is not None:
        key_map = ldm["lora"].model_lora_keys_clip(clip.cond_stage_model, key_map)

    loaded = ldm["lora"].load_lora(lora_path, key_map)

    new_modelpatcher = None
    if model is not None:
        new_modelpatcher = model.clone()
        new_modelpatcher.add_patches(loaded, strength_model)

    new_clip = None
    if clip is not None:
        new_clip = clip.clone()
        new_clip.add_patches(loaded, strength_clip)

    return new_modelpatcher, new_clip
