import neuroglancer
import numpy as np
import sys

# Configure server - use port 9000 to avoid conflict with PyTC server on 8080
neuroglancer.set_server_bind_address('127.0.0.1', 9000)

# Create viewer
viewer = neuroglancer.Viewer()

# Create mock 3D volume (100x100x100 voxels)
print("Generating mock volume data...", flush=True)
volume = np.random.randint(0, 255, (100, 100, 100), dtype=np.uint8)

# Add image layer
with viewer.txn() as s:
    s.layers['image'] = neuroglancer.ImageLayer(
        source=neuroglancer.LocalVolume(
            data=volume,
            dimensions=neuroglancer.CoordinateSpace(
                names=['x', 'y', 'z'],
                units=['nm', 'nm', 'nm'],
                scales=[10, 10, 10]
            )
        )
    )

viewer_url = str(viewer)

print(f"\n{'='*60}", flush=True)
print(f"Neuroglancer is running!", flush=True)
print(f"{'='*60}", flush=True)
print(f"URL: {viewer_url}", flush=True)
print(f"\nThis URL will be used by the Proof Reading tab.", flush=True)
print(f"Keep this script running while using the application.", flush=True)
print(f"\nPress Ctrl+C to stop the server", flush=True)
print(f"{'='*60}\n", flush=True)

# Save URL to file for the backend to read
with open('neuroglancer_url.txt', 'w') as f:
    f.write(viewer_url)

# Keep server running
try:
    import time
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nShutting down Neuroglancer server...", flush=True)
