import React, { useState, useEffect, useRef } from 'react';
import { Button, Input, Modal, message, Menu, Breadcrumb, Empty, Image } from 'antd';
import { FolderFilled, FileOutlined, FileTextOutlined, HomeOutlined, ArrowUpOutlined, AppstoreOutlined, BarsOutlined, UploadOutlined, EyeOutlined } from '@ant-design/icons';
import axios from 'axios';

// API base URL (adjust via env vars if needed)
const API_BASE = `${process.env.REACT_APP_SERVER_PROTOCOL || 'http'}://${process.env.REACT_APP_SERVER_URL || 'localhost:4243'}`;

// Configure axios to include JWT token
axios.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Transform backend file list into UI state
const transformFiles = (fileList) => {
  const folders = [];
  const files = {};
  fileList.forEach((f) => {
    if (f.is_folder) {
      folders.push({ key: String(f.id), title: f.name, parent: f.path === 'root' ? 'root' : String(f.path), is_folder: true });
    } else {
      const parentKey = f.path || 'root';
      if (!files[parentKey]) files[parentKey] = [];
      files[parentKey].push({ key: String(f.id), name: f.name, size: f.size, type: f.type, is_folder: false });
    }
  });
  if (!folders.find((f) => f.key === 'root')) {
    folders.unshift({ key: 'root', title: 'My Drive', parent: null });
  }
  return { folders, files };
};

function FilesManager() {
  const [folders, setFolders] = useState([]);
  const [files, setFiles] = useState({});
  const [currentFolder, setCurrentFolder] = useState('root');
  const [viewMode, setViewMode] = useState('grid'); // 'grid' or 'list'
  const [selectedItems, setSelectedItems] = useState([]);
  const [clipboard, setClipboard] = useState({ items: [], action: null }); // copy / move
  const [editingItem, setEditingItem] = useState(null);
  const [newItemType, setNewItemType] = useState(null);
  const [tempName, setTempName] = useState('');
  const inputRef = useRef(null);
  const [contextMenu, setContextMenu] = useState(null);
  const [previewFile, setPreviewFile] = useState(null);
  const [propertiesData, setPropertiesData] = useState(null);
  const [selectionBox, setSelectionBox] = useState(null);
  const containerRef = useRef(null);
  const itemRefs = useRef({});
  const isDragSelecting = useRef(false);

  // Focus input when editing starts
  useEffect(() => {
    if (editingItem && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editingItem]);

  // Load initial data
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    const fetchFiles = async () => {
      try {
        const res = await axios.get(`${API_BASE}/files`, { withCredentials: true });
        const { folders: flds, files: fls } = transformFiles(res.data);
        setFolders(flds);
        setFiles(fls);
      } catch (err) {
        console.error('Failed to load files', err);
        message.error('Could not load files');
      }
    };
    fetchFiles();
  }, []);

  const getCurrentFolderObj = () => folders.find((f) => f.key === currentFolder);
  // eslint-disable-next-line no-loop-func
  const getBreadcrumbs = () => {
    const path = [];
    let curr = getCurrentFolderObj();
    while (curr) {
      path.unshift(curr);
      curr = folders.find((f) => f.key === curr.parent);
    }
    return path;
  };

  const handleNavigate = (key) => {
    setCurrentFolder(key);
    setSelectedItems([]);
    setEditingItem(null);
    setNewItemType(null);
  };

  const handleUp = () => {
    const curr = getCurrentFolderObj();
    if (curr && curr.parent) handleNavigate(curr.parent);
  };

  // Folder creation
  const startCreateFolder = () => {
    const key = `new_folder_${Date.now()}`;
    setNewItemType('folder');
    setEditingItem(key);
    setTempName('');
  };

  const finishCreateFolder = async () => {
    if (!tempName.trim()) {
      setEditingItem(null);
      setNewItemType(null);
      return;
    }
    try {
      const payload = { name: tempName, path: currentFolder };
      const res = await axios.post(`${API_BASE}/files/folder`, payload, { withCredentials: true });
      const newFolder = res.data;
      setFolders([...folders, { key: String(newFolder.id), title: newFolder.name, parent: newFolder.path }]);
      setFiles({ ...files, [String(newFolder.id)]: [] });
      message.success('Folder created');
    } catch (err) {
      console.error(err);
      message.error('Failed to create folder');
    }
    setEditingItem(null);
    setNewItemType(null);
  };

  // Rename
  const startRename = (key, currentName) => {
    setEditingItem(key);
    setTempName(currentName);
  };

  const finishRename = async () => {
    if (!tempName.trim()) {
      setEditingItem(null);
      return;
    }
    const key = editingItem;
    const isFolder = folders.some((f) => f.key === key);
    try {
      await axios.put(`${API_BASE}/files/${key}`, { name: tempName, path: isFolder ? undefined : currentFolder }, { withCredentials: true });
      if (isFolder) {
        setFolders(folders.map((f) => (f.key === key ? { ...f, title: tempName } : f)));
      } else {
        setFiles((prev) => ({
          ...prev,
          [currentFolder]: prev[currentFolder].map((f) => (f.key === key ? { ...f, name: tempName } : f)),
        }));
      }
      message.success('Renamed successfully');
    } catch (err) {
      console.error(err);
      message.error('Rename failed');
    }
    setEditingItem(null);
  };

  // Delete
  const handleDelete = async (keys = selectedItems) => {
    if (keys.length === 0) return;
    try {
      await Promise.all(keys.map((id) => axios.delete(`${API_BASE}/files/${id}`, { withCredentials: true })));
      const folderIds = keys.filter((k) => folders.some((f) => f.key === k));
      const fileIds = keys.filter((k) => !folderIds.includes(k));
      setFolders(folders.filter((f) => !folderIds.includes(f.key)));
      setFiles((prev) => {
        const newFiles = { ...prev };
        Object.keys(newFiles).forEach((fk) => {
          newFiles[fk] = newFiles[fk].filter((f) => !fileIds.includes(f.key));
        });
        return newFiles;
      });
      setSelectedItems([]);
      message.success(`Deleted ${keys.length} items`);
    } catch (err) {
      console.error(err);
      message.error('Delete failed');
    }
  };

  // Copy / Paste (simple copy creates a new entry via folder endpoint for demo)
  const handleCopy = (keys = selectedItems) => {
    if (keys.length === 0) return;
    setClipboard({ items: keys, action: 'copy' });
    message.info('Copied to clipboard');
  };

  const handlePaste = async () => {
    if (!clipboard.items.length) return;
    if (clipboard.action === 'copy') {
      const newEntries = [];
      for (const id of clipboard.items) {
        const orig = Object.values(files).flat().find((f) => f.key === id);
        if (!orig) continue;
        const payload = { name: `Copy of ${orig.name}`, path: currentFolder };
        try {
          const res = await axios.post(`${API_BASE}/files/folder`, payload, { withCredentials: true });
          newEntries.push({ key: String(res.data.id), name: payload.name, size: orig.size, type: orig.type });
        } catch (err) {
          console.error('Paste error', err);
        }
      }
      if (newEntries.length) {
        setFiles((prev) => ({ ...prev, [currentFolder]: [...(prev[currentFolder] || []), ...newEntries] }));
        message.success('Pasted items');
      }
    }
  };

  // Preview
  const handlePreview = (key) => {
    const file = (files[currentFolder] || []).find((f) => f.key === key);
    if (file) setPreviewFile(file);
  };

  // Properties
  const handleProperties = (keys = selectedItems) => {
    if (keys.length === 0) return;

    if (keys.length === 1) {
      // Single item - show detailed info
      const key = keys[0];
      const folder = folders.find((f) => f.key === key);
      const file = Object.values(files).flat().find((f) => f.key === key);
      const item = folder || file;

      if (item) {
        setPropertiesData({
          type: 'single',
          name: item.title || item.name,
          isFolder: !!folder,
          size: item.size || 'N/A',
          fileType: item.type || 'Folder',
          created: new Date().toLocaleString(), // Backend should provide this
          modified: new Date().toLocaleString(), // Backend should provide this
        });
      }
    } else {
      // Multiple items - show summary
      const folderKeys = keys.filter((k) => folders.some((f) => f.key === k));
      const fileKeys = keys.filter((k) => !folderKeys.includes(k));

      // Calculate total size (simplified - would need backend support for accurate calculation)
      let totalSize = 0;
      fileKeys.forEach((key) => {
        const file = Object.values(files).flat().find((f) => f.key === key);
        if (file && file.size) {
          // Parse size string (e.g., "1.5MB" or "500KB")
          const sizeStr = String(file.size);
          const match = sizeStr.match(/([0-9.]+)\s*(KB|MB|GB)/i);
          if (match) {
            const value = parseFloat(match[1]);
            const unit = match[2].toUpperCase();
            if (unit === 'KB') totalSize += value;
            else if (unit === 'MB') totalSize += value * 1024;
            else if (unit === 'GB') totalSize += value * 1024 * 1024;
          }
        }
      });

      const totalSizeStr = totalSize > 1024
        ? `${(totalSize / 1024).toFixed(2)} MB`
        : `${totalSize.toFixed(2)} KB`;

      setPropertiesData({
        type: 'multiple',
        totalCount: keys.length,
        folderCount: folderKeys.length,
        fileCount: fileKeys.length,
        totalSize: totalSizeStr,
      });
    }
  };

  // Drag & Drop
  const handleDragStart = (e, key, type) => {
    let itemsToDrag = selectedItems;
    if (!selectedItems.includes(key)) {
      itemsToDrag = [key];
      setSelectedItems([key]);
    }
    e.dataTransfer.setData('text/plain', JSON.stringify({ keys: itemsToDrag }));
  };

  const handleDragOver = (e) => e.preventDefault();

  const handleDrop = async (e, targetFolderKey) => {
    e.preventDefault();

    // Check if dropping files from OS (external files)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      await handleExternalFileDrop(e.dataTransfer.files, targetFolderKey);
      return;
    }

    // Handle internal drag-and-drop
    const dataStr = e.dataTransfer.getData('text/plain');
    if (!dataStr) return;
    const { keys } = JSON.parse(dataStr);
    if (!keys || keys.length === 0) return;
    if (keys.includes(targetFolderKey)) return;

    let moved = 0;
    for (const key of keys) {
      const isFolder = folders.some((f) => f.key === key);
      const item = isFolder
        ? folders.find((f) => f.key === key)
        : Object.values(files).flat().find((f) => f.key === key);

      if (!item) continue;

      try {
        // Send name along with path to fix 422 error
        await axios.put(`${API_BASE}/files/${key}`, {
          name: item.title || item.name,
          path: targetFolderKey
        }, { withCredentials: true });

        if (isFolder) {
          setFolders((prev) => prev.map((f) => (f.key === key ? { ...f, parent: targetFolderKey } : f)));
        } else {
          setFiles((prev) => {
            const sourceFolder = Object.keys(prev).find((fk) => prev[fk].some((f) => f.key === key));
            if (!sourceFolder) return prev;
            const fileObj = prev[sourceFolder].find((f) => f.key === key);
            const newSource = prev[sourceFolder].filter((f) => f.key !== key);
            const newTarget = [...(prev[targetFolderKey] || []), fileObj];
            return { ...prev, [sourceFolder]: newSource, [targetFolderKey]: newTarget };
          });
        }
        moved++;
      } catch (err) {
        console.error('Move error', err);
        message.error(`Failed to move ${item.title || item.name}`);
      }
    }
    if (moved) {
      message.success(`Moved ${moved} items`);
      setSelectedItems([]);
    }
  };

  // Handle external file drops from OS
  const handleExternalFileDrop = async (fileList, targetFolder) => {
    const filesArray = Array.from(fileList);
    let uploaded = 0;

    for (const file of filesArray) {
      const form = new FormData();
      form.append('file', file);
      form.append('path', targetFolder);

      try {
        const res = await axios.post(`${API_BASE}/files/upload`, form, {
          headers: { 'Content-Type': 'multipart/form-data' },
          withCredentials: true,
        });
        const newFile = res.data;
        setFiles((prev) => ({
          ...prev,
          [targetFolder]: [...(prev[targetFolder] || []), {
            key: String(newFile.id),
            name: newFile.name,
            size: newFile.size,
            type: newFile.type
          }],
        }));
        uploaded++;
      } catch (err) {
        console.error('Upload error', err);
        message.error(`Failed to upload ${file.name}`);
      }
    }

    if (uploaded > 0) {
      message.success(`Uploaded ${uploaded} file${uploaded > 1 ? 's' : ''}`);
    }
  };


  // Selection box handling
  const handleMouseDown = (e) => {
    if (e.target !== containerRef.current && e.target.className !== 'file-manager-content') return;
    isDragSelecting.current = false;
    if (!e.ctrlKey && !e.shiftKey) setSelectedItems([]);
    const rect = containerRef.current.getBoundingClientRect();
    setSelectionBox({
      startX: e.clientX - rect.left,
      startY: e.clientY - rect.top + containerRef.current.scrollTop,
      currentX: e.clientX - rect.left,
      currentY: e.clientY - rect.top + containerRef.current.scrollTop,
      initialSelected: e.ctrlKey ? [...selectedItems] : [],
    });
  };

  const handleMouseMove = (e) => {
    if (!selectionBox) return;
    const rect = containerRef.current.getBoundingClientRect();
    const currentX = e.clientX - rect.left;
    const currentY = e.clientY - rect.top + containerRef.current.scrollTop;
    if (Math.abs(currentX - selectionBox.startX) > 5 || Math.abs(currentY - selectionBox.startY) > 5) {
      isDragSelecting.current = true;
    }
    setSelectionBox((prev) => ({ ...prev, currentX, currentY }));
    const left = Math.min(selectionBox.startX, currentX);
    const top = Math.min(selectionBox.startY, currentY);
    const width = Math.abs(currentX - selectionBox.startX);
    const height = Math.abs(currentY - selectionBox.startY);
    const newSelected = [];
    Object.keys(itemRefs.current).forEach((key) => {
      const el = itemRefs.current[key];
      if (!el) return;
      const itemRect = el.getBoundingClientRect();
      const containerRect = containerRef.current.getBoundingClientRect();
      const itemLeft = itemRect.left - containerRect.left;
      const itemTop = itemRect.top - containerRect.top + containerRef.current.scrollTop;
      if (
        left < itemLeft + itemRect.width &&
        left + width > itemLeft &&
        top < itemTop + itemRect.height &&
        top + height > itemTop
      ) {
        newSelected.push(key);
      }
    });
    const merged = Array.from(new Set([...selectionBox.initialSelected, ...newSelected]));
    setSelectedItems(merged);
  };

  const handleMouseUp = () => setSelectionBox(null);

  // Keyboard shortcuts
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (editingItem) {
        if (e.key === 'Enter') newItemType ? finishCreateFolder() : finishRename();
        if (e.key === 'Escape') {
          setEditingItem(null);
          setNewItemType(null);
        }
        return;
      }
      if (e.target.tagName === 'INPUT') return;
      if (e.key === 'Delete') handleDelete();
      if (e.ctrlKey && e.key === 'c') handleCopy();
      if (e.ctrlKey && e.key === 'v') handlePaste();
      if (e.ctrlKey && e.key === 'a') {
        e.preventDefault();
        const allKeys = [
          ...folders.filter((f) => f.parent === currentFolder).map((f) => f.key),
          ...(files[currentFolder] || []).map((f) => f.key),
        ];
        setSelectedItems(allKeys);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedItems, clipboard, currentFolder, folders, files, editingItem, newItemType, tempName]);

  // Context menu handling
  const handleContextMenu = (e, type, key) => {
    e.preventDefault();
    e.stopPropagation();
    if (type === 'item') {
      if (!selectedItems.includes(key)) setSelectedItems([key]);
    } else if (type === 'container') {
      if (e.target === containerRef.current || e.target.className === 'file-manager-content') setSelectedItems([]);
    }
    setContextMenu({ x: e.clientX, y: e.clientY, type, key });
  };

  useEffect(() => {
    const handleClick = () => setContextMenu(null);
    window.addEventListener('click', handleClick);
    return () => window.removeEventListener('click', handleClick);
  }, []);

  const renderItem = (item, type) => {
    const isSelected = selectedItems.includes(item.key);
    const isEditing = editingItem === item.key;
    const icon = type === 'folder' ? <FolderFilled style={{ fontSize: 48, color: '#1890ff' }} /> : <FileOutlined style={{ fontSize: 48, color: '#555' }} />;
    return (
      <div
        key={item.key}
        ref={(el) => (itemRefs.current[item.key] = el)}
        draggable={!isEditing}
        onDragStart={(e) => handleDragStart(e, item.key, type)}
        onDragOver={type === 'folder' ? handleDragOver : undefined}
        onDrop={type === 'folder' ? (e) => handleDrop(e, item.key) : undefined}
        onContextMenu={(e) => handleContextMenu(e, 'item', item.key)}
        onClick={(e) => {
          e.stopPropagation();
          if (e.ctrlKey) {
            setSelectedItems((prev) => (isSelected ? prev.filter((k) => k !== item.key) : [...prev, item.key]));
          } else if (e.shiftKey && selectedItems.length) {
            setSelectedItems((prev) => [...prev, item.key]);
          } else {
            setSelectedItems([item.key]);
          }
        }}
        onDoubleClick={() => {
          if (isEditing) return;
          if (type === 'folder') handleNavigate(item.key);
          else handlePreview(item.key);
        }}
        style={{
          width: viewMode === 'grid' ? 100 : '100%',
          padding: 8,
          margin: viewMode === 'grid' ? 8 : 0,
          textAlign: viewMode === 'grid' ? 'center' : 'left',
          cursor: 'pointer',
          borderRadius: 4,
          backgroundColor: isSelected ? '#e6f7ff' : 'transparent',
          border: isSelected ? '1px solid #1890ff' : '1px solid transparent',
          display: viewMode === 'list' ? 'flex' : 'block',
          alignItems: 'center',
          userSelect: 'none',
        }}
      >
        <div style={{ marginBottom: viewMode === 'grid' ? 4 : 0, marginRight: viewMode === 'list' ? 12 : 0 }}>
          {React.cloneElement(icon, { style: { fontSize: viewMode === 'grid' ? 48 : 24, color: type === 'folder' ? '#1890ff' : '#555' } })}
        </div>
        {isEditing ? (
          <Input
            ref={inputRef}
            size="small"
            value={tempName}
            onChange={(e) => setTempName(e.target.value)}
            onBlur={() => (newItemType ? finishCreateFolder() : finishRename())}
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.stopPropagation()}
            style={{ width: viewMode === 'grid' ? '100%' : 300 }}
          />
        ) : (
          <div style={{ wordBreak: 'break-word', fontSize: 12 }}>{item.title || item.name}</div>
        )}
      </div>
    );
  };

  const renderNewFolderPlaceholder = () => {
    if (newItemType !== 'folder') return null;
    return (
      <div
        style={{
          width: viewMode === 'grid' ? 100 : '100%',
          padding: 8,
          margin: viewMode === 'grid' ? 8 : 0,
          textAlign: viewMode === 'grid' ? 'center' : 'left',
          borderRadius: 4,
          border: '1px solid #1890ff',
          display: viewMode === 'list' ? 'flex' : 'block',
          alignItems: 'center',
        }}
      >
        <div style={{ marginBottom: viewMode === 'grid' ? 4 : 0, marginRight: viewMode === 'list' ? 12 : 0 }}>
          <FolderFilled style={{ fontSize: viewMode === 'grid' ? 48 : 24, color: '#1890ff' }} />
        </div>
        <Input
          ref={inputRef}
          size="small"
          value={tempName}
          onChange={(e) => setTempName(e.target.value)}
          onBlur={finishCreateFolder}
          onClick={(e) => e.stopPropagation()}
          onKeyDown={(e) => e.stopPropagation()}
          style={{ width: viewMode === 'grid' ? '100%' : 300 }}
        />
      </div>
    );
  };

  const currentFolders = folders.filter((f) => f.parent === currentFolder);
  const currentFiles = files[currentFolder] || [];

  const getContextMenuItems = () => {
    if (contextMenu?.type === 'container') {
      return [
        { key: 'new_folder', label: 'Create Folder', icon: <FolderFilled /> },
        { key: 'upload', label: 'Upload File...', icon: <UploadOutlined /> },
      ];
    }
    const items = [];
    // Only show preview for files, not folders
    if (selectedItems.length === 1) {
      const selectedKey = selectedItems[0];
      const isFolder = folders.some((f) => f.key === selectedKey);
      if (!isFolder) {
        items.push({ key: 'preview', label: 'Preview', icon: <EyeOutlined /> });
      }
    }
    items.push(
      { key: 'rename', label: 'Rename', icon: <FileTextOutlined />, disabled: selectedItems.length > 1 },
      { key: 'copy', label: `Copy${selectedItems.length > 1 ? ` (${selectedItems.length})` : ''}`, icon: <FileOutlined /> },
      { key: 'delete', label: `Delete${selectedItems.length > 1 ? ` (${selectedItems.length})` : ''}`, danger: true, icon: <FileOutlined /> },
      { type: 'divider' },
      { key: 'properties', label: 'Properties', icon: <FileTextOutlined /> }
    );
    return items;
  };

  const handleUploadClick = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.multiple = true;
    input.onchange = async (e) => {
      const filesSelected = Array.from(e.target.files);
      for (const file of filesSelected) {
        const form = new FormData();
        form.append('file', file);
        form.append('path', currentFolder);
        try {
          const res = await axios.post(`${API_BASE}/files/upload`, form, {
            headers: { 'Content-Type': 'multipart/form-data' },
          });
          const newFile = res.data;
          setFiles((prev) => ({
            ...prev,
            [currentFolder]: [...(prev[currentFolder] || []), { key: String(newFile.id), name: newFile.name, size: newFile.size, type: newFile.type }],
          }));
          message.success(`${file.name} uploaded`);
        } catch (err) {
          console.error('Upload error', err);
          message.error(`Failed to upload ${file.name}`);
        }
      }
    };
    input.click();
  };

  return (
    <div
      style={{ height: '100%', display: 'flex', flexDirection: 'column' }}
      onClick={(e) => {
        if (isDragSelecting.current) {
          isDragSelecting.current = false;
          return;
        }
        setSelectedItems([]);
        setContextMenu(null);
      }}
      onContextMenu={(e) => handleContextMenu(e, 'container')}
    >
      {/* Toolbar & Breadcrumbs */}
      <div style={{ padding: '12px 0', borderBottom: '1px solid #f0f0f0', display: 'flex', gap: 16, alignItems: 'center' }}>
        <Button icon={<ArrowUpOutlined />} onClick={handleUp} disabled={currentFolder === 'root'} size="small" />
        <Breadcrumb style={{ flex: 1 }}>
          {getBreadcrumbs().map((f) => (
            <Breadcrumb.Item key={f.key} onClick={() => handleNavigate(f.key)} style={{ cursor: 'pointer' }}>
              {f.key === 'root' ? <HomeOutlined /> : f.title}
            </Breadcrumb.Item>
          ))}
        </Breadcrumb>
        <Button
          icon={viewMode === 'grid' ? <BarsOutlined /> : <AppstoreOutlined />}
          onClick={() => setViewMode(viewMode === 'grid' ? 'list' : 'grid')}
          title={viewMode === 'grid' ? 'Switch to List View' : 'Switch to Grid View'}
        />
      </div>

      {/* Content Area */}
      <div
        ref={containerRef}
        className="file-manager-content"
        style={{ flex: 1, overflow: 'auto', display: 'flex', flexWrap: 'wrap', alignContent: 'flex-start', position: 'relative', flexDirection: viewMode === 'list' ? 'column' : 'row' }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onDragOver={handleDragOver}
        onDrop={(e) => handleDrop(e, currentFolder)}
      >
        {currentFolders.length === 0 && currentFiles.length === 0 && !newItemType && (
          <div style={{ width: '100%', marginTop: 64, pointerEvents: 'none' }}>
            <Empty description="Empty Folder" />
          </div>
        )}
        {currentFolders.map((f) => renderItem(f, 'folder'))}
        {renderNewFolderPlaceholder()}
        {currentFiles.map((f) => renderItem(f, 'file'))}
        {selectionBox && (
          <div
            style={{
              position: 'absolute',
              left: Math.min(selectionBox.startX, selectionBox.currentX),
              top: Math.min(selectionBox.startY, selectionBox.currentY),
              width: Math.abs(selectionBox.currentX - selectionBox.startX),
              height: Math.abs(selectionBox.currentY - selectionBox.startY),
              backgroundColor: 'rgba(24, 144, 255, 0.2)',
              border: '1px solid #1890ff',
              pointerEvents: 'none',
              zIndex: 100,
            }}
          />
        )}
      </div>

      {/* Context Menu */}
      {contextMenu && (
        <div
          style={{
            position: 'fixed',
            top: contextMenu.y,
            left: contextMenu.x,
            zIndex: 1000,
            background: '#fff',
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
            borderRadius: 4,
            border: '1px solid #f0f0f0',
          }}
        >
          <Menu
            selectable={false}
            onClick={({ key }) => {
              setContextMenu(null);
              if (key === 'new_folder') startCreateFolder();
              if (key === 'upload') handleUploadClick();
              if (key === 'rename') {
                const item = folders.find((f) => f.key === contextMenu.key) || (files[currentFolder] || []).find((f) => f.key === contextMenu.key);
                startRename(contextMenu.key, item.title || item.name);
              }
              if (key === 'copy') handleCopy(selectedItems.length > 0 ? selectedItems : [contextMenu.key]);
              if (key === 'delete') handleDelete(selectedItems.length > 0 ? selectedItems : [contextMenu.key]);
              if (key === 'preview') handlePreview(contextMenu.key);
              if (key === 'properties') handleProperties(selectedItems.length > 0 ? selectedItems : [contextMenu.key]);
            }}
            items={getContextMenuItems()}
          />
        </div>
      )}

      {/* Preview Modal */}
      <Modal
        title={previewFile?.name}
        open={!!previewFile}
        onCancel={() => setPreviewFile(null)}
        footer={null}
        width={800}
      >
        {previewFile && (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 300 }}>
            {previewFile.type?.startsWith('image') ? (
              <Image src="https://via.placeholder.com/600x400?text=Image+Preview+Placeholder" alt={previewFile.name} style={{ maxWidth: '100%', maxHeight: 600 }} />
            ) : (
              <div style={{ padding: 20, background: '#f5f5f5', width: '100%', borderRadius: 8 }}>
                <pre style={{ whiteSpace: 'pre-wrap' }}>{previewFile.name === 'readme.txt' ? "This is a dummy text file content.\n\nIn a real app, this would fetch the file content from the server." : "Preview not available for this file type."}</pre>
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* Properties Modal */}
      <Modal
        title="Properties"
        open={!!propertiesData}
        onCancel={() => setPropertiesData(null)}
        footer={[
          <Button key="close" type="primary" onClick={() => setPropertiesData(null)}>
            Close
          </Button>,
        ]}
        width={500}
      >
        {propertiesData && propertiesData.type === 'single' && (
          <div style={{ padding: '16px 0' }}>
            <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
              {propertiesData.isFolder ? (
                <FolderFilled style={{ fontSize: 48, color: '#1890ff' }} />
              ) : (
                <FileOutlined style={{ fontSize: 48, color: '#555' }} />
              )}
              <div>
                <div style={{ fontSize: 18, fontWeight: 'bold', marginBottom: 4 }}>{propertiesData.name}</div>
                <div style={{ color: '#888', fontSize: 12 }}>{propertiesData.isFolder ? 'Folder' : 'File'}</div>
              </div>
            </div>
            <div style={{ borderTop: '1px solid #f0f0f0', paddingTop: 16 }}>
              <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontWeight: 500 }}>Type:</span>
                <span>{propertiesData.fileType}</span>
              </div>
              <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontWeight: 500 }}>Size:</span>
                <span>{propertiesData.size}</span>
              </div>
              <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontWeight: 500 }}>Created:</span>
                <span>{propertiesData.created}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontWeight: 500 }}>Modified:</span>
                <span>{propertiesData.modified}</span>
              </div>
            </div>
          </div>
        )}
        {propertiesData && propertiesData.type === 'multiple' && (
          <div style={{ padding: '16px 0' }}>
            <div style={{ fontSize: 16, fontWeight: 'bold', marginBottom: 16 }}>Selection Summary</div>
            <div style={{ borderTop: '1px solid #f0f0f0', paddingTop: 16 }}>
              <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontWeight: 500 }}>Total Items:</span>
                <span>{propertiesData.totalCount}</span>
              </div>
              <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontWeight: 500 }}>Folders:</span>
                <span>{propertiesData.folderCount}</span>
              </div>
              <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontWeight: 500 }}>Files:</span>
                <span>{propertiesData.fileCount}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontWeight: 500 }}>Total Size:</span>
                <span>{propertiesData.totalSize}</span>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

export default FilesManager;
