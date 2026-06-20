"""Prompt expansion engine — GPT-2 based prompt enhancement.

License: Algorithm by Lvmin Zhang at Stanford, 2023. CC-By NC 4.0 for external use.
"""
from __future__ import annotations

import math
from common.log_utils import get_logger
import os
import re

import numpy as np
import torch

logger = get_logger(__name__)

SEED_LIMIT_NUMPY = 2 ** 32
NEG_INF = -8192.0


def safe_str(x: str) -> str:
    """Clean string: deduplicate spaces, strip punctuation."""
    x = re.sub(r"\s+", " ", x).strip()
    x = re.sub(r"[,.]+$", "", x)
    return x


def remove_pattern(x: str, pattern: str) -> str:
    """Remove pattern from string."""
    return re.sub(pattern, "", x)


class FooocusExpansion:
    """GPT-2 based prompt expansion. Takes short prompts and generates expanded versions."""

    def __init__(self) -> None:
        from transformers import AutoTokenizer, AutoModelForCausalLM

        from app.core.config import get_settings

        settings = get_settings()
        model_path = getattr(settings, "expansion_model_path", None)
        if model_path is None:
            # Try common locations
            candidates = [
                os.path.join(os.getcwd(), "models", "expansion"),
                os.path.join(os.getcwd(), "data", "models", "expansion"),
                os.path.join(os.getcwd(), "data", "models", "prompt_expansion", "fooocus_expansion"),
                os.path.expanduser("~/.cache/fooocus/expansion"),
            ]
            for c in candidates:
                if os.path.exists(c):
                    model_path = c
                    break
            if model_path is None:
                raise FileNotFoundError(
                    "FooocusExpansion model not found. "
                    "Set expansion_model_path in config or download the model."
                )

        logger.info("Loading FooocusExpansion from %s", model_path)

        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForCausalLM.from_pretrained(model_path)

        # Build logits bias to mask non-positive vocabulary
        self._build_vocab_mask(model_path)

        # Move to GPU if available
        from app.services.model_manager import get_model_manager
        mm = get_model_manager()
        if mm.is_gpu_available():
            self.model = self.model.to(mm.device, dtype=torch.float16)

        self.model.eval()
        logger.info("FooocusExpansion loaded")

    def _build_vocab_mask(self, model_path: str) -> None:
        """Build logits bias tensor that masks non-positive vocabulary tokens."""
        vocab_size = self.model.config.vocab_size

        # Load positive word list
        positive_path = os.path.join(model_path, "positive.txt")
        if not os.path.exists(positive_path):
            logger.warning("positive.txt not found at %s, using empty mask", positive_path)
            self.logits_bias = torch.zeros(vocab_size)
            return

        with open(positive_path, "r", encoding="utf-8") as f:
            positive_words = set(line.strip().lower() for line in f if line.strip())

        # Get tokenizer vocabulary
        vocab = self.tokenizer.get_vocab()
        positive_ids = set()
        for word in positive_words:
            if word in vocab:
                positive_ids.add(vocab[word])

        # Build bias: 0 for positive tokens, NEG_INF for others
        self.logits_bias = torch.full((vocab_size,), NEG_INF)
        for token_id in positive_ids:
            self.logits_bias[token_id] = 0.0

        # Always allow token ID 11 (comma)
        if 11 < vocab_size:
            self.logits_bias[11] = 0.0

        logger.info(
            "Vocab mask: %d/%d positive tokens",
            len(positive_ids), vocab_size
        )

    def logits_processor(self, input_ids: torch.Tensor, scores: torch.Tensor) -> torch.Tensor:
        """Custom logits processor: mask already-used and non-positive tokens."""
        # Apply vocab mask
        scores = scores + self.logits_bias.to(scores.device)

        # Mask already-used tokens
        for i in range(input_ids.shape[0]):
            used_tokens = set(input_ids[i].tolist())
            for token_id in used_tokens:
                if token_id < scores.shape[-1]:
                    scores[i, token_id] = NEG_INF

        # Always allow comma (token ID 11)
        if 11 < scores.shape[-1]:
            scores[:, 11] = max(scores[:, 11].item(), 0.0)

        return scores

    @torch.no_grad()
    def __call__(self, prompt: str, seed: int = 42) -> str:
        """Expand a short prompt using GPT-2.

        Args:
            prompt: User prompt to expand
            seed: Random seed for generation

        Returns:
            Expanded prompt string
        """
        prompt = safe_str(prompt)
        if not prompt:
            return prompt

        # Calculate max_new_tokens to fit within 75-token CLIP boundary
        tokens = self.tokenizer.encode(prompt)
        current_len = len(tokens)
        # Next multiple of 75, minus current length
        target_len = math.ceil(current_len / 75) * 75
        max_new_tokens = max(target_len - current_len, 1)

        # Set seed
        np.random.seed(seed % SEED_LIMIT_NUMPY)
        torch.manual_seed(seed)

        # Generate
        from transformers import LogitsProcessorList
        logits_processors = LogitsProcessorList([self.logits_processor])

        input_ids = self.tokenizer.encode(prompt, return_tensors="pt")
        if next(self.model.parameters()).device.type == "cuda":
            input_ids = input_ids.to(self.model.device)

        output = self.model.generate(
            input_ids,
            max_new_tokens=max_new_tokens,
            top_k=100,
            do_sample=True,
            logits_processor=logits_processors,
        )

        expanded = self.tokenizer.decode(output[0], skip_special_tokens=True)
        expanded = safe_str(expanded)

        return expanded
