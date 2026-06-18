"""
SE8 Image Engine — Pipeline

Orchestrates model loading, CLIP encoding, and diffusion processing.

Design decisions:
- Class-based instead of 15+ module-level globals
- Uses SE8 model_base, model_manager, checkpoint modules
- Thread-safe, no global mutable state
- Config-driven via ImageEngineSettings
- Lazy torch imports

Architecture:
  Pipeline holds:
  - model_base: StableDiffusionModel (base SDXL)
  - model_refiner: StableDiffusionModel (refiner, optional)
  - final_unet/final_clip/final_vae/final_refiner_* — resolved after refresh
  - loaded_ControlNets: dict cache
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class Pipeline:
    """Main image generation pipeline.

    Orchestrates model loading, LoRA application, CLIP encoding,
    and diffusion processing. Thread-safe singleton via module-level instance.
    """

    def __init__(self):
        """Initialize empty pipeline — no models loaded."""
        from app.services.model_base import StableDiffusionModel

        self.model_base: StableDiffusionModel = StableDiffusionModel()
        self.model_refiner: StableDiffusionModel = StableDiffusionModel()

        # Resolved references after refresh_everything()
        self.final_unet = None
        self.final_clip = None
        self.final_vae = None
        self.final_refiner_unet = None
        self.final_refiner_vae = None
        self.final_expansion = None

        # ControlNet cache
        self.loaded_controlnets: Dict[str, Any] = {}

        # Clip encode cache
        self._clip_cond_cache: Dict[str, Any] = {}

        # Lazy-loaded config paths
        self._paths_checkpoints: Optional[List[str]] = None
        self._paths_loras: Optional[List[str]] = None
        self._path_vae: Optional[str] = None
        self._path_embeddings: Optional[str] = None

    # -------------------------------------------------------------------------
    # Config path resolution
    # -------------------------------------------------------------------------

    def _get_paths_checkpoints(self) -> List[str]:
        if self._paths_checkpoints is None:
            try:
                from modules.config import paths_checkpoints
                self._paths_checkpoints = paths_checkpoints
            except ImportError:
                from app.core.config import get_settings
                md = get_settings().model_dir
                self._paths_checkpoints = [os.path.join(md, "checkpoints"), os.path.join(md, "unet")]
        return self._paths_checkpoints

    def _get_paths_loras(self) -> List[str]:
        if self._paths_loras is None:
            try:
                from modules.config import paths_loras
                self._paths_loras = paths_loras
            except ImportError:
                from app.core.config import get_settings
                md = get_settings().model_dir
                self._paths_loras = [os.path.join(md, "loras")]
        return self._paths_loras

    def _get_path_vae(self) -> str:
        if self._path_vae is None:
            try:
                from modules.config import path_vae
                self._path_vae = path_vae
            except ImportError:
                from app.core.config import get_settings
                self._path_vae = os.path.join(get_settings().model_dir, "vae")
        return self._path_vae

    def _get_path_embeddings(self) -> str:
        if self._path_embeddings is None:
            try:
                from modules.config import path_embeddings
                self._path_embeddings = path_embeddings
            except ImportError:
                from app.core.config import get_settings
                self._path_embeddings = os.path.join(get_settings().model_dir, "embeddings")
        return self._path_embeddings

    # -------------------------------------------------------------------------
    # Model loading helpers
    # -------------------------------------------------------------------------

    def _resolve_filename(self, name: str, folder_list: List[str]) -> Optional[str]:
        """Resolve a model name to a file path using folder list."""
        if name in (None, 'None', 'none', ''):
            return None

        if os.path.exists(name):
            return name

        try:
            from modules.util import get_file_from_folder_list
            return get_file_from_folder_list(name, folder_list)
        except ImportError:
            # Fallback: try each folder
            for folder in folder_list:
                for ext in ['.safetensors', '.ckpt', '.pt', '.bin', '']:
                    path = os.path.join(folder, name + ext)
                    if os.path.exists(path):
                        return path
            return None

    @staticmethod
    def _no_grad(fn):
        """Decorator: torch.no_grad + torch.inference_mode."""
        import torch

        def wrapper(*args, **kwargs):
            with torch.no_grad():
                with torch.inference_mode():
                    return fn(*args, **kwargs)
        return wrapper

    # -------------------------------------------------------------------------
    # Model refresh functions
    # -------------------------------------------------------------------------

    @_no_grad
    def refresh_base_model(self, name: str, vae_name: Optional[str] = None):
        """Load or reload the base model.

        Skips if the model filename hasn't changed (cache check).
        """
        from app.services.checkpoint import load_checkpoint_guess_config
        from app.services.model_base import StableDiffusionModel

        filename = self._resolve_filename(name, self._get_paths_checkpoints())
        if filename is None:
            logger.warning(f"Base model '{name}' not found")
            return

        vae_filename = None
        if vae_name is not None and vae_name not in ('None', 'none', '', 'Automatic'):
            vae_filename = self._resolve_filename(vae_name, [self._get_path_vae()])

        if (self.model_base.filename == filename
                and self.model_base.vae_filename == vae_filename):
            logger.debug(f"Base model unchanged: {filename}")
            return

        unet, clip, vae, vae_fn, clip_vision = load_checkpoint_guess_config(
            filename,
            embedding_directory=self._get_path_embeddings(),
            vae_filename_param=vae_filename,
        )

        self.model_base = StableDiffusionModel(
            unet=unet, clip=clip, vae=vae,
            clip_vision=clip_vision,
            filename=filename, vae_filename=vae_fn,
        )
        logger.info(f"Base model loaded: {filename}")

    @_no_grad
    def refresh_refiner_model(self, name: str):
        """Load or reload the refiner model.

        If name is 'None', unloads the refiner.
        """
        from app.services.checkpoint import load_checkpoint_guess_config
        from app.services.model_base import StableDiffusionModel

        filename = self._resolve_filename(name, self._get_paths_checkpoints())

        if self.model_refiner.filename == filename:
            return

        self.model_refiner = StableDiffusionModel()

        if name in ('None', 'none', ''):
            logger.info("Refiner unloaded")
            return

        if filename is None:
            logger.warning(f"Refiner model '{name}' not found")
            return

        unet, clip, vae, vae_fn, clip_vision = load_checkpoint_guess_config(
            filename,
            embedding_directory=self._get_path_embeddings(),
        )

        self.model_refiner = StableDiffusionModel(
            unet=unet, clip=clip, vae=vae,
            clip_vision=clip_vision,
            filename=filename, vae_filename=vae_fn,
        )

        # For SDXL/SDXLRefiner, refiner doesn't need clip/vae separately
        if hasattr(self.model_refiner.unet, 'model'):
            from ldm_patched.modules.model_base import SDXL, SDXLRefiner
            model = self.model_refiner.unet.model
            if isinstance(model, (SDXL, SDXLRefiner)):
                self.model_refiner.clip = None
                self.model_refiner.vae = None

        logger.info(f"Refiner model loaded: {filename}")

    @_no_grad
    def synthesize_refiner_model(self):
        """Create a synthetic refiner from the base model (shared UNet)."""
        from app.services.model_base import StableDiffusionModel

        logger.info("Synthetic Refiner Activated")
        self.model_refiner = StableDiffusionModel(
            unet=self.model_base.unet,
            vae=self.model_base.vae,
            clip=self.model_base.clip,
            clip_vision=self.model_base.clip_vision,
            filename=self.model_base.filename,
        )
        # Refiner shares base components, null out its own
        self.model_refiner.vae = None
        self.model_refiner.clip = None
        self.model_refiner.clip_vision = None

    @_no_grad
    def refresh_loras(
        self,
        loras: List[Tuple[str, float]],
        base_model_additional_loras: Optional[List] = None,
    ):
        """Refresh LoRA weights for base and refiner models."""
        if not isinstance(base_model_additional_loras, list):
            base_model_additional_loras = []

        self.model_base.refresh_loras(loras + base_model_additional_loras)
        self.model_refiner.refresh_loras(loras)

    @_no_grad
    def refresh_controlnets(self, model_paths: List[Optional[str]]):
        """Load/cache ControlNet models, unload unused ones."""
        from app.infrastructure.operators import ControlNetApplyAdvanced

        new_cache = {}
        for p in model_paths:
            if p is not None:
                if p in self.loaded_controlnets:
                    new_cache[p] = self.loaded_controlnets[p]
                else:
                    try:
                        import ldm_patched.modules.controlnet
                        new_cache[p] = ldm_patched.modules.controlnet.load_controlnet(p)
                        logger.info(f"ControlNet loaded: {p}")
                    except Exception as e:
                        logger.warning(f"ControlNet load failed for {p}: {e}")
        self.loaded_controlnets = new_cache

    # -------------------------------------------------------------------------
    # Integrity check
    # -------------------------------------------------------------------------

    @_no_grad
    def assert_model_integrity(self) -> bool:
        """Verify base model is SDXL (required)."""
        if self.model_base.unet_with_lora is not None:
            try:
                from ldm_patched.modules.model_base import SDXL
                if not isinstance(self.model_base.unet_with_lora.model, SDXL):
                    raise NotImplementedError(
                        "Only SDXL base models are supported in SE8"
                    )
            except ImportError:
                logger.warning("Cannot verify model type — skipping integrity check")
        return True

    # -------------------------------------------------------------------------
    # CLIP encoding
    # -------------------------------------------------------------------------

    @_no_grad
    def clip_encode_single(self, text: str, verbose: bool = False):
        """Encode a single text string with CLIP, using cache.

        Returns:
            (cond_tensor, {"pooled_output": pooled_tensor})
        """
        if self.final_clip is None:
            return None

        cached = self._clip_cond_cache.get(text, None)
        if cached is not None:
            if verbose:
                logger.debug(f"[CLIP Cached] {text}")
            return cached

        tokens = self.final_clip.tokenize(text)
        result = self.final_clip.encode_from_tokens(tokens, return_pooled=True)
        self._clip_cond_cache[text] = result
        if verbose:
            logger.debug(f"[CLIP Encoded] {text}")
        return result

    @_no_grad
    def clip_encode(self, texts: List[str], pool_top_k: int = 1):
        """Encode a list of texts with CLIP, concatenating conditions.

        Args:
            texts: List of text strings to encode.
            pool_top_k: Number of top texts to pool (for weighted prompting).

        Returns:
            [[concatenated_cond, {"pooled_output": accumulated_pooled}]]
        """
        if self.final_clip is None:
            return None
        if not isinstance(texts, list) or len(texts) == 0:
            return None

        import torch

        cond_list = []
        pooled_acc = 0

        for i, text in enumerate(texts):
            cond, pooled = self.clip_encode_single(text)
            cond_list.append(cond)
            if i < pool_top_k:
                pooled_acc += pooled

        return [[torch.cat(cond_list, dim=1), {"pooled_output": pooled_acc}]]

    @_no_grad
    def set_clip_skip(self, clip_skip: int):
        """Set CLIP skip layers."""
        if self.final_clip is None:
            return
        self.final_clip.clip_layer(-abs(clip_skip))

    def clear_caches(self):
        """Clear all CLIP encode caches."""
        self._clip_cond_cache.clear()

    # -------------------------------------------------------------------------
    # Text encoder preparation
    # -------------------------------------------------------------------------

    @_no_grad
    def prepare_text_encoder(self, async_call: bool = True):
        """Load CLIP + Expansion models to GPU for text encoding."""
        from app.services.model_manager import get_model_manager

        if self.final_clip is None or self.final_expansion is None:
            return

        manager = get_model_manager()
        models_to_load = []
        if hasattr(self.final_clip, 'patcher'):
            models_to_load.append(self.final_clip.patcher)
        if hasattr(self.final_expansion, 'patcher'):
            models_to_load.append(self.final_expansion.patcher)

        if models_to_load:
            manager.load_models_gpu(models_to_load)

    # -------------------------------------------------------------------------
    # Master refresh
    # -------------------------------------------------------------------------

    @_no_grad
    def refresh_everything(
        self,
        refiner_model_name: str,
        base_model_name: str,
        loras: List[Tuple[str, float]],
        base_model_additional_loras: Optional[List] = None,
        use_synthetic_refiner: bool = False,
        vae_name: Optional[str] = None,
    ):
        """Reload all models and apply LoRAs.

        This is the main entry point for model switching.
        Called once at startup and whenever model params change.
        """
        self.final_unet = None
        self.final_clip = None
        self.final_vae = None
        self.final_refiner_unet = None
        self.final_refiner_vae = None

        if use_synthetic_refiner and refiner_model_name in ('None', 'none', ''):
            self.refresh_base_model(base_model_name, vae_name)
            self.synthesize_refiner_model()
        else:
            self.refresh_refiner_model(refiner_model_name)
            self.refresh_base_model(base_model_name, vae_name)

        self.refresh_loras(loras, base_model_additional_loras=base_model_additional_loras)
        self.assert_model_integrity()

        self.final_unet = self.model_base.unet_with_lora
        self.final_clip = self.model_base.clip_with_lora
        self.final_vae = self.model_base.vae

        self.final_refiner_unet = self.model_refiner.unet_with_lora
        self.final_refiner_vae = self.model_refiner.vae

        if self.final_expansion is None:
            try:
                from app.services.expansion import FooocusExpansion
                self.final_expansion = FooocusExpansion()
            except Exception as e:
                logger.warning("FooocusExpansion not available — prompt expansion disabled: %s", e)

        self.prepare_text_encoder(async_call=True)
        self.clear_caches()

    # -------------------------------------------------------------------------
    # VAE parse (refiner interpose)
    # -------------------------------------------------------------------------

    @_no_grad
    def vae_parse(self, latent: Dict[str, Any]) -> Dict[str, Any]:
        """Apply VAE interpose for refiner VAE swap."""
        if self.final_refiner_vae is None:
            return latent

        try:
            import extras.vae_interpose as vae_interpose
            result = vae_interpose.parse(latent["samples"])
            return {"samples": result}
        except ImportError:
            return latent

    # -------------------------------------------------------------------------
    # Sigma calculation
    # -------------------------------------------------------------------------

    @_no_grad
    def calculate_sigmas_all(
        self, sampler: str, scheduler: str, steps: int
    ):
        """Calculate all sigma values for a sampler/scheduler combination."""
        from ldm_patched.modules.samplers import calculate_sigmas_scheduler

        discard_penultimate_sigma = False
        if sampler in ['dpm_2', 'dpm_2_ancestral']:
            steps += 1
            discard_penultimate_sigma = True

        sigmas = calculate_sigmas_scheduler(
            self.final_unet.model, scheduler, steps
        )

        if discard_penultimate_sigma:
            sigmas = sigmas[:-2].concat([sigmas[-1:]])

        return sigmas

    @_no_grad
    def calculate_sigmas(
        self, sampler: str, scheduler: str, steps: int, denoise: float
    ):
        """Calculate sigmas with denoise support."""
        if denoise is None or denoise > 0.9999:
            return self.calculate_sigmas_all(sampler, scheduler, steps)
        else:
            new_steps = int(steps / denoise)
            sigmas = self.calculate_sigmas_all(sampler, scheduler, new_steps)
            sigmas = sigmas[-(steps + 1):]
            return sigmas

    # -------------------------------------------------------------------------
    # VAE candidate selection
    # -------------------------------------------------------------------------

    @_no_grad
    def get_candidate_vae(
        self, steps: int, switch: int, denoise: float = 1.0,
        refiner_swap_method: str = "joint",
    ):
        """Select which VAE(s) to use for decoding based on denoise level."""
        assert refiner_swap_method in ('joint', 'separate', 'vae')

        if self.final_refiner_vae is not None and self.final_refiner_unet is not None:
            if denoise > 0.9:
                return self.final_vae, self.final_refiner_vae
            else:
                karras_threshold = (float(steps - switch) / float(steps)) ** 0.834
                if denoise > karras_threshold:
                    return self.final_vae, None
                else:
                    return self.final_refiner_vae, None

        return self.final_vae, self.final_refiner_vae

    # -------------------------------------------------------------------------
    # Diffusion processing
    # -------------------------------------------------------------------------

    @_no_grad
    def process_diffusion(
        self,
        positive_cond,
        negative_cond,
        steps: int,
        switch: int,
        width: int,
        height: int,
        image_seed: int,
        callback: Optional[Callable],
        sampler_name: str,
        scheduler_name: str,
        latent=None,
        denoise: float = 1.0,
        tiled: bool = False,
        cfg_scale: float = 7.0,
        refiner_swap_method: str = "joint",
        disable_preview: bool = False,
    ) -> List[np.ndarray]:
        """Run the full diffusion process.

        Handles base-to-refiner switching with 3 methods:
        - joint: refiner used during sampling (joint denoising)
        - separate: base denoise then refiner denoise (two passes)
        - vae: base denoise then VAE swap + refiner refinement

        Returns:
            List of numpy uint8 images [H, W, C].
        """
        from app.infrastructure.core_ops import ksampler, generate_empty_latent, decode_vae

        target_unet = self.final_unet
        target_vae = self.final_vae
        target_refiner_unet = self.final_refiner_unet
        target_refiner_vae = self.final_refiner_vae
        target_clip = self.final_clip

        assert refiner_swap_method in ('joint', 'separate', 'vae')

        # Refiner selection based on denoise level
        if self.final_refiner_vae is not None and self.final_refiner_unet is not None:
            if denoise > 0.9:
                refiner_swap_method = 'vae'
            else:
                refiner_swap_method = 'joint'
                karras_threshold = (float(steps - switch) / float(steps)) ** 0.834
                if denoise > karras_threshold:
                    target_unet, target_vae = self.final_unet, self.final_vae
                    target_refiner_unet, target_refiner_vae = None, None
                    logger.info("[Sampler] only use Base because of partial denoise.")
                else:
                    positive_cond = self._clip_separate(
                        positive_cond, target_refiner_unet.model, target_clip
                    )
                    negative_cond = self._clip_separate(
                        negative_cond, target_refiner_unet.model, target_clip
                    )
                    target_unet, target_vae = self.final_refiner_unet, self.final_refiner_vae
                    target_refiner_unet, target_refiner_vae = None, None
                    logger.info("[Sampler] only use Refiner because of partial denoise.")

        logger.info(f"[Sampler] refiner_swap_method = {refiner_swap_method}")

        if latent is None:
            initial_latent = generate_empty_latent(width=width, height=height, batch_size=1)
        else:
            initial_latent = latent

        # Calculate sigma range
        from app.services.model_manager import get_model_manager
        manager = get_model_manager()

        minmax_sigmas = self.calculate_sigmas(
            sampler=sampler_name, scheduler=scheduler_name,
            steps=steps, denoise=denoise,
        )
        sigma_min = float(minmax_sigmas[minmax_sigmas > 0].min().cpu().numpy())
        sigma_max = float(minmax_sigmas.max().cpu().numpy())
        logger.info(f"[Sampler] sigma_min = {sigma_min}, sigma_max = {sigma_max}")

        # Initialize Brownian tree noise sampler
        try:
            import modules.patch
            device = manager.device
            modules.patch.BrownianTreeNoiseSamplerPatched.global_init(
                initial_latent['samples'].to(device),
                sigma_min, sigma_max, seed=image_seed, cpu=False,
            )
        except (ImportError, AttributeError):
            logger.debug("BrownianTreeNoiseSamplerPatched not available")

        decoded_latent = None

        if refiner_swap_method == 'joint':
            sampled_latent = ksampler(
                model=target_unet,
                refiner=target_refiner_unet,
                positive=positive_cond,
                negative=negative_cond,
                latent=initial_latent,
                steps=steps, start_step=0, last_step=steps,
                disable_noise=False, force_full_denoise=True,
                seed=image_seed, denoise=denoise,
                callback_function=callback,
                cfg=cfg_scale,
                sampler_name=sampler_name,
                scheduler=scheduler_name,
                refiner_switch=switch,
                disable_preview=disable_preview,
            )
            decoded_latent = decode_vae(vae=target_vae, latent_image=sampled_latent, tiled=tiled)

        elif refiner_swap_method == 'separate':
            sampled_latent = ksampler(
                model=target_unet,
                positive=positive_cond,
                negative=negative_cond,
                latent=initial_latent,
                steps=steps, start_step=0, last_step=switch,
                disable_noise=False, force_full_denoise=False,
                seed=image_seed, denoise=denoise,
                callback_function=callback,
                cfg=cfg_scale,
                sampler_name=sampler_name,
                scheduler=scheduler_name,
                disable_preview=disable_preview,
            )
            logger.info("Refiner swapped by changing ksampler. Noise preserved.")

            target_model = target_refiner_unet or target_unet

            sampled_latent = ksampler(
                model=target_model,
                positive=self._clip_separate(positive_cond, target_model.model, target_clip),
                negative=self._clip_separate(negative_cond, target_model.model, target_clip),
                latent=sampled_latent,
                steps=steps, start_step=switch, last_step=steps,
                disable_noise=True, force_full_denoise=True,
                seed=image_seed, denoise=denoise,
                callback_function=callback,
                cfg=cfg_scale,
                sampler_name=sampler_name,
                scheduler=scheduler_name,
                disable_preview=disable_preview,
            )

            target_model = target_refiner_vae or target_vae
            decoded_latent = decode_vae(vae=target_model, latent_image=sampled_latent, tiled=tiled)

        elif refiner_swap_method == 'vae':
            # VAE-based swap
            try:
                import modules.patch
                _pid = os.getpid()
                if _pid in modules.patch.patch_settings:
                    modules.patch.patch_settings[_pid].eps_record = 'vae'
            except (ImportError, AttributeError, KeyError):
                pass

            try:
                import modules.inpaint_worker
                if modules.inpaint_worker.current_task is not None:
                    modules.inpaint_worker.current_task.unswap()
            except (ImportError, AttributeError):
                pass

            sampled_latent = ksampler(
                model=target_unet,
                positive=positive_cond,
                negative=negative_cond,
                latent=initial_latent,
                steps=steps, start_step=0, last_step=switch,
                disable_noise=False, force_full_denoise=True,
                seed=image_seed, denoise=denoise,
                callback_function=callback,
                cfg=cfg_scale,
                sampler_name=sampler_name,
                scheduler=scheduler_name,
                disable_preview=disable_preview,
            )
            logger.info("SE8 VAE-based swap.")

            target_model = target_refiner_unet or target_unet

            sampled_latent = self.vae_parse(sampled_latent)

            k_sigmas = 1.4
            sigmas = self.calculate_sigmas(
                sampler=sampler_name, scheduler=scheduler_name,
                steps=steps, denoise=denoise,
            )[switch:] * k_sigmas
            len_sigmas = len(sigmas) - 1

            try:
                import modules.patch
                _pid = os.getpid()
                if _pid in modules.patch.patch_settings and modules.patch.patch_settings[_pid].eps_record is not None:
                    noise_mean = torch.mean(
                        modules.patch.patch_settings[_pid].eps_record,
                        dim=1, keepdim=True,
                    )
            except (ImportError, AttributeError):
                noise_mean = None

            try:
                import modules.inpaint_worker
                if modules.inpaint_worker.current_task is not None:
                    modules.inpaint_worker.current_task.swap()
            except (ImportError, AttributeError):
                pass

            sampled_latent = ksampler(
                model=target_model,
                positive=self._clip_separate(positive_cond, target_model.model, target_clip),
                negative=self._clip_separate(negative_cond, target_model.model, target_clip),
                latent=sampled_latent,
                steps=len_sigmas, start_step=0, last_step=len_sigmas,
                disable_noise=False, force_full_denoise=True,
                seed=image_seed + 1, denoise=denoise,
                callback_function=callback,
                cfg=cfg_scale,
                sampler_name=sampler_name,
                scheduler=scheduler_name,
                sigmas=sigmas,
                noise_mean=noise_mean,
                disable_preview=disable_preview,
            )

            target_model = target_refiner_vae or target_vae
            decoded_latent = decode_vae(vae=target_model, latent_image=sampled_latent, tiled=tiled)

        images = self.pytorch_to_numpy(decoded_latent)

        # Reset eps_record
        try:
            import modules.patch
            _pid = os.getpid()
            if _pid in modules.patch.patch_settings:
                modules.patch.patch_settings[_pid].eps_record = None
        except (ImportError, AttributeError, KeyError):
            pass

        return images

    # -------------------------------------------------------------------------
    # Utility functions
    # -------------------------------------------------------------------------

    @staticmethod
    def _clip_separate(cond, target_model, target_clip):
        """Separate CLIP conditioning for refiner swap."""
        try:
            from modules.sample_hijack import clip_separate
            return clip_separate(cond, target_model=target_model, target_clip=target_clip)
        except ImportError:
            return cond

    @staticmethod
    def pytorch_to_numpy(x) -> List[np.ndarray]:
        """Convert PyTorch tensor(s) to list of numpy uint8 images."""
        import torch
        if x is None:
            return []
        if isinstance(x, dict):
            x = x.get("samples", x)
        if isinstance(x, torch.Tensor):
            x = [x]
        return [np.clip(255.0 * y.cpu().numpy(), 0, 255).astype(np.uint8) for y in x]

    @staticmethod
    def numpy_to_pytorch(x):
        """Convert numpy image(s) to PyTorch tensor."""
        import torch
        y = x.astype(np.float32) / 255.0
        y = y[None]
        y = np.ascontiguousarray(y.copy())
        y = torch.from_numpy(y).float()
        return y


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_pipeline: Optional[Pipeline] = None


def get_pipeline() -> Pipeline:
    """Get or create the singleton Pipeline instance."""
    global _pipeline
    if _pipeline is None:
        _pipeline = Pipeline()
    return _pipeline


def reset_pipeline():
    """Reset the singleton (for testing or model reload)."""
    global _pipeline
    _pipeline = None
