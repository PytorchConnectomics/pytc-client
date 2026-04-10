import json
import os
import sys

# Paths
DEFAULT_JSON = "/home/sam/Workshop/pytc-client/server_api/data_store/project_manager_data.json"
EXTERNAL_JSON = os.environ.get("PROJECT_METADATA_JSON")

if not EXTERNAL_JSON:
    print("Error: PROJECT_METADATA_JSON environment variable not set.")
    sys.exit(1)

if not os.path.exists(EXTERNAL_JSON):
    print(f"Error: External file not found at {EXTERNAL_JSON}")
    sys.exit(1)

print(f"Reading default data from {DEFAULT_JSON}...")
with open(DEFAULT_JSON, 'r') as f:
    default_data = json.load(f)

print(f"Reading current external data from {EXTERNAL_JSON}...")
with open(EXTERNAL_JSON, 'r') as f:
    external_data = json.load(f)

# Keys to migrate from default if missing in external
KEYS_TO_MIGRATE = [
    "quota_data", 
    "proofreader_data", 
    "throughput_data", 
    "datasets", 
    "milestones", 
    "cumulative_data", 
    "cumulative_target", 
    "at_risk", 
    "upcoming_milestones", 
    "msg_preview", 
    "workers",
    "users"
]

migrated_count = 0
for key in KEYS_TO_MIGRATE:
    if key not in external_data or not external_data[key]:
        if key in default_data:
            print(f"Migrating missing key: {key}")
            external_data[key] = default_data[key]
            migrated_count += 1
        else:
            print(f"Warning: Key '{key}' not found in default data.")

if migrated_count > 0:
    print(f"Writing {migrated_count} new keys to {EXTERNAL_JSON}...")
    with open(EXTERNAL_JSON, 'w') as f:
        json.dump(external_data, f, indent=2)
    print("Initialization complete.")
else:
    print("External file already contains all necessary keys. No changes made.")
