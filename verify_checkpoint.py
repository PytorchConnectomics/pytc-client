
import torch
import sys
import os

# Add the pytorch_connectomics directory to sys.path
sys.path.append("/Users/adamg/seg.bio/pytc-client/pytorch_connectomics")

# Import the config module to ensure classes are registered
import connectomics.config.hydra_config

checkpoint_path = "/Users/adamg/seg.bio/pytc-client/lucchi_test/epoch=269-step=5400.ckpt"

print(f"Attempting to load checkpoint: {checkpoint_path}")

try:
    # Try loading with map_location='cpu' and weights_only=False
    checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=False)
    print("✓ Checkpoint loaded successfully!")
    
    # Inspect keys
    print(f"Checkpoint keys: {checkpoint.keys()}")
    
    if 'hyper_parameters' in checkpoint:
        print("Hyperparameters found.")
        # print(checkpoint['hyper_parameters'])
        
except AttributeError as e:
    print(f"✗ AttributeError during loading: {e}")
    print("This usually means a class in the checkpoint is missing from the codebase.")
except Exception as e:
    print(f"✗ Error during loading: {e}")
    import traceback
    traceback.print_exc()
