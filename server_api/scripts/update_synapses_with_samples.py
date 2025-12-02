"""
Update mock synapse data to use realistic positions based on Lucchi sample dimensions.
Also update the project to link to the sample image files.

Sample dimensions: 50 x 512 x 512 (z, y, x)
Resolution: 5nm per voxel
"""
import sqlite3
import random
import os
from datetime import datetime

# Connect to database
conn = sqlite3.connect('sql_app.db')
cursor = conn.cursor()

print("Updating database with Lucchi sample integration...")

# Get absolute paths to sample files
base_dir = os.path.abspath('.')
image_path = os.path.join(base_dir, 'samples_pytc', 'lucchiIm.tif')
label_path = os.path.join(base_dir, 'samples_pytc', 'lucchiLabels.tif')

print(f"\nImage path: {image_path}")
print(f"Label path: {label_path}")

# Check if files exist
if not os.path.exists(image_path):
    print(f"WARNING: Image file not found: {image_path}")
    print("Run: python server_api/scripts/create_synthetic_samples.py")
else:
    print(f"✓ Image file exists ({os.path.getsize(image_path) / (1024*1024):.2f} MB)")

if not os.path.exists(label_path):
    print(f"WARNING: Label file not found: {label_path}")
else:
    print(f"✓ Label file exists ({os.path.getsize(label_path) / (1024*1024):.2f} MB)")

# Update project table to include image and label paths
cursor.execute('''
ALTER TABLE projects ADD COLUMN image_path TEXT
''')
cursor.execute('''
ALTER TABLE projects ADD COLUMN label_path TEXT
''')

print("\n✓ Added image_path and label_path columns to projects table")

# Update the mock project with file paths
cursor.execute('''
UPDATE projects 
SET image_path = ?, label_path = ?
WHERE name = 'Mock Synapse Project'
''', (image_path, label_path))

print("✓ Updated Mock Synapse Project with sample file paths")

# Delete existing synapses
cursor.execute("DELETE FROM synapses WHERE project_id = 1")
print("\n✓ Deleted old synapse data")

# Image dimensions (z, y, x) in voxels
z_max, y_max, x_max = 50, 512, 512
resolution_nm = 5  # 5nm per voxel

# Convert to nm for synapse positions
z_max_nm = z_max * resolution_nm
y_max_nm = y_max * resolution_nm  
x_max_nm = x_max * resolution_nm

print(f"\nImage dimensions:")
print(f"  Voxels: {z_max} x {y_max} x {x_max}")
print(f"  Physical size: {z_max_nm}nm x {y_max_nm}nm x {x_max_nm}nm")
print(f"  ({z_max_nm/1000:.1f}µm x {y_max_nm/1000:.1f}µm x {x_max_nm/1000:.1f}µm)")

# Create 100 new synapses with realistic positions
print(f"\nGenerating 100 synapses within image bounds...")

# Distribution: 80 errors, 15 correct, 5 incorrect
statuses = ['error'] * 80 + ['correct'] * 15 + ['incorrect'] * 5
random.shuffle(statuses)

for i in range(100):
    # Random coordinates within image bounds (in nm)
    x = random.uniform(0, x_max_nm)
    y = random.uniform(0, y_max_nm)
    z = random.uniform(0, z_max_nm)
    
    # Random neuron IDs (some may be None for errors)
    if statuses[i] == 'error':
        pre_id = random.randint(1, 50) if random.random() > 0.3 else None
        post_id = random.randint(1, 50) if random.random() > 0.3 else None
    else:
        pre_id = random.randint(1, 50)
        post_id = random.randint(1, 50)
    
    confidence = random.uniform(0.6, 0.95)
    
    cursor.execute('''
    INSERT INTO synapses (
        project_id, pre_neuron_id, post_neuron_id,
        x, y, z, status, confidence
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        1,  # project_id
        pre_id,
        post_id,
        x, y, z,
        statuses[i],
        confidence
    ))

conn.commit()

print(f"✓ Created 100 synapses")
print(f"  - Errors (need review): 80")
print(f"  - Correct: 15")
print(f"  - Incorrect: 5")

# Show sample data
print("\nSample synapses:")
cursor.execute('''
SELECT id, x, y, z, status, pre_neuron_id, post_neuron_id 
FROM synapses 
WHERE project_id = 1 
LIMIT 5
''')

for row in cursor.fetchall():
    print(f"  ID {row[0]}: ({row[1]:.1f}, {row[2]:.1f}, {row[3]:.1f})nm - Status: {row[4]}, Pre: {row[5]}, Post: {row[6]}")

conn.close()

print("\n" + "="*60)
print("Database updated successfully!")
print("="*60)
print("\nNext steps:")
print("1. Restart the backend server")
print("2. Navigate to Proof Reading tab")
print("3. Neuroglancer will load with the sample data!")
print("="*60)
