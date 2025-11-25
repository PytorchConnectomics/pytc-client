import h5py
import tifffile
import sys
import os
import numpy as np

def convert(h5_path, tiff_path):
    print(f"Converting {h5_path} to {tiff_path}...")
    try:
        with h5py.File(h5_path, 'r') as f:
            # Assuming 'main' key based on previous inspection
            data = f['main'][:]
            
            # Ensure data is in a format tifffile can handle (e.g., numpy array)
            # If it's 3D, tifffile handles it as a stack
            
            # Normalize if needed or just save raw
            tifffile.imwrite(tiff_path, data)
            print(f"Successfully saved {tiff_path}")
    except Exception as e:
        print(f"Error converting {h5_path}: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python h5_to_tiff.py <input_h5> <output_tiff>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    convert(input_file, output_file)
