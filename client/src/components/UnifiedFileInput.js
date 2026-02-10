import React, { useState } from "react";
import { Input, message } from "antd";
import { FolderOpenOutlined } from "@ant-design/icons";
import FilePickerModal from "./FilePickerModal";

/**
 * Unified File Input Component
 * Supports:
 * - Text input (path)
 * - Drag and drop (external files)
 * - File picker (mounted storage)
 *
 * @param {string} selectionType - 'file', 'directory', or 'fileOrDirectory' (default: 'file')
 * @param {object|string} value - The current value. Can be a string (path) or object { path, display }
 */
const UnifiedFileInput = ({
  value,
  onChange,
  placeholder,
  style,
  disabled,
  selectionType = "file",
}) => {
  const [filePickerVisible, setFilePickerVisible] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);

  const handleBrowse = () => {
    if (disabled) return;
    setFilePickerVisible(true);
  };

  const handleFilePickerSelect = (item) => {
    let fullPath;
    let displayPath;

    // Determine physical path (backend value)
    if (item.physical_path) {
      fullPath = item.physical_path;
    } else if (item.path && item.path !== "root") {
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
        message.warning(
          "Could not determine file path. Are you using the Electron app?",
        );
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
    if (!value) return "";
    if (typeof value === "object") {
      return value.display || value.path || "";
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
          position: "relative",
          ...style,
        }}
      >
        <Input
          value={getDisplayValue()}
          onChange={handleInputChange}
          placeholder={placeholder}
          disabled={disabled}
          style={{
            borderColor: isDragOver ? "#1890ff" : undefined,
            boxShadow: isDragOver
              ? "0 0 0 2px rgba(24, 144, 255, 0.2)"
              : undefined,
          }}
          prefix={
            <FolderOpenOutlined
              style={{
                cursor: disabled ? "not-allowed" : "pointer",
                color: disabled ? "#ccc" : "#1890ff",
              }}
              onClick={handleBrowse}
            />
          }
        />
        {isDragOver && (
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: "rgba(24, 144, 255, 0.1)",
              pointerEvents: "none",
              zIndex: 10,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#1890ff",
              fontWeight: "bold",
            }}
          >
            Drop {selectionType === "directory" ? "folder" : "file"} here
          </div>
        )}
      </div>

      <FilePickerModal
        visible={filePickerVisible}
        onCancel={() => setFilePickerVisible(false)}
        onSelect={handleFilePickerSelect}
        title={`Select ${selectionType === "directory" ? "Directory" : "File"}`}
        selectionType={selectionType}
      />
    </>
  );
};

export default UnifiedFileInput;
