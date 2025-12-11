"""
Data Manager for EHTool
Handles loading and processing image datasets for error detection workflow
Adapted from original EHTool for FastAPI integration
"""
import os
import glob
import numpy as np
import tifffile
from PIL import Image
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path

from .utils import (
    to_uint8,
    ensure_grayscale_2d,
    enhance_contrast,
    array_to_base64,
    load_image_file,
    get_image_dimensions
)


class DataManager:
    """
    Manages image and mask data for error detection workflow
    Supports both 2D images and 3D TIFF stacks
    """
    
    def __init__(self):
        self.image_volume: Optional[np.ndarray] = None
        self.mask_volume: Optional[np.ndarray] = None
        self.is_3d: bool = False
        self.total_layers: int = 0
        self.image_shape: Optional[Tuple[int, ...]] = None
    
    def load_dataset(self, dataset_path: str, mask_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Load image dataset and optional mask dataset
        
        Args:
            dataset_path: Path to image file or directory
            mask_path: Optional path to mask file or directory
        
        Returns:
            Dictionary with dataset info
        """
        # Discover and load images
        image_data = self._load_volume(dataset_path)
        
        # Load masks if provided
        mask_data = None
        if mask_path:
            mask_data = self._load_volume(mask_path)
            
            # Validate mask dimensions match image
            if image_data['num_slices'] != mask_data['num_slices']:
                raise ValueError(
                    f"Mask layer count ({mask_data['num_slices']}) does not match "
                    f"image layer count ({image_data['num_slices']})"
                )
            
            # Validate 2D dimensions match
            img_shape = image_data['shape']
            mask_shape = mask_data['shape']
            if img_shape[-2:] != mask_shape[-2:]:
                raise ValueError(
                    f"Mask dimensions {mask_shape[-2:]} do not match "
                    f"image dimensions {img_shape[-2:]}"
                )
        
        # Store volume data
        self.image_volume = image_data['volume']
        self.mask_volume = mask_data['volume'] if mask_data else None
        self.is_3d = image_data['is_3d']
        self.total_layers = image_data['num_slices']
        self.image_shape = image_data['shape']
        
        return {
            "total_layers": self.total_layers,
            "is_3d": self.is_3d,
            "image_shape": self.image_shape,
            "has_masks": mask_data is not None
        }
    
    def get_layer(self, layer_index: int, enhance: bool = True) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """
        Get image and mask for a specific layer
        
        Args:
            layer_index: 0-based layer index
            enhance: Whether to apply contrast enhancement
        
        Returns:
            Tuple of (image_array, mask_array or None)
        """
        if layer_index < 0 or layer_index >= self.total_layers:
            raise IndexError(f"Layer index {layer_index} out of range [0, {self.total_layers})")
        
        # Get image slice
        if self.image_volume.ndim == 3:
            # 3D volume - get specific slice
            image = self.image_volume[layer_index]
        else:
            # 2D image
            image = self.image_volume
        
        image = ensure_grayscale_2d(image)
        
        if enhance:
            image = enhance_contrast(image)
        else:
            image = to_uint8(image)
        
        # Get mask slice if exists
        mask = None
        if self.mask_volume is not None:
            if self.mask_volume.ndim == 3:
                mask = self.mask_volume[layer_index]
            else:
                mask = self.mask_volume
            
            mask = ensure_grayscale_2d(mask)
            mask = to_uint8(mask)
        
        return image, mask
    
    def get_layer_base64(self, layer_index: int, enhance: bool = True) -> Tuple[str, Optional[str]]:
        """
        Get image and mask as base64-encoded strings
        
        Args:
            layer_index: 0-based layer index
            enhance: Whether to apply contrast enhancement
        
        Returns:
            Tuple of (image_base64, mask_base64 or None)
        """
        image, mask = self.get_layer(layer_index, enhance=enhance)
        
        image_base64 = array_to_base64(image, format='PNG')
        mask_base64 = array_to_base64(mask, format='PNG') if mask is not None else None
        
        return image_base64, mask_base64
    
    def get_layer_name(self, layer_index: int) -> str:
        """Get the name for a layer"""
        if layer_index < 0 or layer_index >= self.total_layers:
            return f"Layer {layer_index}"
        
        if self.is_3d:
            return f"Layer {layer_index + 1}"
        else:
            return "Image"
    
    def _load_volume(self, path: str) -> Dict[str, Any]:
        """
        Load volume data from a path (file, directory, or glob pattern)
        
        Args:
            path: Path to file, directory, or glob pattern
        
        Returns:
            Dictionary with volume, shape, num_slices, is_3d
        """
        path_obj = Path(path)
        
        # Single file
        if path_obj.is_file():
            if path.lower().endswith(('.tif', '.tiff')):
                # Load TIFF (may be multi-page)
                volume = tifffile.imread(path)
                
                if volume.ndim == 2:
                    # Single 2D image
                    return {
                        'volume': volume,
                        'shape': volume.shape,
                        'num_slices': 1,
                        'is_3d': False
                    }
                elif volume.ndim == 3:
                    # 3D stack
                    return {
                        'volume': volume,
                        'shape': volume.shape,
                        'num_slices': volume.shape[0],
                        'is_3d': True
                    }
                else:
                    raise ValueError(f"Unsupported TIFF dimensions: {volume.ndim}")
            else:
                # Load single 2D image (PNG, JPG, etc.)
                image = load_image_file(path)
                return {
                    'volume': image,
                    'shape': image.shape,
                    'num_slices': 1,
                    'is_3d': False
                }
        
        # Directory or glob pattern - load multiple 2D files
        elif path_obj.is_dir() or '*' in path or '?' in path:
            files = []
            
            if path_obj.is_dir():
                # Directory - find all image files
                for ext in ['*.tif', '*.tiff', '*.png', '*.jpg', '*.jpeg']:
                    files.extend(glob.glob(os.path.join(path, ext)))
                    files.extend(glob.glob(os.path.join(path, ext.upper())))
            else:
                # Glob pattern
                files = glob.glob(path)
            
            if not files:
                raise ValueError(f"No image files found at: {path}")
            
            files = sorted(files)
            
            # Load all files into a 3D volume
            slices = []
            for file_path in files:
                img = load_image_file(file_path)
                img = ensure_grayscale_2d(img)
                slices.append(img)
            
            # Stack into 3D volume
            volume = np.stack(slices, axis=0)
            
            return {
                'volume': volume,
                'shape': volume.shape,
                'num_slices': volume.shape[0],
                'is_3d': True
            }
        
        else:
            raise ValueError(f"Invalid path: {path}")
