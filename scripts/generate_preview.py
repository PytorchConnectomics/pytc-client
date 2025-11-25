import tifffile
import numpy as np
import base64
import sys
import io
from PIL import Image

def generate_preview(tiff_path):
    try:
        # Read TIFF
        vol = tifffile.imread(tiff_path)
        
        # Handle dimensions
        if vol.ndim == 3:
            # z, y, x -> take center z
            z_center = vol.shape[0] // 2
            img = vol[z_center]
        elif vol.ndim == 2:
            img = vol
        else:
            print(f"Error: Unexpected dimensions {vol.ndim}")
            return

        # Normalize to 0-255 for display
        if img.dtype != np.uint8:
            img = img.astype(np.float32)
            img = (img - img.min()) / (img.max() - img.min()) * 255
            img = img.astype(np.uint8)

        # Convert to PIL Image
        pil_img = Image.fromarray(img)
        
        # Save to buffer as PNG
        buff = io.BytesIO()
        pil_img.save(buff, format="PNG")
        img_str = base64.b64encode(buff.getvalue()).decode("utf-8")
        
        print(f"PREVIEW_START:{tiff_path}")
        print(f"data:image/png;base64,{img_str}")
        print(f"PREVIEW_END:{tiff_path}")
        
    except Exception as e:
        print(f"Error processing {tiff_path}: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_preview.py <tiff_path1> <tiff_path2> ...")
        sys.exit(1)
    
    for path in sys.argv[1:]:
        generate_preview(path)
