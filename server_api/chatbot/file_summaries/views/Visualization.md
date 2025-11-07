# Visualization View

## Overview
The Visualization view provides an interface for displaying and managing Neuroglancer 3D visualizations of biomedical image data. It supports multiple viewer tabs and provides interactive 3D rendering capabilities.

## Functionality
- **Multi-viewer Support**: Manage multiple Neuroglancer visualizations
- **Tab Management**: Add, remove, and switch between viewers
- **3D Rendering**: Interactive 3D visualization of biomedical data
- **Viewer Controls**: Refresh, close, and manage viewers
- **User Guidance**: Step-by-step instructions for data visualization

## Key Features
- **Tabbed Interface**: Multiple viewer tabs with close functionality
- **Interactive 3D**: Full Neuroglancer functionality in embedded iframes
- **Viewer Management**: Add, remove, and refresh viewers
- **User Instructions**: Clear guidance for visualization setup
- **Responsive Design**: Adapts to different screen sizes

## Viewer Management
- **Multiple Viewers**: Support for multiple simultaneous visualizations
- **Tab Navigation**: Easy switching between different viewers
- **Viewer Controls**: Refresh and close individual viewers
- **Viewer Metadata**: Display viewer titles and information

## User Interface
- **Tabbed Display**: Clean tab interface for multiple viewers
- **Viewer Controls**: Refresh and close buttons for each viewer
- **Instruction Timeline**: Step-by-step guidance for new users
- **Responsive Layout**: Adapts to available screen space

## Props
- `viewers`: Array of active Neuroglancer viewers
- `setViewers`: Function to update viewer list

## State Management
- `activeKey`: Currently active viewer tab
- Manages viewer list and active tab state
- Handles viewer creation and removal

## User Workflow
1. **Data Upload**: Upload image and label files
2. **File Selection**: Choose specific images and labels
3. **Scale Configuration**: Set voxel scales for 3D rendering
4. **Visualization**: Generate Neuroglancer visualization
5. **Viewer Management**: Manage multiple viewers and tabs

## Viewer Operations
- **Add Viewer**: Create new Neuroglancer visualization
- **Remove Viewer**: Close and remove viewer tabs
- **Refresh Viewer**: Reload viewer with updated data
- **Switch Viewer**: Navigate between different viewers

## Integration Points
- **DataLoader**: Connects to data loading functionality
- **Neuroglancer API**: Integrates with Neuroglancer service
- **File System**: Accesses uploaded image and label files
- **Backend Services**: Communicates with visualization backend

## Error Handling
- **Viewer Errors**: Graceful handling of viewer creation failures
- **Connection Issues**: Proper error messages for connection problems
- **User Feedback**: Clear indication of viewer status
- **Recovery**: Options to retry failed operations

## Use Cases
- **Data Exploration**: Visualize biomedical image data
- **Quality Control**: Check data quality and annotations
- **3D Analysis**: Analyze 3D structure of biomedical data
- **Annotation Review**: Examine labels and segmentation results

## Technical Implementation
- **Iframe Integration**: Embedded Neuroglancer interface
- **Tab Management**: Dynamic tab creation and removal
- **State Management**: Maintains viewer state and metadata
- **API Integration**: Communicates with backend services

## Advanced Features
- **Multi-layer Support**: Display both images and labels
- **Interactive Controls**: Full Neuroglancer functionality
- **Viewer Persistence**: Maintains viewers across sessions
- **Performance Optimization**: Efficient handling of multiple viewers
