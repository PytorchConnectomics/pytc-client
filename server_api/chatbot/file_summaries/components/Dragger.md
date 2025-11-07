# Dragger Component

## Overview
The Dragger component provides a drag-and-drop file upload interface with advanced file handling capabilities. It supports multiple file formats including TIFF images and provides preview functionality for uploaded files.

## Functionality
- **Drag & Drop Upload**: Intuitive file upload with drag-and-drop support
- **Multi-file Support**: Handle multiple files simultaneously
- **File Preview**: Generate thumbnails for uploaded images
- **File Type Detection**: Automatically categorize files as images or labels
- **TIFF Support**: Special handling for TIFF image files with preview generation
- **File Management**: Add, remove, and organize uploaded files

## Key Features
- **Visual Upload Area**: Large, clear drop zone for file uploads
- **File Previews**: Thumbnail generation for image files
- **File Categorization**: Separate handling for images and labels
- **Path Management**: Track and manage file paths
- **Cache Management**: Clear file cache functionality
- **Error Handling**: Graceful handling of upload errors

## File Type Support
- **Images**: JPG, PNG, TIFF, and other image formats
- **Labels**: Segmentation masks and annotation files
- **TIFF Special Handling**: Custom preview generation for TIFF files

## User Interface
- **Upload Area**: Large drop zone with clear instructions
- **File List**: Visual list of uploaded files with thumbnails
- **Preview Modal**: Detailed file preview with metadata
- **File Controls**: Add, remove, and categorize files
- **Cache Controls**: Clear all uploaded files

## File Management
- **File Storage**: Maintains list of uploaded files in global context
- **Path Tracking**: Stores file paths for later use
- **File Categorization**: Separates images and labels
- **Metadata**: Tracks file names, paths, and types

## TIFF Handling
- **Preview Generation**: Creates thumbnails for TIFF files
- **Metadata Extraction**: Reads TIFF tags for dimensions
- **Error Recovery**: Fallback to default image on errors
- **Performance**: Optimized handling of large TIFF files

## State Management
- **File List**: Maintains array of uploaded files
- **Preview State**: Manages file preview modal
- **File Metadata**: Tracks file properties and paths
- **Error State**: Handles upload and processing errors

## User Workflow
1. **File Upload**: Drag and drop files or click to browse
2. **File Preview**: Click on files to see detailed preview
3. **File Categorization**: Select whether file is image or label
4. **Path Configuration**: Set folder paths for files
5. **File Management**: Remove files or clear entire cache

## Integration Points
- **Global Context**: Updates file lists and metadata
- **File System**: Interacts with local file system
- **Image Processing**: Handles image preview generation
- **UI Components**: Integrates with Ant Design upload components

## Error Handling
- **Upload Errors**: Graceful handling of failed uploads
- **File Processing**: Error recovery for corrupted files
- **Path Validation**: Ensures valid file paths
- **User Feedback**: Clear error messages and guidance

## Use Cases
- **Data Preparation**: Upload training and validation data
- **File Organization**: Categorize files for different workflows
- **Preview Management**: Review files before processing
- **Cache Management**: Clear and reset file collections
