# GlobalContext Provider

## Overview
The GlobalContext provider manages the global application state for the PyTorch Connectomics client. It provides centralized state management for files, configurations, and application data across all components.

## Functionality
- **File Management**: Centralized management of uploaded files and metadata
- **Configuration State**: Manages training and inference configurations
- **Path Management**: Tracks input/output paths and file locations
- **Viewer State**: Manages Neuroglancer viewers and visualizations
- **Data Persistence**: Automatic saving and loading of application state

## Key Features
- **Persistent Storage**: Uses localforage for reliable data persistence
- **State Synchronization**: Automatic state updates across components
- **File Organization**: Separate management of images and labels
- **Configuration Management**: Centralized configuration state
- **Error Handling**: Robust error handling for storage operations

## State Management
- **Files**: Array of uploaded files with metadata
- **File Lists**: Organized lists of images and labels
- **Configurations**: Training and inference configuration data
- **Paths**: Input/output paths and file locations
- **Viewers**: Neuroglancer viewer state and metadata

## File Management
- **File Storage**: Maintains array of uploaded files
- **File Categorization**: Separates images and labels
- **File Metadata**: Tracks file names, paths, and properties
- **File Operations**: Add, remove, and update file information

## Configuration Management
- **Training Config**: YAML configuration for model training
- **Inference Config**: YAML configuration for model inference
- **Parameter State**: Tracks configuration parameters
- **Validation**: Ensures configuration validity

## Path Management
- **Input Paths**: Tracks input data locations
- **Output Paths**: Manages output directory locations
- **Log Paths**: Tracks training log locations
- **Checkpoint Paths**: Manages model checkpoint locations

## Viewer Management
- **Current Image**: Currently selected image for visualization
- **Current Label**: Currently selected label for visualization
- **Viewer State**: Manages Neuroglancer viewer instances
- **Visualization Data**: Tracks visualization parameters

## Data Persistence
- **Local Storage**: Uses localforage for reliable storage
- **Automatic Saving**: Saves state changes automatically
- **Data Recovery**: Loads saved state on application startup
- **Error Handling**: Graceful handling of storage errors

## Context Provider
- **AppContext**: Main context for global state
- **ContextWrapper**: Provider component for state management
- **State Access**: Provides state to child components
- **State Updates**: Handles state changes and updates

## Custom Hooks
- **usePersistedState**: Custom hook for persistent state management
- **State Synchronization**: Automatic state updates
- **Error Recovery**: Handles storage errors gracefully
- **Performance**: Optimized state management

## Integration Points
- **Components**: Provides state to all application components
- **File System**: Integrates with local file system
- **Storage**: Uses localforage for data persistence
- **API**: Connects to backend services

## Error Handling
- **Storage Errors**: Graceful handling of storage failures
- **State Recovery**: Automatic recovery from storage errors
- **User Feedback**: Clear error messages and guidance
- **Fallback**: Default values for failed operations

## Use Cases
- **Application State**: Centralized state management
- **Data Persistence**: Reliable data storage and recovery
- **Component Communication**: Shared state between components
- **Configuration Management**: Centralized configuration handling

## Technical Implementation
- **React Context**: Uses React Context API for state management
- **Local Storage**: Integrates with localforage for persistence
- **State Updates**: Efficient state update mechanisms
- **Performance**: Optimized for large datasets

## Advanced Features
- **State Validation**: Ensures state consistency
- **Performance Optimization**: Efficient state updates
- **Memory Management**: Proper cleanup and memory usage
- **Scalability**: Handles large amounts of data efficiently
