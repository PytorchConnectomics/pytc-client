"""
Utility functions for EHTool
Adapted from original EHTool for FastAPI integration
"""
import os
import base64
import io
import numpy as np
from PIL import Image
import tifffile
import cv2
from typing import Optional, Tuple


def to_uint8(arr: np.ndarray) -> np.ndarray:
    """Convert array to uint8 format"""
    if arr.dtype == np.uint8:
        return arr
    
    # Normalize to 0-255 range
    if arr.max() > 0:
        arr_normalized = (arr.astype(np.float32) / arr.max() * 255.0)
    else:
        arr_normalized = arr.astype(np.float32)
    
    return np.clip(arr_normalized, 0, 255).astype(np.uint8)


def ensure_grayscale_2d(arr: np.ndarray) -> np.ndarray:
    """Ensure an array is 2D grayscale"""
    if arr.ndim == 2:
        return arr
    
    if arr.ndim == 3:
        if arr.shape[2] == 1:
            return arr[:, :, 0]
        # Convert RGB to grayscale
        return np.mean(arr[:, :, :3], axis=2).astype(arr.dtype)
    
    raise ValueError(f"Unsupported array dimensions: {arr.ndim}")


def enhance_contrast(arr: np.ndarray) -> np.ndarray:
    """
    Apply CLAHE contrast enhancement for better visibility
    """
    if arr.ndim != 2:
        return arr
    
    # Ensure uint8
    arr_uint8 = to_uint8(arr)
    
    # Apply CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(arr_uint8)


def array_to_base64(arr: np.ndarray, format: str = 'PNG') -> str:
    """
    Convert numpy array to base64-encoded image string
    
    Args:
        arr: Image array
        format: Image format ('PNG', 'JPEG', etc.)
    
    Returns:
        Base64-encoded string
    """
    # Ensure uint8
    arr_uint8 = to_uint8(arr)
    
    # Convert to PIL Image
    if arr_uint8.ndim == 2:
        # Grayscale
        img = Image.fromarray(arr_uint8, mode='L')
    elif arr_uint8.ndim == 3:
        # RGB or RGBA
        if arr_uint8.shape[2] == 3:
            img = Image.fromarray(arr_uint8, mode='RGB')
        elif arr_uint8.shape[2] == 4:
            img = Image.fromarray(arr_uint8, mode='RGBA')
        else:
            raise ValueError(f"Unsupported number of channels: {arr_uint8.shape[2]}")
    else:
        raise ValueError(f"Unsupported array dimensions: {arr_uint8.ndim}")
    
    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format=format)
    buffer.seek(0)
    img_bytes = buffer.read()
    img_base64 = base64.b64encode(img_bytes).decode('utf-8')
    
    return f"data:image/{format.lower()};base64,{img_base64}"


def base64_to_array(base64_str: str) -> np.ndarray:
    """
    Convert base64-encoded image string to numpy array
    
    Args:
        base64_str: Base64-encoded image string (with or without data URI prefix)
    
    Returns:
        Numpy array
    """
    # Remove data URI prefix if present
    if ',' in base64_str:
        base64_str = base64_str.split(',', 1)[1]
    
    # Decode base64
    img_bytes = base64.b64decode(base64_str)
    
    # Convert to PIL Image
    img = Image.open(io.BytesIO(img_bytes))
    
    # Convert to numpy array
    return np.array(img)


def load_image_file(file_path: str) -> np.ndarray:
    """
    Load image from file path
    
    Args:
        file_path: Path to image file
    
    Returns:
        Numpy array
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Image file not found: {file_path}")
    
    ext = os.path.splitext(file_path.lower())[1]
    
    if ext in ['.tif', '.tiff']:
        # Load TIFF
        arr = tifffile.imread(file_path)
    else:
        # Load with PIL
        img = Image.open(file_path)
        arr = np.array(img)
    
    return arr


def get_image_dimensions(file_path: str) -> Tuple[int, ...]:
    """
    Get dimensions of an image file without loading full data
    
    Args:
        file_path: Path to image file
    
    Returns:
        Tuple of dimensions (height, width) or (depth, height, width)
    """
    ext = os.path.splitext(file_path.lower())[1]
    
    if ext in ['.tif', '.tiff']:
        with tifffile.TiffFile(file_path) as tif:
            # Get shape from first page
            page = tif.pages[0]
            if len(tif.pages) > 1:
                # Multi-page TIFF (3D stack)
                return (len(tif.pages), page.shape[0], page.shape[1])
            else:
                # Single page
                return page.shape
    else:
        # Use PIL for other formats
        with Image.open(file_path) as img:
            width, height = img.size
            return (height, width)
