# Configurator Component

## Overview
The Configurator component provides a step-by-step wizard interface for configuring model training and inference parameters. It guides users through the process of setting up their deep learning workflows with proper validation and user-friendly controls.

## Functionality
- **Multi-step Configuration**: Breaks down complex configuration into manageable steps
- **Training/Inference Support**: Handles both training and inference configuration workflows
- **Parameter Validation**: Ensures proper configuration before proceeding
- **Progress Tracking**: Visual progress indicator with step navigation
- **Configuration Persistence**: Saves configuration data to localStorage

## Configuration Steps
1. **Set Inputs**: Select input images and labels for the workflow
2. **Base Configuration**: Upload and configure YAML configuration files
3. **Advanced Configuration**: Fine-tune parameters with sliders and text editing

## Key Features
- **Step Navigation**: Previous/Next buttons for step-by-step progression
- **Dynamic Content**: Different content based on current step
- **Validation**: Ensures required fields are completed before proceeding
- **Success Feedback**: Confirmation messages for completed configurations
- **Type-specific Logic**: Different behavior for training vs inference workflows

## Props
- `fileList`: Array of available files for selection
- `type`: String indicating configuration type ('training' or 'inference')

## State Management
- `current`: Current step index in the configuration process
- Uses global context for accessing shared application state

## Configuration Types

### Training Configuration
- **Input Selection**: Choose training images and labels
- **Output Path**: Specify where to save training outputs
- **Log Path**: Set location for training logs
- **YAML Configuration**: Upload and customize training parameters

### Inference Configuration
- **Input Selection**: Choose input images and labels
- **Checkpoint Path**: Specify model checkpoint location
- **Output Path**: Set location for inference results
- **YAML Configuration**: Upload and customize inference parameters

## User Workflow
1. **Start Configuration**: User selects training or inference mode
2. **Input Selection**: Choose appropriate files from uploaded data
3. **Base Configuration**: Upload YAML file or use default settings
4. **Advanced Configuration**: Fine-tune parameters with sliders
5. **Completion**: Save configuration and proceed to execution

## Integration Points
- **Global Context**: Accesses file lists and configuration state
- **YAML Context**: Manages YAML-specific parameters
- **Child Components**: Orchestrates InputSelector, YamlFileUploader, and YamlFileEditor
- **Local Storage**: Persists configuration data

## Error Handling
- **Validation**: Prevents progression without required inputs
- **User Feedback**: Clear error messages and guidance
- **Recovery**: Allows users to go back and fix issues

## Use Cases
- **Model Training Setup**: Configure parameters for training new models
- **Inference Configuration**: Set up model inference with proper parameters
- **Parameter Tuning**: Adjust hyperparameters for optimal performance
- **Workflow Management**: Organize and manage different configuration scenarios
