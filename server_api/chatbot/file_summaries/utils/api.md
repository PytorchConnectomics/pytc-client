# API Utility Functions

## Overview
The API utility module provides centralized functions for communicating with the backend services. It handles all HTTP requests, error handling, and data formatting for the PyTorch Connectomics client application.

## Functionality
- **HTTP Requests**: Centralized HTTP request handling
- **Error Handling**: Comprehensive error handling and user feedback
- **Data Formatting**: Proper data formatting for API requests
- **Service Integration**: Connects to various backend services
- **Response Processing**: Handles API responses and data extraction

## Key Features
- **Centralized API**: Single point for all API communications
- **Error Handling**: Robust error handling with user feedback
- **Data Validation**: Ensures proper data formatting
- **Service Integration**: Connects to multiple backend services
- **Response Processing**: Efficient response handling and data extraction

## API Endpoints

### Neuroglancer Visualization
- **getNeuroglancerViewer**: Generate Neuroglancer 3D visualizations
- **Data Format**: Image and label paths with voxel scales
- **Response**: Neuroglancer viewer URL

### Model Training
- **startModelTraining**: Initiate model training process
- **stopModelTraining**: Halt model training process
- **Data Format**: Training configuration and parameters
- **Response**: Training status and progress

### Model Inference
- **startModelInference**: Run model inference on new data
- **stopModelInference**: Halt model inference process
- **Data Format**: Inference configuration and checkpoint paths
- **Response**: Inference status and results

### Monitoring
- **getTensorboardURL**: Get TensorBoard monitoring URL
- **Response**: TensorBoard interface URL

### Chat Assistant
- **createChatSession**: Create new chat session
- **queryChatBot**: Send queries to AI assistant
- **Data Format**: Session ID and user queries
- **Response**: AI assistant responses

## Error Handling
- **HTTP Errors**: Comprehensive HTTP error handling
- **Network Errors**: Graceful handling of network issues
- **Data Validation**: Ensures proper data formatting
- **User Feedback**: Clear error messages and guidance

## Data Formatting
- **Request Data**: Proper JSON formatting for API requests
- **Response Data**: Efficient response data extraction
- **Error Messages**: Clear and informative error messages
- **Status Codes**: Proper HTTP status code handling

## Service Integration
- **Backend Services**: Connects to various backend services
- **API Protocol**: Configurable API protocol and URL
- **Authentication**: Handles authentication if needed
- **Rate Limiting**: Manages API rate limiting

## User Experience
- **Loading States**: Proper loading indicators
- **Error Messages**: Clear and helpful error messages
- **Success Feedback**: Confirmation of successful operations
- **Progress Tracking**: Real-time progress updates

## Technical Implementation
- **Axios Integration**: Uses Axios for HTTP requests
- **Promise Handling**: Proper async/await pattern
- **Error Boundaries**: Comprehensive error handling
- **Performance**: Optimized request handling

## Use Cases
- **Data Visualization**: Generate 3D visualizations
- **Model Training**: Execute training workflows
- **Model Inference**: Run inference on new data
- **Monitoring**: Access training metrics and performance
- **User Support**: AI-powered assistance and guidance

## Advanced Features
- **Request Interceptors**: Automatic request processing
- **Response Interceptors**: Automatic response processing
- **Error Recovery**: Automatic retry and error recovery
- **Performance Monitoring**: Track API performance and usage

## Configuration
- **Environment Variables**: Configurable API endpoints
- **Protocol Settings**: HTTP/HTTPS protocol configuration
- **Timeout Settings**: Configurable request timeouts
- **Retry Logic**: Automatic retry for failed requests
