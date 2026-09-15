#!/usr/bin/env python3
"""Create a NucMM demonstration project once, without resetting existing work."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, default=ROOT / 'uploads/NucMM/image.tif')
    parser.add_argument('--labels', type=Path, default=ROOT / 'uploads/NucMM/labels.tif')
    args = parser.parse_args()
    import os
    os.chdir(ROOT)
    import numpy as np
    import tifffile
    import yaml
    from server_api.auth import database, models
    from server_api.auth.utils import get_password_hash
    from server_api.workflows.db_models import WorkflowSession
    from server_api.workflows.service import create_workflow_session, update_workflow_fields

    database.init_db()
    with database.SessionLocal() as db:
        guest = db.query(models.User).filter_by(username='guest').first()
        if not guest:
            guest = models.User(username='guest', hashed_password=get_password_hash('guest'))
            db.add(guest)
            db.commit()
            db.refresh(guest)
        existing = db.query(WorkflowSession).filter_by(user_id=guest.id).first()
        if existing:
            print(f'Existing project {existing.id} retained; no data reset.')
            return
        image, labels = args.image.resolve(), args.labels.resolve()
        if not image.is_file() or not labels.is_file():
            raise SystemExit('Provide the NucMM image and label TIFFs with --image and --labels.')
        raw, mask = tifffile.imread(image), tifffile.imread(labels)
        if raw.ndim != 3 or raw.shape != mask.shape:
            raise SystemExit('Expected image and label TIFFs with the same 3D shape.')
        ids = np.unique(mask)
        count = int(np.count_nonzero(ids))
        config = yaml.safe_load((ROOT / 'demo_configs/NucMM-CPU-demo.yaml').read_text())
        output = image.parent / 'runs' / 'cpu-training'
        config['DATASET'].update(IMAGE_NAME=str(image), LABEL_NAME=str(labels), OUTPUT_PATH=str(output))
        config['INFERENCE'].update(IMAGE_NAME=str(image), OUTPUT_PATH=str(image.parent / 'runs' / 'cpu-inference'))
        config_text = yaml.safe_dump(config, sort_keys=False)
        workflow = create_workflow_session(db, user_id=guest.id, title='NucMM dummy project')
        update_workflow_fields(db, workflow, {
            'dataset_path': str(image.parent), 'image_path': str(image),
            'label_path': str(labels), 'mask_path': str(labels), 'stage': 'proofreading',
            'config_path': 'demo_configs/NucMM-CPU-demo.yaml',
            'training_output_path': str(output),
            'metadata': {
                'created_from': 'agent_demo_seed',
                'training_config': config_text,
                'inference_config': config_text,
                'training_config_origin': 'demo_configs/NucMM-CPU-demo.yaml',
                'inference_config_origin': 'demo_configs/NucMM-CPU-demo.yaml',
                'project_context': {'imaging_modality': 'micro-CT', 'target_structure': 'nuclei',
                                    'task_goal': 'instance segmentation', 'voxel_size_nm': [720,720,720]},
                'visualization_scales': [720,720,720],
                'demo': {'shape_zyx': list(raw.shape), 'instance_count': count,
                         'labels': 'published NucMM labels; no scientific review claimed'}
            }
        })
        print(json.dumps({'workflow_id': workflow.id, 'shape_zyx': list(raw.shape), 'instances': count}))


if __name__ == '__main__':
    main()
