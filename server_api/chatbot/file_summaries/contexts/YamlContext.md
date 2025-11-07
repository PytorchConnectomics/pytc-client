# YamlContext Provider

## Overview
The YamlContext provider manages YAML-specific configuration parameters for model training and inference. It provides specialized state management for YAML configuration files and their associated parameters.

## Functionality
- **Parameter Management**: Manages YAML configuration parameters
- **Training Parameters**: Handles training-specific YAML settings
- **Inference Parameters**: Manages inference-specific YAML settings
- **Parameter Updates**: Real-time updates to YAML parameters
- **Configuration State**: Maintains YAML configuration state

## Key Features
- **Parameter Tracking**: Monitors YAML parameter values
- **Type-specific Logic**: Different behavior for training vs inference
- **Real-time Updates**: Immediate parameter updates
- **State Persistence**: Maintains parameter state across sessions
- **Validation**: Ensures parameter validity and ranges

## Training Parameters
- **Number of GPUs**: GPU configuration for training
- **Number of CPUs**: CPU configuration for processing
- **Learning Rate**: Learning rate for optimization
- **Samples Per Batch**: Batch size for training

## Inference Parameters
- **Augmentation Number**: Number of augmentations to apply
- **Samples Per Batch**: Batch size for inference

## State Management
- **Parameter State**: Tracks all YAML parameters
- **Update Functions**: Provides functions to update parameters
- **State Synchronization**: Automatic state updates
- **Validation**: Ensures parameter validity

## Context Provider
- **YamlContext**: Main context for YAML parameters
- **YamlContextWrapper**: Provider component for state management
- **State Access**: Provides state to child components
- **State Updates**: Handles parameter changes and updates

## Parameter Updates
- **Real-time Updates**: Immediate parameter updates
- **Validation**: Ensures parameter values are valid
- **State Synchronization**: Updates state across components
- **Error Handling**: Graceful handling of invalid parameters

## Integration Points
- **YAML Components**: Integrates with YAML editing components
- **Configuration**: Connects to training/inference configuration
- **Parameter Sliders**: Provides data for parameter sliders
- **YAML Generation**: Updates YAML content based on parameters

## User Interface
- **Parameter Sliders**: Visual controls for parameter adjustment
- **Real-time Updates**: Immediate feedback on parameter changes
- **Validation**: Visual feedback on parameter validity
- **State Display**: Clear indication of current parameter values

## Error Handling
- **Parameter Validation**: Ensures parameter values are valid
- **Range Checking**: Validates parameter ranges
- **Type Validation**: Ensures correct parameter types
- **User Feedback**: Clear error messages and guidance

## Use Cases
- **Parameter Tuning**: Adjust YAML parameters for optimal performance
- **Configuration Management**: Manage YAML configuration state
- **Parameter Synchronization**: Keep parameters in sync across components
- **YAML Generation**: Generate YAML content from parameters

## Technical Implementation
- **React Context**: Uses React Context API for state management
- **State Updates**: Efficient parameter update mechanisms
- **Validation**: Robust parameter validation
- **Performance**: Optimized for real-time updates

## Advanced Features
- **Parameter Persistence**: Maintains parameters across sessions
- **Validation**: Comprehensive parameter validation
- **Performance**: Efficient parameter updates
- **Scalability**: Handles complex parameter configurations

## Parameter Types
- **Numeric Parameters**: GPU/CPU counts, learning rates, batch sizes
- **Configuration Parameters**: System and solver settings
- **Inference Parameters**: Augmentation and batch settings
- **Validation Parameters**: Parameter ranges and constraints
