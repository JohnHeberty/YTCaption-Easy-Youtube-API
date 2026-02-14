"""
Frame Preprocessor Module - Sprint 02

Implements advanced preprocessing techniques for low-quality/compressed videos:
- CLAHE (Contrast Limited Adaptive Histogram Equalization)
- Adaptive Binarization (Otsu + Gaussian Adaptive)
- Noise Reduction (Bilateral + Gaussian)
- Sharpening (Unsharp mask)

Author: YTCaption Team
Sprint: 02 - Advanced Preprocessing
"""

import cv2
import numpy as np
from typing import Tuple, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class FramePreprocessor:
    """
    Advanced frame preprocessing for improved OCR accuracy on low-quality videos.
    
    Key Features:
    - CLAHE: Enhances contrast adaptively (local histogram equalization)
    - Adaptive Binarization: Converts to binary for better text detection
    - Noise Reduction: Removes compression artifacts
    - Sharpening: Enhances text edges
    
    Usage:
        preprocessor = FramePreprocessor(use_clahe=True, use_binarization=True)
        enhanced_frame = preprocessor.preprocess(frame)
    """
    
    def __init__(
        self,
        use_clahe: bool = True,
        use_binarization: bool = False,
        use_noise_reduction: bool = True,
        use_sharpening: bool = False,
        clahe_clip_limit: float = 2.0,
        clahe_tile_size: Tuple[int, int] = (8, 8),
        binarization_method: str = 'adaptive',  # 'adaptive', 'otsu', 'both'
        adaptive_block_size: int = 11,
        adaptive_c: int = 2,
    ):
        """
        Initialize preprocessor with configuration.
        
        Args:
            use_clahe: Apply CLAHE (recommended for low-contrast videos)
            use_binarization: Convert to binary (good for clear text, may hurt complex backgrounds)
            use_noise_reduction: Apply noise reduction (recommended for compressed videos)
            use_sharpening: Apply sharpening (can help blurry text, may amplify noise)
            clahe_clip_limit: CLAHE contrast limit (higher = more contrast, 2.0-4.0 typical)
            clahe_tile_size: CLAHE grid size (smaller = more local, 8x8 typical)
            binarization_method: 'adaptive' (local), 'otsu' (global), 'both' (max of both)
            adaptive_block_size: Block size for adaptive threshold (must be odd, 11-21 typical)
            adaptive_c: Constant subtracted from mean in adaptive threshold (2-10 typical)
        """
        self.use_clahe = use_clahe
        self.use_binarization = use_binarization
        self.use_noise_reduction = use_noise_reduction
        self.use_sharpening = use_sharpening
        
        # CLAHE parameters
        self.clahe_clip_limit = clahe_clip_limit
        self.clahe_tile_size = clahe_tile_size
        self.clahe = cv2.createCLAHE(clipLimit=clahe_clip_limit, tileGridSize=clahe_tile_size)
        
        # Binarization parameters
        self.binarization_method = binarization_method
        self.adaptive_block_size = adaptive_block_size
        self.adaptive_c = adaptive_c
        
        logger.info(f"FramePreprocessor initialized: CLAHE={use_clahe}, "
                   f"Binarization={use_binarization}, NoiseReduction={use_noise_reduction}, "
                   f"Sharpening={use_sharpening}")
    
    def preprocess(self, frame: np.ndarray, return_steps: bool = False) -> np.ndarray:
        """
        Apply preprocessing pipeline to frame.
        
        Args:
            frame: Input frame (BGR or grayscale)
            return_steps: If True, return dict with intermediate steps
        
        Returns:
            Preprocessed frame (grayscale) or dict with steps if return_steps=True
        """
        steps = {'original': frame.copy()}
        
        # Step 1: Convert to grayscale if needed
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame.copy()
        steps['grayscale'] = gray.copy()
        
        # Step 2: Noise reduction (before CLAHE to avoid amplifying noise)
        if self.use_noise_reduction:
            gray = self._apply_noise_reduction(gray)
            steps['noise_reduced'] = gray.copy()
        
        # Step 3: CLAHE (contrast enhancement)
        if self.use_clahe:
            gray = self._apply_clahe(gray)
            steps['clahe'] = gray.copy()
        
        # Step 4: Sharpening (enhance text edges)
        if self.use_sharpening:
            gray = self._apply_sharpening(gray)
            steps['sharpened'] = gray.copy()
        
        # Step 5: Binarization (convert to black/white)
        if self.use_binarization:
            gray = self._apply_binarization(gray)
            steps['binarized'] = gray.copy()
        
        if return_steps:
            steps['final'] = gray
            return steps
        
        return gray
    
    def _apply_clahe(self, gray: np.ndarray) -> np.ndarray:
        """Apply Contrast Limited Adaptive Histogram Equalization."""
        return self.clahe.apply(gray)
    
    def _apply_binarization(self, gray: np.ndarray) -> np.ndarray:
        """
        Apply binarization (convert to black/white).
        
        Methods:
        - adaptive: Local thresholding (good for varying lighting)
        - otsu: Global thresholding (good for bimodal histogram)
        - both: Max of both (union of detected text)
        """
        if self.binarization_method == 'adaptive':
            # Adaptive Gaussian thresholding
            binary = cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                self.adaptive_block_size,
                self.adaptive_c
            )
            return binary
        
        elif self.binarization_method == 'otsu':
            # Otsu's thresholding (automatic global threshold)
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            return binary
        
        elif self.binarization_method == 'both':
            # Combine both methods (max = union of detected text)
            adaptive = cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                self.adaptive_block_size,
                self.adaptive_c
            )
            _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            binary = cv2.max(adaptive, otsu)
            return binary
        
        else:
            logger.warning(f"Unknown binarization method: {self.binarization_method}, skipping")
            return gray
    
    def _apply_noise_reduction(self, gray: np.ndarray) -> np.ndarray:
        """
        Apply noise reduction.
        
        Uses bilateral filter: preserves edges while smoothing noise.
        """
        # Bilateral filter: edge-preserving smoothing
        # d=5: diameter of pixel neighborhood
        # sigmaColor=75: filter sigma in color space (larger = more colors mixed)
        # sigmaSpace=75: filter sigma in coordinate space (larger = farther pixels influence)
        denoised = cv2.bilateralFilter(gray, d=5, sigmaColor=75, sigmaSpace=75)
        return denoised
    
    def _apply_sharpening(self, gray: np.ndarray) -> np.ndarray:
        """
        Apply sharpening using unsharp mask.
        
        Unsharp mask = Original + (Original - Blurred) * amount
        """
        # Gaussian blur
        blurred = cv2.GaussianBlur(gray, (0, 0), sigmaX=1.0)
        
        # Unsharp mask with amount=1.5
        sharpened = cv2.addWeighted(gray, 1.5, blurred, -0.5, 0)
        
        return sharpened
    
    def get_config(self) -> Dict:
        """Get current preprocessor configuration."""
        return {
            'use_clahe': self.use_clahe,
            'use_binarization': self.use_binarization,
            'use_noise_reduction': self.use_noise_reduction,
            'use_sharpening': self.use_sharpening,
            'clahe_clip_limit': self.clahe_clip_limit,
            'clahe_tile_size': self.clahe_tile_size,
            'binarization_method': self.binarization_method,
            'adaptive_block_size': self.adaptive_block_size,
            'adaptive_c': self.adaptive_c,
        }
    
    @classmethod
    def create_preset(cls, preset: str) -> 'FramePreprocessor':
        """
        Create preprocessor with predefined preset.
        
        Presets:
        - 'none': No preprocessing (pass-through)
        - 'light': CLAHE only (fast, minimal impact)
        - 'medium': CLAHE + noise reduction (balanced)
        - 'heavy': All techniques (slow, max enhancement)
        - 'low_quality': Optimized for compressed/low-res videos
        - 'high_quality': Minimal processing for clean videos
        
        Usage:
            preprocessor = FramePreprocessor.create_preset('medium')
        """
        presets = {
            'none': {
                'use_clahe': False,
                'use_binarization': False,
                'use_noise_reduction': False,
                'use_sharpening': False,
            },
            'light': {
                'use_clahe': True,
                'use_binarization': False,
                'use_noise_reduction': False,
                'use_sharpening': False,
                'clahe_clip_limit': 2.0,
            },
            'medium': {
                'use_clahe': True,
                'use_binarization': False,
                'use_noise_reduction': True,
                'use_sharpening': False,
                'clahe_clip_limit': 2.5,
            },
            'heavy': {
                'use_clahe': True,
                'use_binarization': True,
                'use_noise_reduction': True,
                'use_sharpening': True,
                'clahe_clip_limit': 3.0,
                'binarization_method': 'adaptive',
            },
            'low_quality': {
                'use_clahe': True,
                'use_binarization': False,
                'use_noise_reduction': True,
                'use_sharpening': False,
                'clahe_clip_limit': 3.0,
                'clahe_tile_size': (8, 8),
            },
            'high_quality': {
                'use_clahe': True,
                'use_binarization': False,
                'use_noise_reduction': False,
                'use_sharpening': False,
                'clahe_clip_limit': 1.5,
            },
        }
        
        if preset not in presets:
            raise ValueError(f"Unknown preset: {preset}. Available: {list(presets.keys())}")
        
        logger.info(f"Creating preprocessor with preset: {preset}")
        return cls(**presets[preset])


# Convenience functions for quick usage
def preprocess_frame_light(frame: np.ndarray) -> np.ndarray:
    """Quick preprocessing: CLAHE only (fast)."""
    preprocessor = FramePreprocessor.create_preset('light')
    return preprocessor.preprocess(frame)


def preprocess_frame_medium(frame: np.ndarray) -> np.ndarray:
    """Quick preprocessing: CLAHE + noise reduction (balanced)."""
    preprocessor = FramePreprocessor.create_preset('medium')
    return preprocessor.preprocess(frame)


def preprocess_frame_heavy(frame: np.ndarray) -> np.ndarray:
    """Quick preprocessing: All techniques (max enhancement)."""
    preprocessor = FramePreprocessor.create_preset('heavy')
    return preprocessor.preprocess(frame)


if __name__ == "__main__":
    # Quick test
    print("FramePreprocessor - Sprint 02")
    print("=" * 60)
    
    # Test with dummy frame
    dummy_frame = np.random.randint(0, 255, (100, 200, 3), dtype=np.uint8)
    
    # Test all presets
    presets = ['none', 'light', 'medium', 'heavy', 'low_quality', 'high_quality']
    
    for preset in presets:
        preprocessor = FramePreprocessor.create_preset(preset)
        result = preprocessor.preprocess(dummy_frame)
        config = preprocessor.get_config()
        print(f"\n✅ Preset '{preset}':")
        print(f"   Config: {config}")
        print(f"   Output shape: {result.shape}, dtype: {result.dtype}")
    
    print("\n🎉 FramePreprocessor module working!")
