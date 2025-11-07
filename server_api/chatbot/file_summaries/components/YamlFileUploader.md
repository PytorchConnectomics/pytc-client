# YamlFileUploader Component

## Overview
The YamlFileUploader component provides an interface for uploading and configuring YAML configuration files for model training and inference. It includes parameter sliders for easy adjustment of key settings and automatic YAML generation.

## Functionality
- **YAML Upload**: Upload YAML configuration files
- **Parameter Sliders**: Interactive sliders for key parameters
- **Auto-generation**: Automatically generates YAML from slider values
- **Type-specific Configuration**: Different parameters for training vs inference
- **Path Integration**: Automatically updates input/output paths

## Key Features
- **File Upload**: Drag-and-drop or click to upload YAML files
- **Parameter Sliders**: Visual sliders for adjusting key parameters
- **Real-time Updates**: Immediate YAML generation from slider changes
- **Path Management**: Automatic path configuration based on selected files
- **Validation**: Ensures proper YAML structure and values

## Props
- `type`: String indicating configuration type ('training' or 'inference')

## Parameter Sliders

### Training Parameters
- **Number of GPUs**: 0-8 GPUs for training
- **Number of CPUs**: 1-8 CPUs for processing
- **Learning Rate**: 0.01-0.1 learning rate range
- **Samples Per Batch**: 2-16 batch size range

### Inference Parameters
- **Augmentation Number**: 2-16 augmentation count
- **Samples Per Batch**: 2-16 batch size for inference

## YAML Structure
- **SYSTEM Section**: GPU/CPU configuration
- **SOLVER Section**: Training parameters (learning rate, batch size)
- **INFERENCE Section**: Inference-specific parameters
- **DATASET Section**: Input/output paths and file names

## User Interface
- **Upload Button**: Clear upload interface for YAML files
- **Parameter Grid**: Organized grid of parameter sliders
- **File Display**: Shows name of uploaded YAML file
- **Slider Controls**: Interactive sliders with value labels

## State Management
- Uses global context for accessing and updating configuration
- Manages YAML content and parameter values
- Updates file paths and configuration settings

## Integration Points
- **Global Context**: Accesses file lists and configuration state
- **YAML Context**: Manages YAML-specific parameters
- **File System**: Integrates with file upload and path management
- **Configuration**: Connects to training/inference setup

## User Workflow
1. **File Upload**: Upload YAML configuration file
2. **Parameter Adjustment**: Use sliders to adjust key parameters
3. **Path Configuration**: Automatically updates input/output paths
4. **YAML Generation**: Real-time YAML generation from slider values
5. **Validation**: Ensure proper configuration before proceeding

## YAML Generation
- **Automatic Updates**: YAML updates when sliders change
- **Path Integration**: Automatically sets input/output paths
- **Parameter Mapping**: Maps slider values to YAML structure
- **Validation**: Ensures valid YAML syntax and values

## Error Handling
- **File Validation**: Ensures uploaded files are valid YAML
- **Parameter Validation**: Checks parameter ranges and values
- **Path Validation**: Ensures valid input/output paths
- **User Feedback**: Clear error messages and guidance

## Use Cases
- **Configuration Setup**: Upload and configure YAML files
- **Parameter Tuning**: Adjust key parameters with sliders
- **Path Management**: Automatically configure input/output paths
- **Workflow Setup**: Prepare configuration for training/inference

## Advanced Features
- **Common Path Detection**: Automatically finds common paths between files
- **Parameter Persistence**: Maintains parameter values across sessions
- **Real-time Updates**: Immediate feedback on parameter changes
- **Validation**: Comprehensive validation of configuration values
