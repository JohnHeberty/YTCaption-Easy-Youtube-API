"""InpaintWorker — manages inpainting region, UNet patching, post-processing."""
from typing import Optional, Tuple
from common.log_utils import get_logger

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageFilter

logger = get_logger(__name__)

# Global singleton for current inpaint task
current_task: Optional["InpaintWorker"] = None
inpaint_head_model = None


def box_blur(x: np.ndarray, k: int) -> np.ndarray:
    """PIL-based box blur on numpy array."""
    img = Image.fromarray(x)
    img = img.filter(ImageFilter.BoxBlur(k))
    return np.array(img)


def max_filter_opencv(x: np.ndarray, ksize: int = 3) -> np.ndarray:
    """OpenCV dilate (max filter)."""
    kernel = np.ones((ksize, ksize), dtype=np.uint8)
    return cv2.dilate(x, kernel, iterations=1)


def morphological_open(x: np.ndarray) -> np.ndarray:
    """Custom iterative morphological opening for mask edges."""
    # 32 iterations of dilate-minus-8 to erode mask edges
    result = x.copy()
    for _ in range(32):
        dilated = max_filter_opencv(result, 3)
        result = np.maximum(result - 8, 0)
        result = np.where(dilated > 0, np.maximum(result, dilated - 8), result)
    return result


def up255(x: np.ndarray, t: float = 0) -> np.ndarray:
    """Threshold to binary 0/255."""
    return np.where(x > t, 255, 0).astype(np.uint8)


def regulate_abcd(x: np.ndarray, a: int, b: int, c: int, d: int) -> Tuple[int, int, int, int]:
    """Clamp bounding box to image dimensions."""
    h, w = x.shape[:2]
    a = max(0, min(a, w))
    b = max(0, min(b, w))
    c = max(0, min(c, h))
    d = max(0, min(d, h))
    return a, b, c, d


def compute_initial_abcd(x: np.ndarray) -> Tuple[int, int, int, int]:
    """Find bounding box of non-zero mask, expand to square with 15% margin."""
    mask = (x > 0).astype(np.uint8)
    coords = np.where(mask)
    if len(coords[0]) == 0:
        h, w = x.shape[:2]
        return 0, w, 0, h

    y_min, y_max = coords[0].min(), coords[0].max()
    x_min, x_max = coords[1].min(), coords[1].max()

    # Expand to square
    width = x_max - x_min
    height = y_max - y_min
    size = max(width, height)

    # Add 15% margin
    margin = int(size * 0.15)
    size = int(size * 1.3)

    # Center
    cx = (x_min + x_max) // 2
    cy = (y_min + y_max) // 2

    a = cx - size // 2
    b = cx + size // 2
    c = cy - size // 2
    d = cy + size // 2

    h, w = x.shape[:2]
    a = max(0, min(a, w))
    b = max(0, min(b, w))
    c = max(0, min(c, h))
    d = max(0, min(d, h))

    return a, b, c, d


def solve_abcd(
    x: np.ndarray, a: int, b: int, c: int, d: int, k: float = 0.618
) -> Tuple[int, int, int, int]:
    """Expand bounding box until it covers k fraction of image (aspect-ratio aware)."""
    h, w = x.shape[:2]
    target_area = h * w * k

    for _ in range(10):
        area = (d - c) * (b - a)
        if area >= target_area:
            break

        # Expand in the smaller dimension
        dw = b - a
        dh = d - c
        if dw < dh:
            expand = max(1, int((dh - dw) / 2))
            a = max(0, a - expand)
            b = min(w, b + expand)
        else:
            expand = max(1, int((dw - dh) / 2))
            c = max(0, c - expand)
            d = min(h, d + expand)

    return regulate_abcd(x, a, b, c, d)


def fooocus_fill(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Multi-scale iterative box-blur fill.

    Repeatedly blurs while preserving unmasked pixels, using decreasing
    kernel sizes (512 down to 3) with increasing repeats.
    """
    result = image.copy()
    mask_bool = mask > 128

    for kernel_size in [512, 256, 128, 64, 32, 16, 8, 4, 3]:
        repeats = max(1, 16 // max(kernel_size // 32, 1))
        for _ in range(repeats):
            blurred = box_blur(result, kernel_size)
            result = np.where(mask_bool[:, :, np.newaxis], blurred, result)

    return result


class InpaintHead(torch.nn.Module):
    """Tiny CNN head for inpainting: 5-channel input (4 latent + 1 mask) -> 320 channels."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.head = torch.nn.Parameter(torch.randn(320, 5, 3, 3) * 0.01)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Replicate padding
        x = F.pad(x, (1, 1, 1, 1), mode="replicate")
        return F.conv2d(x, self.head)


class InpaintWorker:
    """Central inpainting orchestrator.

    Manages cropping to region of interest, optional super-resolution,
    mask processing, latent storage, UNet patching, color correction,
    and post-processing.
    """

    def __init__(
        self,
        image: np.ndarray,
        mask: np.ndarray,
        use_fill: bool = True,
        k: float = 0.618,
    ):
        """
        Args:
            image: Input image (HWC, RGB, uint8)
            mask: Binary mask (H, W, uint8) — 255=masked, 0=keep
            use_fill: Whether to apply fooocus_fill preprocessing
            k: Fill ratio parameter
        """
        self.original_image = image.copy()
        self.original_mask = mask.copy()

        # Compute bounding box of mask
        a, b, c, d = compute_initial_abcd(mask)
        a, b, c, d = solve_abcd(mask, a, b, c, d, k)

        self.interested_a = a
        self.interested_b = b
        self.interested_c = c
        self.interested_d = d

        # Crop interested region
        self.interested_image = image[c:d, a:b].copy()
        self.interested_mask = mask[c:d, a:b].copy()

        # Upscale if too small (minimum 1024px)
        h, w = self.interested_image.shape[:2]
        if min(h, w) < 1024:
            from app.services.upscaler import perform_upscale
            self.interested_image = perform_upscale(self.interested_image)
            self.interested_mask = cv2.resize(
                self.interested_mask,
                (self.interested_image.shape[1], self.interested_image.shape[0]),
                interpolation=cv2.INTER_NEAREST,
            )

        # Resize to 1024 ceil
        h, w = self.interested_image.shape[:2]
        new_h = int(np.ceil(h / 64) * 64)
        new_w = int(np.ceil(w / 64) * 64)
        self.interested_image = cv2.resize(self.interested_image, (new_w, new_h))
        self.interested_mask = cv2.resize(self.interested_mask, (new_w, new_h), interpolation=cv2.INTER_NEAREST)

        # Apply fooocus_fill if enabled
        if use_fill:
            self.interested_fill = fooocus_fill(self.interested_image, self.interested_mask)
        else:
            self.interested_fill = self.interested_image.copy()

        # Resample mask to 0-1 float
        self.interested_mask = self.interested_mask.astype(np.float32) / 255.0

        # Apply morphological open to full mask
        self.interested_mask = morphological_open((self.interested_mask * 255).astype(np.uint8)).astype(np.float32) / 255.0

        # Latent storage
        self.latent: Optional[torch.Tensor] = None
        self.latent_fill: Optional[torch.Tensor] = None
        self.latent_mask: Optional[torch.Tensor] = None
        self.latent_after_swap: Optional[torch.Tensor] = None

        self.current_device = "cpu"
        logger.info(
            "InpaintWorker initialized: crop region %dx%d",
            self.interested_image.shape[1], self.interested_image.shape[0]
        )

    def load_latent(
        self,
        latent_fill: torch.Tensor,
        latent_mask: torch.Tensor,
        latent_swap: Optional[torch.Tensor] = None,
    ):
        """Store latent representations."""
        self.latent_fill = latent_fill
        self.latent_mask = latent_mask
        self.latent = latent_fill.clone()
        if latent_swap is not None:
            self.latent_after_swap = latent_swap

    def patch(
        self,
        inpaint_head_model_path: str,
        inpaint_latent: torch.Tensor,
        inpaint_latent_mask: torch.Tensor,
        model,
    ):
        """Load InpaintHead, run inference, patch UNet's input block 0."""
        global inpaint_head_model

        if inpaint_head_model is None:
            inpaint_head_model = InpaintHead()
            state_dict = torch.load(inpaint_head_model_path, map_location="cpu")
            inpaint_head_model.load_state_dict(state_dict, strict=False)
            inpaint_head_model.eval()

        # Concatenate mask + latent
        x = torch.cat([inpaint_latent_mask, inpaint_latent], dim=1)
        inpaint_features = inpaint_head_model(x)

        # Patch UNet input block 0 to add inpaint features
        def patched_input_block(block, x_in, transformer_options):
            result = block(x_in, transformer_options)
            if isinstance(result, tuple):
                h, = result
            else:
                h = result
            # Add inpaint features at first input block
            h = h + inpaint_features.to(h.device, h.dtype)
            return (h,)

        # Register patch
        model.clone().set_model_patch(
            "inpaint_features_add",
            lambda block, x_in, transformer_options: patched_input_block(block, x_in, transformer_options)
        )

        return model

    def swap(self):
        """Swap latent with latent_after_swap (for VAE-based refiner swap)."""
        if self.latent_after_swap is not None:
            self.latent, self.latent_after_swap = self.latent_after_swap, self.latent

    def unswap(self):
        """Reverse the swap."""
        self.swap()

    def color_correction(self, img: np.ndarray) -> np.ndarray:
        """Alpha-blend generated image with original using the morphological mask."""
        # Generate mask from interested_mask (upscale to match img size)
        mask = cv2.resize(
            (self.interested_mask * 255).astype(np.uint8),
            (img.shape[1], img.shape[0]),
            interpolation=cv2.INTER_LINEAR,
        ).astype(np.float32) / 255.0

        # Original crop
        original = cv2.resize(
            self.interested_image,
            (img.shape[1], img.shape[0]),
            interpolation=cv2.INTER_LINEAR,
        )

        # Alpha blend
        mask_3ch = mask[:, :, np.newaxis]
        result = (img * mask_3ch + original * (1 - mask_3ch)).astype(np.uint8)
        return result

    def post_process(self, img: np.ndarray) -> np.ndarray:
        """Resample generated content back to original crop dimensions, paste into original image."""
        # Resize generated image to original crop size
        crop_h = self.interested_d - self.interested_c
        crop_w = self.interested_b - self.interested_a
        img_resized = cv2.resize(img, (crop_w, crop_h), interpolation=cv2.INTER_LANCZOS4)

        # Apply color correction
        img_resized = self.color_correction(img_resized)

        # Paste into original image
        result = self.original_image.copy()
        result[self.interested_c:self.interested_d, self.interested_a:self.interested_b] = img_resized

        return result

    def visualize_mask_processing(self):
        """Return [interested_fill, interested_mask, interested_image] for debugging."""
        return [
            self.interested_fill,
            (self.interested_mask * 255).astype(np.uint8),
            self.interested_image,
        ]
