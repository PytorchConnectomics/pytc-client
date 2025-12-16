import React, { useState } from 'react';
import { Input, Modal, Button, message } from 'antd';
import { FolderOpenOutlined, LaptopOutlined, CloudServerOutlined } from '@ant-design/icons';
import FilePickerModal from './FilePickerModal';

/**
 * Unified File Input Component
 * Supports:
 * - Text input (path)
 * - Drag and drop (external files)
 * - File picker (Local Machine or Server Storage)
 * 
 * @param {string} selectionType - 'file' or 'directory' (default: 'file')
 * @param {object|string} value - The current value. Can be a string (path) or object { path, display }
 */
const UnifiedFileInput = ({ value, onChange, placeholder, style, disabled, selectionType = 'file' }) => {
  const [filePickerVisible, setFilePickerVisible] = useState(false);
  const [sourceSelectionVisible, setSourceSelectionVisible] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);

  const handleBrowse = () => {
    if (disabled) return;
    setSourceSelectionVisible(true);
  };

  const handleLocalSelection = async () => {
    setSourceSelectionVisible(false);
    try {
      const { ipcRenderer } = window.require('electron');
      const properties = selectionType === 'directory'
        ? ['openDirectory']
        : ['openFile'];

      const filePath = await ipcRenderer.invoke('dialog:openFile', { properties });
      if (filePath) {
        // For local files, path and display are the same
        onChange({ path: filePath, display: filePath });
      }
    } catch (error) {
      console.error('Error opening file dialog:', error);
      message.error('Failed to open file dialog');
    }
  };

  const handleServerSelection = () => {
    setSourceSelectionVisible(false);
    setFilePickerVisible(true);
  };

  const handleFilePickerSelect = (item) => {
    let fullPath;
    let displayPath;

    // Determine physical path (backend value)
    if (item.physical_path) {
      fullPath = item.physical_path;
    } else if (item.path && item.path !== 'root') {
      fullPath = `${item.path}/${item.name}`;
    } else {
      fullPath = item.name;
    }

    // Determine display path (logical value)
    if (item.logical_path) {
      displayPath = item.logical_path;
    } else {
      displayPath = item.name;
    }

    onChange({ path: fullPath, display: displayPath });
    setFilePickerVisible(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);

    if (disabled) return;

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      // Electron exposes the full path in the 'path' property of the File object
      if (file.path) {
        onChange({ path: file.path, display: file.path });
      } else {
        message.warning('Could not determine file path. Are you using the Electron app?');
      }
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    if (!disabled) {
      setIsDragOver(true);
    }
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleInputChange = (e) => {
    const val = e.target.value;
    onChange({ path: val, display: val });
  };

  // Extract display value
  const getDisplayValue = () => {
    if (!value) return '';
    if (typeof value === 'object') {
      return value.display || value.path || '';
    }
    return value;
  };

  return (
    <>
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        style={{
          position: 'relative',
          ...style
        }}
      >
        <Input
          value={getDisplayValue()}
          onChange={handleInputChange}
          placeholder={placeholder}
          disabled={disabled}
          style={{
            borderColor: isDragOver ? '#1890ff' : undefined,
            boxShadow: isDragOver ? '0 0 0 2px rgba(24, 144, 255, 0.2)' : undefined
          }}
          prefix={
            <FolderOpenOutlined
              style={{
                cursor: disabled ? 'not-allowed' : 'pointer',
                color: disabled ? '#ccc' : '#1890ff'
              }}
              onClick={handleBrowse}
            />
          }
        />
        {isDragOver && (
          <div style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(24, 144, 255, 0.1)',
            pointerEvents: 'none',
            zIndex: 10,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#1890ff',
            fontWeight: 'bold'
          }}>
            Drop {selectionType === 'directory' ? 'folder' : 'file'} here
          </div>
        )}
      </div>

      {/* Source Selection Modal */}
      <Modal
        title={
          <span>
            <FolderOpenOutlined style={{ marginRight: 8 }} />
            Select Source
          </span>
        }
        open={sourceSelectionVisible}
        onCancel={() => setSourceSelectionVisible(false)}
        footer={null}
        width={400}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '10px 0' }}>
          <p style={{ marginBottom: '16px' }}>Where would you like to select from?</p>
          <Button
            size="large"
            icon={<LaptopOutlined />}
            onClick={handleLocalSelection}
            block
          >
            Local Machine
          </Button>
          <Button
            size="large"
            icon={<CloudServerOutlined />}
            onClick={handleServerSelection}
            block
          >
            Server Storage
          </Button>
        </div>
      </Modal>

      <FilePickerModal
        visible={filePickerVisible}
        onCancel={() => setFilePickerVisible(false)}
        onSelect={handleFilePickerSelect}
        title={`Select ${selectionType === 'directory' ? 'Directory' : 'File'}`}
        selectionType={selectionType}
      />
    </>
  );
};

export default UnifiedFileInput;
