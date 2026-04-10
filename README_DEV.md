# PyTC Client — Developer Guide (External Data)

This guide explains how to configure the PyTC client to work with externalized metadata and data storage.

## Environment Variables

To use external data, set the following environment variables before starting the backend:

- `PROJECT_METADATA_JSON`: Absolute path to the `project_manager_data.json` file.
- `DATA_ROOT_EM`: Root directory containing the H5 volume files.

### Example Setup (Bash)

```bash
export PROJECT_METADATA_JSON="/home/sam/Workshop/Pytc-data/im_64nm/server_api/data_store/project_manager_data.json"
export DATA_ROOT_EM="/home/sam/Workshop/Pytc-data/im_64nm/im_64nm/"

./scripts/start.sh
```

## Migration Utility (Kanchan's Logic)

To assign volumes in a specific subdirectory to a user (e.g., "kanchan"), use the provided migration script:

```bash
python3 scripts/migrate_metadata.py /path/to/project_manager_data.json --subdir "1440/"
```

This will find all volumes where `rel_path` contains "1440/" and set their assignee to "kanchan".

## Standardized Data Access

The frontend now utilizes a standardized `DataReaderService` (`client/src/services/data_reader.js`).
UI components should only reference volumes by their `taskId` (the volume ID).

### Linking Metadata Dynamically

You can also link to an external metadata file at runtime via the backend API:

```bash
curl -X POST http://localhost:4242/api/pm/data/link \
     -H "Content-Type: application/json" \
     -d '{"path": "/home/sam/Workshop/Pytc-data/im_64nm/project_manager_data_new.json"}'
```
