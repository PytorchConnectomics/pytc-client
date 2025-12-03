"""
Create mock synapse data for testing the Proof Reading tab
"""
import sqlite3
import random
from datetime import datetime

# Connect to database
conn = sqlite3.connect('sql_app.db')
cursor = conn.cursor()

print("Creating database tables...")

# Create projects table
cursor.execute('''
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    user_id INTEGER,
    neuroglancer_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

# Create synapses table
cursor.execute('''
CREATE TABLE IF NOT EXISTS synapses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    pre_neuron_id INTEGER,
    post_neuron_id INTEGER,
    x REAL NOT NULL,
    y REAL NOT NULL,
    z REAL NOT NULL,
    status TEXT DEFAULT 'error',
    confidence REAL,
    reviewed_by INTEGER,
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id)
)
''')

print("Tables created successfully!")

# Check if mock project already exists
cursor.execute("SELECT id FROM projects WHERE name = 'Mock Synapse Project'")
existing_project = cursor.fetchone()

if existing_project:
    project_id = existing_project[0]
    print(f"\nMock project already exists with ID {project_id}")
    
    # Ask if user wants to recreate data
    response = input("Do you want to recreate the synapse data? (y/n): ")
    if response.lower() == 'y':
        cursor.execute("DELETE FROM synapses WHERE project_id = ?", (project_id,))
        print("Deleted existing synapses")
    else:
        print("Keeping existing data")
        conn.close()
        exit(0)
else:
    # Create mock project
    print("\nCreating mock project...")
    cursor.execute('''
    INSERT INTO projects (name, user_id, neuroglancer_url)
    VALUES (?, ?, ?)
    ''', ('Mock Synapse Project', 1, 'http://localhost:8080'))
    
    project_id = cursor.lastrowid
    print(f"Created project with ID {project_id}")

# Create 100 mock synapses
print(f"\nGenerating 100 mock synapses...")

# Distribution: 80 errors, 15 correct, 5 incorrect
statuses = ['error'] * 80 + ['correct'] * 15 + ['incorrect'] * 5
random.shuffle(statuses)

for i in range(100):
    # Random coordinates within 100x100x100 volume
    x = random.uniform(0, 100)
    y = random.uniform(0, 100)
    z = random.uniform(0, 100)
    
    # Random neuron IDs (some may be None for errors)
    if statuses[i] == 'error':
        # Errors may have missing or incorrect neuron IDs
        pre_id = random.randint(1, 50) if random.random() > 0.3 else None
        post_id = random.randint(1, 50) if random.random() > 0.3 else None
    else:
        pre_id = random.randint(1, 50)
        post_id = random.randint(1, 50)
    
    confidence = random.uniform(0.5, 0.99)
    
    cursor.execute('''
    INSERT INTO synapses (
        project_id, pre_neuron_id, post_neuron_id,
        x, y, z, status, confidence
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        project_id,
        pre_id,
        post_id,
        x, y, z,
        statuses[i],
        confidence
    ))

conn.commit()

# Print summary
print(f"\n{'='*60}")
print("Mock data created successfully!")
print(f"{'='*60}")
print(f"Project ID: {project_id}")
print(f"Project Name: Mock Synapse Project")
print(f"Total Synapses: 100")
print(f"  - Errors (need review): 80")
print(f"  - Correct: 15")
print(f"  - Incorrect: 5")
print(f"{'='*60}\n")

# Show sample data
print("Sample synapses:")
cursor.execute('''
SELECT id, x, y, z, status, pre_neuron_id, post_neuron_id 
FROM synapses 
WHERE project_id = ? 
LIMIT 5
''', (project_id,))

for row in cursor.fetchall():
    print(f"  ID {row[0]}: ({row[1]:.1f}, {row[2]:.1f}, {row[3]:.1f}) - Status: {row[4]}, Pre: {row[5]}, Post: {row[6]}")

conn.close()
print("\nDatabase connection closed.")
print("You can now start the backend server and use the Proof Reading tab!")
