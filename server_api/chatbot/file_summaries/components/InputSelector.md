# InputSelector Component

## Overview
The InputSelector component provides a form interface for selecting input files and configuring paths for model training and inference workflows. It allows users to specify which files to use and where to save outputs.

## Functionality
- **File Selection**: Choose input images and labels from uploaded files
- **Path Configuration**: Set output paths for training and inference
- **Type-specific Fields**: Different fields for training vs inference workflows
- **Form Validation**: Ensures required fields are completed
- **Context Integration**: Updates global application state

## Key Features
- **Dropdown Selection**: Choose from available uploaded files
- **Path Input**: Text fields for specifying file paths
- **Conditional Fields**: Different fields based on workflow type
- **Real-time Updates**: Immediate state updates on form changes
- **Validation**: Prevents submission without required inputs

## Form Fields

### Common Fields
- **Input Image**: Dropdown to select input image file
- **Input Label**: Dropdown to select input label file

### Training-specific Fields
- **Output Path**: Where to save training outputs
- **Log Path**: Where to save training logs

### Inference-specific Fields
- **Checkpoint Path**: Path to model checkpoint file

## Props
- `fileList`: Array of available files for selection
- `type`: String indicating workflow type ('training' or 'inference')

## State Management
- Uses global context to access and update application state
- Manages form field values and selections
- Updates file lists and path configurations

## User Interface
- **Form Layout**: Clean, organized form with proper spacing
- **Dropdown Menus**: Easy file selection from available options
- **Text Inputs**: Path input fields with placeholders
- **Conditional Display**: Shows relevant fields based on workflow type

## File Selection
- **Image Files**: Select from uploaded image files
- **Label Files**: Select from uploaded label files
- **Clear Selection**: Option to clear current selections
- **Validation**: Ensures valid file selections

## Path Configuration
- **Output Paths**: Specify where to save results
- **Log Paths**: Set location for training logs
- **Checkpoint Paths**: Specify model checkpoint locations
- **Path Validation**: Ensures valid path formats

## Integration Points
- **Global Context**: Accesses and updates application state
- **File Management**: Integrates with file upload system
- **Configuration**: Connects to training/inference configuration
- **Validation**: Ensures proper configuration before execution

## User Workflow
1. **File Selection**: Choose input images and labels from dropdowns
2. **Path Configuration**: Enter output and log paths
3. **Validation**: Ensure all required fields are completed
4. **Progression**: Move to next configuration step

## Error Handling
- **Required Fields**: Prevents progression without required inputs
- **Path Validation**: Ensures valid path formats
- **File Validation**: Confirms selected files exist
- **User Feedback**: Clear error messages and guidance

## Use Cases
- **Training Setup**: Configure inputs for model training
- **Inference Setup**: Set up inputs for model inference
- **Path Management**: Organize output and log locations
- **File Organization**: Select appropriate files for workflows
