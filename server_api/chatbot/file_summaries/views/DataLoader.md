# DataLoader View

## Overview
The DataLoader view provides an interface for loading and visualizing biomedical image data using Neuroglancer. It allows users to upload files, select images and labels, and generate interactive 3D visualizations.

## Functionality
- **File Upload**: Drag-and-drop interface for uploading image files
- **File Selection**: Choose specific images and labels for visualization
- **Scale Configuration**: Set voxel scales for proper 3D rendering
- **Neuroglancer Integration**: Generate interactive 3D visualizations
- **File Management**: Organize and categorize uploaded files

## Key Features
- **Drag & Drop Upload**: Intuitive file upload interface
- **File Categorization**: Separate handling for images and labels
- **Scale Input**: Configure voxel dimensions for 3D rendering
- **Visualization Button**: Generate Neuroglancer visualizations
- **File Organization**: Clear separation of images and labels

## User Interface
- **Upload Area**: Large drop zone for file uploads
- **File Selectors**: Dropdown menus for choosing images and labels
- **Scale Input**: Text field for entering voxel scales
- **Visualize Button**: Generate 3D visualization
- **File Lists**: Organized display of uploaded files

## File Management
- **Image Files**: Separate list for image files
- **Label Files**: Separate list for label/annotation files
- **File Metadata**: Track file names, paths, and properties
- **File Validation**: Ensure proper file formats and structure

## Scale Configuration
- **Voxel Scales**: Set dimensions for 3D rendering (z, y, x order)
- **Default Values**: Pre-configured scale values
- **Custom Input**: User-defined scale values
- **Validation**: Ensure valid scale values

## Neuroglancer Integration
- **3D Visualization**: Interactive 3D rendering of biomedical data
- **Multi-layer Support**: Display both images and labels
- **Scale-aware Rendering**: Proper 3D scaling based on voxel dimensions
- **Interactive Controls**: Zoom, pan, and rotate in 3D space

## Props
- `fetchNeuroglancerViewer`: Function to generate Neuroglancer visualizations

## State Management
- `currentImage`: Currently selected image file
- `currentLabel`: Currently selected label file
- `scales`: Voxel scale configuration
- Uses global context for file management

## User Workflow
1. **File Upload**: Drag and drop files or click to browse
2. **File Categorization**: Specify whether files are images or labels
3. **File Selection**: Choose specific images and labels from dropdowns
4. **Scale Configuration**: Enter voxel scales for 3D rendering
5. **Visualization**: Click visualize button to generate 3D view

## Integration Points
- **Global Context**: Accesses file lists and metadata
- **Dragger Component**: Handles file upload functionality
- **Neuroglancer API**: Generates 3D visualizations
- **File System**: Manages local file operations

## Error Handling
- **File Validation**: Ensures proper file formats
- **Path Validation**: Checks file paths and accessibility
- **Scale Validation**: Validates voxel scale values
- **User Feedback**: Clear error messages and guidance

## Use Cases
- **Data Exploration**: Visualize biomedical image data
- **Quality Control**: Check data quality before processing
- **Annotation Review**: Examine labels and annotations
- **3D Analysis**: Analyze 3D structure of biomedical data

## Technical Implementation
- **File Processing**: Handles various image formats
- **3D Rendering**: Integrates with Neuroglancer for visualization
- **State Management**: Maintains file and configuration state
- **API Integration**: Communicates with backend services
