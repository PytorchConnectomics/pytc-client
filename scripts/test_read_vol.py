import imageio
import sys
import numpy as np

def test_read(filename):
    print(f"Testing {filename}...")
    try:
        # Test imread
        print("  imageio.imread:")
        img = imageio.imread(filename)
        print(f"    Shape: {img.shape}, Dtype: {img.dtype}")
    except Exception as e:
        print(f"    Failed: {e}")

    try:
        # Test volread
        print("  imageio.volread:")
        vol = imageio.volread(filename)
        print(f"    Shape: {vol.shape}, Dtype: {vol.dtype}")
    except Exception as e:
        print(f"    Failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_read_vol.py <tiff_file>")
        sys.exit(1)
    
    test_read(sys.argv[1])
