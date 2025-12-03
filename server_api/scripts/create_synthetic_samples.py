"""
Create synthetic sample TIFF files for Neuroglancer demonstration.
These are placeholders until real Lucchi dataset files are downloaded.

The Lucchi dataset specifications:
- Image dimensions: typically 165 x 1024 x 768 (z, y, x)
- Resolution: 5nm per voxel
- Type: EM (electron microscopy) grayscale images
"""

import numpy as np
from PIL import Image
import os

def create_synthetic_volume(output_path, shape=(165, 1024, 768), is_label=False):
    """
    Create a synthetic 3D volume and save as multi-page TIFF
    
    Args:
        output_path: Path to save the TIFF file
        shape: (z, y, x) dimensions
        is_label: If True, create segmentation labels; if False, create grayscale image
    """
    print(f"Creating synthetic volume: {output_path}")
    print(f"Dimensions (z,y,x): {shape}")
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    if is_label:
        # Create synthetic segmentation labels
        # Simulate mitochondria as random ellipsoids
        volume = np.zeros(shape, dtype=np.uint8)
        
        # Add some random "mitochondria" labels
        num_mitochondria = 50
        for i in range(1, num_mitochondria + 1):
            # Random center
            z_center = np.random.randint(10, shape[0] - 10)
            y_center = np.random.randint(100, shape[1] - 100)
            x_center = np.random.randint(100, shape[2] - 100)
            
            # Random size
            z_radius = np.random.randint(3, 8)
            y_radius = np.random.randint(20, 50)
            x_radius = np.random.randint(20, 50)
            
            # Create ellipsoid
            for z in range(max(0, z_center - z_radius), min(shape[0], z_center + z_radius)):
                for y in range(max(0, y_center - y_radius), min(shape[1], y_center + y_radius)):
                    for x in range(max(0, x_center - x_radius), min(shape[2], x_center + x_radius)):
                        # Ellipsoid equation
                        if ((z - z_center)**2 / z_radius**2 + 
                            (y - y_center)**2 / y_radius**2 + 
                            (x - x_center)**2 / x_radius**2) <= 1:
                            volume[z, y, x] = i  # Label ID
        
        print(f"Created {num_mitochondria} synthetic mitochondria")
    else:
        # Create synthetic grayscale EM-like image
        # Use Perlin-like noise for realistic texture
        volume = np.random.randint(50, 200, shape, dtype=np.uint8)
        
        # Add some structure (simulate cell membranes)
        for _ in range(20):
            z = np.random.randint(0, shape[0])
            y_start = np.random.randint(0, shape[1] - 100)
            x_start = np.random.randint(0, shape[2] - 100)
            
            # Draw a "membrane" line
            for i in range(100):
                y = min(y_start + i, shape[1] - 1)
                x = min(x_start + i + np.random.randint(-5, 5), shape[2] - 1)
                volume[z, y, x] = 30  # Dark line
    
    # Save as multi-page TIFF
    images = [Image.fromarray(volume[i]) for i in range(shape[0])]
    images[0].save(
        output_path,
        save_all=True,
        append_images=images[1:],
        compression='tiff_deflate'
    )
    
    print(f"Saved to: {output_path}")
    print(f"File size: {os.path.getsize(output_path) / (1024*1024):.2f} MB\n")

if __name__ == "__main__":
    # Create samples_pytc directory
    os.makedirs("samples_pytc", exist_ok=True)
    
    print("="*60)
    print("Creating Synthetic Lucchi-like Dataset")
    print("="*60)
    print("\nNOTE: These are SYNTHETIC placeholder files.")
    print("For real data, download from:")
    print("  https://www.epfl.ch/labs/cvlab/data/data-em/")
    print("  or search for 'Lucchi mitochondria dataset'\n")
    print("="*60)
    print()
    
    # Create synthetic image (smaller for demo - 50 slices instead of 165)
    create_synthetic_volume(
        "samples_pytc/lucchiIm.tif",
        shape=(50, 512, 512),  # Smaller for faster loading
        is_label=False
    )
    
    # Create synthetic labels
    create_synthetic_volume(
        "samples_pytc/lucchiLabels.tif",
        shape=(50, 512, 512),
        is_label=True
    )
    
    print("="*60)
    print("✅ Synthetic sample files created successfully!")
    print("="*60)
    print("\nFiles created:")
    print("  - samples_pytc/lucchiIm.tif (grayscale EM-like image)")
    print("  - samples_pytc/lucchiLabels.tif (mitochondria segmentation)")
    print("\nThese files are ready to use with Neuroglancer!")
    print("="*60)
