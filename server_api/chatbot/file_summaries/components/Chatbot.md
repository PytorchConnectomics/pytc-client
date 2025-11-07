# Chatbot Component

## Overview
The ChatBot component provides an AI-powered conversational interface for user support and assistance. It integrates with a RAG (Retrieval-Augmented Generation) backend to provide intelligent responses about the PyTorch Connectomics platform.

## Functionality
- **Real-time Chat Interface**: Provides a full-screen chat interface with message history
- **Session Management**: Creates and maintains chat sessions with unique session IDs
- **Message Persistence**: Saves chat history and session data in localStorage
- **AI Integration**: Connects to backend RAG system for intelligent responses
- **User Experience**: Clean, modern UI with message bubbles and typing indicators

## Key Features
- **Session-based Conversations**: Each chat session maintains context and memory
- **Message History**: Persistent storage of conversation history
- **Error Handling**: Graceful error handling for network issues
- **Responsive Design**: Full-height layout with proper scrolling
- **Input Validation**: Prevents empty message sending

## Props
- `onClose`: Function to close the chat interface

## State Management
- `messages`: Array of chat messages with user/bot distinction
- `inputValue`: Current text input value
- `sessionId`: Unique identifier for the chat session
- `isSending`: Boolean indicating if a message is being processed

## API Integration
- **createChatSession()**: Creates a new chat session with the backend
- **queryChatBot(sessionId, query)**: Sends user queries to the AI assistant

## User Interactions
1. **Opening Chat**: Click the message icon to open the chat interface
2. **Sending Messages**: Type in the text area and press Enter or click Send
3. **Session Persistence**: Chat history is automatically saved and restored
4. **Closing Chat**: Click the X button to close the interface

## Technical Implementation
- Uses Ant Design components for UI consistency
- Implements proper cleanup with useEffect hooks
- Handles async operations with proper error boundaries
- Manages local storage for data persistence

## Use Cases
- **User Support**: Help users navigate the platform and understand features
- **Troubleshooting**: Assist with common issues and error resolution
- **Feature Guidance**: Provide step-by-step instructions for complex workflows
- **Documentation Access**: Answer questions about platform capabilities

## Integration Points
- **Global Context**: Accesses shared application state
- **API Layer**: Communicates with backend RAG system
- **Local Storage**: Persists user data across sessions
- **UI Framework**: Integrates with Ant Design component library
