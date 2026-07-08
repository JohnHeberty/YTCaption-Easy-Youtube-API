"""FaceID Plus v2 adapter classes for SE8 Image Generation.

Extracted from worker.py to reduce God Module complexity.
Architecture:
  - FaceIDProj: Linear(512→1024) + Perceiver Resampler → 4 × 2048-d tokens
  - FaceIDIPAdapter: LoRA (q/k/v/out) + standard to_k_ip/to_v_ip
"""
from __future__ import annotations

import logging

import torch

logger = logging.getLogger(__name__)


class FaceIDProj(torch.nn.Module):
    """Projection network for FaceID Plus v2.

    Projects InsightFace embeddings (512-d) to cross-attention tokens (4 × 2048-d)
    using a linear projection + Perceiver Resampler.
    """

    def __init__(self, state_dict: dict):
        super().__init__()
        # Linear projection: 512 → 1024 → 8192
        self.proj = torch.nn.Sequential(
            torch.nn.Linear(512, 1024),
            torch.nn.GELU(),
            torch.nn.Linear(1024, 8192),
        )
        # Perceiver Resampler
        from extras.resampler import Resampler
        self.perceiver = Resampler(
            dim=2048, depth=4, dim_head=64, heads=20,
            num_queries=4, embedding_dim=1280, output_dim=2048, ff_mult=4,
        )
        self.norm = torch.nn.LayerNorm(2048)

        # Load weights with prefix mapping
        proj_sd = {}
        for k, v in state_dict.items():
            if k.startswith("proj."):
                proj_sd[k] = v
            elif k.startswith("perceiver_resampler."):
                proj_sd["perceiver." + k[len("perceiver_resampler."):]] = v
            elif k.startswith("norm."):
                proj_sd[k] = v

        missing, unexpected = self.load_state_dict(proj_sd, strict=False)
        if missing:
            logger.warning("FaceID proj missing keys: %s", missing[:5])
        logger.info("FaceID proj loaded (proj + perceiver + norm)")

    def forward(self, embeds: torch.Tensor) -> torch.Tensor:
        """embeds: [B, 512] InsightFace embedding → [B, 4, 2048] cross-attention tokens"""
        x = self.proj(embeds)  # [B, 512] → [B, 8192]
        x = x.unsqueeze(1)  # [B, 1, 8192]
        x = self.perceiver(x)  # [B, 4, 2048]
        x = self.norm(x)
        return x


class FaceIDIPAdapter(torch.nn.Module):
    """FaceID Plus v2 with LoRA modifications + standard IP-Adapter KV injection."""

    def __init__(self, state_dict: dict, cross_attention_dim: int = 2048):
        super().__init__()
        self.cross_attention_dim = cross_attention_dim

        # Extract unique block indices from ip_adapter keys
        # Keys like "0.to_q_lora.down.weight", "1.to_k_ip.weight"
        block_indices = set()
        for k in state_dict.keys():
            idx = k.split(".")[0]
            if idx.isdigit():
                block_indices.add(int(idx))
        self.block_indices = sorted(block_indices)
        logger.info("FaceID IP-Adapter: %d blocks", len(self.block_indices))

        # For each block, create to_k_ip and to_v_ip linear layers
        self.to_kvs = torch.nn.ModuleList()
        for idx in self.block_indices:
            # Determine output dimension from state dict
            k_key = f"{idx}.to_k_ip.weight"
            if k_key in state_dict:
                out_dim = state_dict[k_key].shape[0]
            else:
                out_dim = 640  # default for SDXL
            to_kv = torch.nn.Linear(cross_attention_dim, out_dim * 2, bias=False)
            # Load weights
            if k_key in state_dict:
                to_kv.weight.data[:out_dim] = state_dict[k_key]
            v_key = f"{idx}.to_v_ip.weight"
            if v_key in state_dict:
                to_kv.weight.data[out_dim:] = state_dict[v_key]
            self.to_kvs.append(to_kv)

    def forward(self, cond: torch.Tensor) -> list[torch.Tensor]:
        """cond: [B, 4, 2048] → list of KV tensors for each block"""
        results = []
        for i, to_kv in enumerate(self.to_kvs):
            kv = to_kv(cond.to(to_kv.weight.device, dtype=to_kv.weight.dtype))
            results.append(kv)
        return results
