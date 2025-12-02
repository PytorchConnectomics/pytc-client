from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from auth import models, database
from auth.router import get_current_user

router = APIRouter()

@router.get("/api/synanno/ng-url/{project_id}")
def get_neuroglancer_url(
    project_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Get Neuroglancer URL for a project by generating a viewer from its image files
    
    Args:
        project_id: ID of the project
        current_user: Authenticated user
        db: Database session
        
    Returns:
        Dictionary with 'url' key containing the Neuroglancer URL
    """
    import httpx
    import os
    
    # Get project with image paths
    project = db.query(models.Project).filter(
        models.Project.id == project_id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if project has image files
    image_path = getattr(project, 'image_path', None)
    label_path = getattr(project, 'label_path', None)
    
    if not image_path or not os.path.exists(image_path):
        # Fallback: return a placeholder message
        return {"url": None, "message": "No image file associated with this project"}
    
    # Generate Neuroglancer web client URL
    try:
        import json
        import urllib.parse
        
        # We assume the NIfTI files are/will be generated in the samples directory
        # and served by the static file server at localhost:8000
        
        # Base URL for the official Neuroglancer web client
        # We can use the demo instance or a specific deployment
        ng_base_url = "https://neuroglancer-demo.appspot.com/"
        
        # Construct the state
        # Note: NIfTI files need to be served with CORS enabled
        ng_state = {
            "dimensions": {
                "x": [5e-9, "m"],
                "y": [5e-9, "m"],
                "z": [5e-9, "m"]
            },
            "position": [256, 256, 25], # Default center
            "crossSectionScale": 1,
            "projectionScale": 256,
            "layers": [
                {
                    "type": "image",
                    "source": "nifti://http://localhost:8000/lucchiIm.nii.gz",
                    "name": "EM Image",
                    "visible": True
                },
                {
                    "type": "segmentation",
                    "source": "nifti://http://localhost:8000/lucchiLabels.nii.gz",
                    "name": "Mitochondria",
                    "visible": True
                }
            ],
            "layout": "4panel"
        }
        
        # Encode state in URL fragment
        # Neuroglancer uses a specific URL encoding for the state
        # Simple JSON stringification usually works for the fragment
        json_state = json.dumps(ng_state)
        # We need to URL encode it? Usually the browser handles it, but let's be safe
        # Actually, Neuroglancer expects the JSON directly in the fragment often, 
        # or encoded. Let's send the raw JSON state to the frontend, 
        # and let the frontend construct the final URL or use an iframe with this src.
        
        # But wait, our frontend expects a "url" field.
        # Let's construct the full URL.
        # The format is https://site/#!{json_state}
        viewer_url = f"{ng_base_url}#!{json_state}"
        
        return {
            "url": viewer_url,
            "message": "Viewer ready (requires NIfTI files)"
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error preparing Neuroglancer URL: {str(e)}"
        )

@router.get("/api/projects/{id}/synapses", response_model=List[models.SynapseResponse])
def get_synapses(
    id: int,
    status: Optional[str] = Query(None, description="Filter by status: error, correct, incorrect, unsure"),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Get synapses for a project, optionally filtered by status
    
    Args:
        id: Project ID
        status: Optional status filter
        current_user: Authenticated user
        db: Database session
        
    Returns:
        List of synapses
    """
    # Verify project exists
    project = db.query(models.Project).filter(models.Project.id == id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    query = db.query(models.Synapse).filter(models.Synapse.project_id == id)
    
    if status:
        query = query.filter(models.Synapse.status == status)
    
    synapses = query.all()
    return synapses

@router.put("/api/synapses/{id}", response_model=models.SynapseResponse)
def update_synapse(
    id: int,
    synapse_update: models.SynapseUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Update a synapse's status and/or neuron IDs
    
    Args:
        id: Synapse ID
        synapse_update: Update data
        current_user: Authenticated user
        db: Database session
        
    Returns:
        Updated synapse
    """
    synapse = db.query(models.Synapse).filter(models.Synapse.id == id).first()
    
    if not synapse:
        raise HTTPException(status_code=404, detail="Synapse not found")
    
    # Update fields if provided
    if synapse_update.status is not None:
        synapse.status = synapse_update.status
    if synapse_update.pre_neuron_id is not None:
        synapse.pre_neuron_id = synapse_update.pre_neuron_id
    if synapse_update.post_neuron_id is not None:
        synapse.post_neuron_id = synapse_update.post_neuron_id
    
    # Track who reviewed and when
    synapse.reviewed_by = current_user.id
    synapse.reviewed_at = datetime.utcnow()
    
    db.commit()
    db.refresh(synapse)
    return synapse

@router.get("/api/projects", response_model=List[models.ProjectResponse])
def get_projects(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Get all projects
    
    Args:
        current_user: Authenticated user
        db: Database session
        
    Returns:
        List of projects
    """
    projects = db.query(models.Project).all()
    return projects
