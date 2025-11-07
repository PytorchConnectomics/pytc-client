# YamlFileEditor Component

## Overview
The YamlFileEditor component provides a text editor interface for viewing and editing YAML configuration files. It allows users to modify training and inference parameters directly in YAML format with syntax validation.

## Functionality
- **YAML Editing**: Text editor for YAML configuration files
- **Syntax Validation**: Real-time YAML syntax checking
- **Type-specific Editing**: Different behavior for training vs inference
- **Auto-save**: Automatically saves changes to global context
- **Error Handling**: Graceful handling of YAML parsing errors

## Key Features
- **Text Area Editor**: Large text area for YAML editing
- **Syntax Highlighting**: Visual feedback for YAML syntax
- **Auto-resize**: Text area adjusts to content size
- **Real-time Validation**: Immediate feedback on syntax errors
- **Context Integration**: Updates global application state

## Props
- `type`: String indicating configuration type ('training' or 'inference')

## State Management
- `yamlContent`: Current YAML content being edited
- Uses global context for accessing and updating configuration
- Manages YAML parsing and validation state

## YAML Configuration
- **Training Config**: Model training parameters and settings
- **Inference Config**: Model inference parameters and settings
- **Parameter Updates**: Real-time updates to configuration values
- **Validation**: Ensures valid YAML syntax and structure

## User Interface
- **Text Editor**: Large, resizable text area for YAML editing
- **File Header**: Displays name of uploaded YAML file
- **Auto-resize**: Text area grows with content
- **Error Display**: Shows YAML parsing errors

## YAML Structure
- **System Parameters**: GPU/CPU configuration
- **Solver Parameters**: Learning rate, batch size, etc.
- **Dataset Parameters**: Input/output paths and file names
- **Inference Parameters**: Augmentation and batch settings

## Integration Points
- **Global Context**: Accesses and updates configuration state
- **YAML Context**: Manages YAML-specific parameters
- **File Upload**: Integrates with YAML file upload system
- **Validation**: Connects to YAML parsing and validation

## User Workflow
1. **File Upload**: Upload YAML configuration file
2. **Content Display**: View current YAML content
3. **Editing**: Modify YAML parameters as needed
4. **Validation**: Check for syntax errors
5. **Saving**: Changes are automatically saved

## Error Handling
- **Syntax Errors**: Real-time YAML syntax validation
- **Parsing Errors**: Graceful handling of invalid YAML
- **User Feedback**: Clear error messages and guidance
- **Recovery**: Allows users to fix syntax errors

## YAML Parameters

### Training Parameters
- **SYSTEM.NUM_GPUS**: Number of GPUs to use
- **SYSTEM.NUM_CPUS**: Number of CPUs to use
- **SOLVER.BASE_LR**: Learning rate for training
- **SOLVER.SAMPLES_PER_BATCH**: Batch size for training

### Inference Parameters
- **INFERENCE.SAMPLES_PER_BATCH**: Batch size for inference
- **INFERENCE.AUG_NUM**: Number of augmentations
- **DATASET.INPUT_PATH**: Path to input data
- **DATASET.OUTPUT_PATH**: Path to save results

## Use Cases
- **Parameter Tuning**: Adjust hyperparameters for optimal performance
- **Configuration Customization**: Modify YAML settings for specific needs
- **Advanced Setup**: Fine-tune parameters not available in sliders
- **Debugging**: Edit configuration to resolve issues
