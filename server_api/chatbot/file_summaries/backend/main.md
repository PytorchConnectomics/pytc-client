# Backend API Server (main.py)

## Overview
The main.py file serves as the primary FastAPI backend server for the PyTorch Connectomics client application. It provides RESTful API endpoints for data visualization, model training, inference, monitoring, and AI-powered user assistance.

## Functionality
- **RESTful API**: Comprehensive REST API for client-server communication
- **CORS Support**: Cross-origin resource sharing for web client
- **Data Visualization**: Neuroglancer 3D visualization services
- **Model Operations**: Training and inference workflow management
- **AI Assistant**: RAG-powered chatbot for user support
- **Monitoring**: TensorBoard integration for training metrics

## Key Features
- **FastAPI Framework**: Modern, high-performance web framework
- **Async Support**: Asynchronous request handling for better performance
- **CORS Middleware**: Cross-origin support for web clients
- **Error Handling**: Comprehensive error handling and logging
- **Service Integration**: Connects to various backend services

## API Endpoints

### Health Check
- **GET /hello**: Basic health check endpoint
- **Response**: Simple hello message
- **Use Case**: Verify server connectivity

### AI Chat Assistant
- **POST /chat/session**: Create new chat session
- **POST /chat/query**: Send queries to AI assistant
- **Features**: RAG-powered responses with context
- **Integration**: OpenAI GPT-4 and Pinecone vector store

### Data Visualization
- **POST /neuroglancer**: Generate Neuroglancer 3D visualizations
- **Input**: Image and label paths with voxel scales
- **Output**: Neuroglancer viewer URL
- **Features**: Interactive 3D visualization of biomedical data

### Model Training
- **POST /start_model_training**: Initiate model training
- **POST /stop_model_training**: Halt model training
- **Features**: Distributed training support
- **Integration**: PyTorch Connectomics training pipeline

### Model Inference
- **POST /start_model_inference**: Run model inference
- **POST /stop_model_inference**: Halt model inference
- **Features**: Batch inference processing
- **Integration**: PyTorch Connectomics inference pipeline

### Monitoring
- **GET /get_tensorboard_url**: Get TensorBoard monitoring URL
- **Features**: Training metrics visualization
- **Integration**: TensorBoard service integration

### File Operations
- **POST /check_files**: Validate and categorize uploaded files
- **Features**: File type detection and validation
- **Integration**: File system operations

## AI Assistant Integration
- **RAG System**: Retrieval-Augmented Generation for intelligent responses
- **Vector Store**: Pinecone integration for document retrieval
- **Language Model**: OpenAI GPT-4 for response generation
- **Session Management**: Multi-session chat support
- **Context Awareness**: Maintains conversation context

## Data Processing
- **File Validation**: Automatic file type detection
- **Path Processing**: Secure path handling and validation
- **Data Formatting**: Proper data formatting for API responses
- **Error Recovery**: Graceful handling of processing errors

## Service Integration
- **PyTorch Connectomics**: Integration with deep learning framework
- **Neuroglancer**: 3D visualization service integration
- **TensorBoard**: Training monitoring service
- **External APIs**: OpenAI and Pinecone service integration

## Security Features
- **Path Validation**: Secure file path handling
- **Input Sanitization**: Proper input validation and sanitization
- **Error Handling**: Secure error messages without sensitive data
- **CORS Configuration**: Proper cross-origin resource sharing

## Performance Optimization
- **Async Operations**: Asynchronous request handling
- **Connection Pooling**: Efficient database and service connections
- **Caching**: Strategic caching for improved performance
- **Resource Management**: Proper resource cleanup and management

## Error Handling
- **HTTP Errors**: Comprehensive HTTP error handling
- **Service Errors**: Graceful handling of service failures
- **Validation Errors**: Input validation and error reporting
- **User Feedback**: Clear error messages and guidance

## Configuration
- **Environment Variables**: Configurable service endpoints
- **CORS Settings**: Cross-origin resource sharing configuration
- **Service URLs**: Configurable backend service URLs
- **Logging**: Comprehensive logging and monitoring

## Use Cases
- **Data Visualization**: Generate 3D visualizations of biomedical data
- **Model Training**: Execute deep learning model training
- **Model Inference**: Run inference on new biomedical data
- **User Support**: Provide AI-powered assistance and guidance
- **Monitoring**: Track training progress and performance

## Technical Implementation
- **FastAPI**: Modern Python web framework
- **Async/Await**: Asynchronous programming patterns
- **Middleware**: CORS and error handling middleware
- **Service Integration**: Multiple backend service integrations

## Advanced Features
- **Session Management**: Multi-user session support
- **Real-time Updates**: WebSocket support for real-time communication
- **Batch Processing**: Efficient batch processing capabilities
- **Scalability**: Horizontal scaling support

## Integration Points
- **Frontend Client**: React.js client application
- **PyTorch Connectomics**: Deep learning framework
- **Neuroglancer**: 3D visualization service
- **TensorBoard**: Training monitoring service
- **AI Services**: OpenAI and Pinecone integrations
