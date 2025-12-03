import os
import numpy as np
import nibabel as nib
from PIL import Image
import glob

def convert_tiff_to_nifti(tiff_path, output_path, resolution=(5, 5, 5)):
    """
    Convert a multi-page TIFF or sequence of TIFFs to a NIfTI file.
    """
    print(f"Converting {tiff_path} to {output_path}...")
    
    # Check if it's a single multi-page TIFF or a pattern
    if '*' in tiff_path:
        files = sorted(glob.glob(tiff_path))
        if not files:
            print(f"No files found for pattern {tiff_path}")
            return False
        # Read first image to get dimensions
        img0 = np.array(Image.open(files[0]))
        volume = np.zeros((len(files), img0.shape[0], img0.shape[1]), dtype=img0.dtype)
        for i, f in enumerate(files):
            volume[i] = np.array(Image.open(f))
    else:
        # Multi-page TIFF
        if not os.path.exists(tiff_path):
            print(f"File not found: {tiff_path}")
            return False
            
        img = Image.open(tiff_path)
        frames = []
        try:
            while True:
                frames.append(np.array(img))
                img.seek(img.tell() + 1)
        except EOFError:
            pass
        volume = np.array(frames)

    # NIfTI expects (x, y, z) or (x, y, z, t)
    # Our volume is likely (z, y, x) from reading frames
    # Let's transpose to (x, y, z) which is standard for Neuroglancer NIfTI
    volume = np.transpose(volume, (2, 1, 0))
    
    # Create affine matrix
    # Scaling is in mm for NIfTI usually, but Neuroglancer can handle nm if specified
    # But standard NIfTI is usually mm. 5nm = 0.000005 mm
    scale = np.array(resolution) * 1e-6 # Convert nm to mm? Or just use raw units and specify in Neuroglancer
    
    # Let's use identity affine for now and specify voxel size in Neuroglancer state
    affine = np.eye(4)
    # Set voxel size in header
    
    nifti_img = nib.Nifti1Image(volume, affine)
    nifti_img.header.set_zooms(resolution) # This sets pixdim
    
    nib.save(nifti_img, output_path)
    print(f"Saved {output_path}")
    return True

if __name__ == "__main__":
    # Use current working directory to find samples
    # Assuming we run from project root
    samples_dir = os.path.join(os.getcwd(), "samples_pytc")
    
    if not os.path.exists(samples_dir):
        print(f"Samples directory not found at {samples_dir}")
        exit(1)
    img_path = os.path.join(samples_dir, "lucchiIm.tif")
    img_out = os.path.join(samples_dir, "lucchiIm.nii.gz")
    convert_tiff_to_nifti(img_path, img_out)
    
    # Convert Labels
    lbl_path = os.path.join(samples_dir, "lucchiLabels.tif")
    lbl_out = os.path.join(samples_dir, "lucchiLabels.nii.gz")
    convert_tiff_to_nifti(lbl_path, lbl_out)
