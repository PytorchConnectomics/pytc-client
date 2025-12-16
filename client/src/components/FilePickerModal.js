import React, { useState, useEffect } from 'react';
import { Modal, List, Breadcrumb, Button, Spin, message } from 'antd';
import { FolderFilled, FileOutlined, HomeOutlined, ArrowUpOutlined } from '@ant-design/icons';
import apiClient from '../services/apiClient';

const FilePickerModal = ({ visible, onCancel, onSelect, title = "Select File", selectionType = 'file' }) => {
  const [currentPath, setCurrentPath] = useState('root');
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [folders, setFolders] = useState([]); // To track folder structure for breadcrumbs

  useEffect(() => {
    if (visible) {
      fetchFiles();
    }
  }, [visible, currentPath]);

  const fetchFiles = async () => {
    setLoading(true);
    try {
      const res = await apiClient.get('/files');
      const allFiles = res.data;

      // Filter items for current path
      const currentItems = allFiles.filter(f => {
        if (currentPath === 'root') {
          return f.path === 'root' || !f.path;
        }
        return f.path === currentPath;
      });

      // Sort: Folders first, then files
      currentItems.sort((a, b) => {
        if (a.is_folder === b.is_folder) return a.name.localeCompare(b.name);
        return a.is_folder ? -1 : 1;
      });

      setItems(currentItems);
    } catch (error) {
      console.error('Failed to load files:', error);
      message.error('Failed to load files');
    } finally {
      setLoading(false);
    }
  };

  const handleItemClick = (item) => {
    if (item.is_folder) {
      setCurrentPath(String(item.id));
    } else {
      // It's a file
      if (selectionType === 'file') {
        onSelect(item);
      }
    }
  };

  const handleNavigateUp = () => {
    if (currentPath === 'root') return;
    // ... navigation logic ...
  };

  // Refactored fetch to get all files once
  const [allData, setAllData] = useState([]);

  useEffect(() => {
    if (visible) {
      loadAllData();
    }
  }, [visible]);

  const loadAllData = async () => {
    setLoading(true);
    try {
      const res = await apiClient.get('/files');
      setAllData(res.data);
    } catch (error) {
      message.error('Failed to load files');
    } finally {
      setLoading(false);
    }
  };

  // Derive items for current view
  useEffect(() => {
    const filtered = allData.filter(f => {
      if (currentPath === 'root') return f.path === 'root' || !f.path;
      return String(f.path) === currentPath;
    });

    filtered.sort((a, b) => {
      if (a.is_folder === b.is_folder) return a.name.localeCompare(b.name);
      return a.is_folder ? -1 : 1;
    });

    setItems(filtered);
  }, [currentPath, allData]);

  const getParentPath = () => {
    if (currentPath === 'root') return null;
    const currentFolderObj = allData.find(f => String(f.id) === currentPath);
    return currentFolderObj ? (currentFolderObj.path || 'root') : 'root';
  };

  const goUp = () => {
    const parent = getParentPath();
    if (parent) setCurrentPath(parent);
  };

  const getBreadcrumbs = () => {
    const parts = [];
    let curr = currentPath;
    while (curr && curr !== 'root') {
      const folder = allData.find(f => String(f.id) === curr);
      if (folder) {
        parts.unshift({ id: String(folder.id), name: folder.name });
        curr = folder.path;
      } else {
        break;
      }
    }
    parts.unshift({ id: 'root', name: 'Home' });
    return parts;
  };

  const constructFullPath = (item) => {
    if (!item) return '';
    if (item.path === 'root' || !item.path) return item.name;

    const parts = [item.name];
    let currParentId = item.path;

    // Safety break to prevent infinite loops
    let attempts = 0;
    while (currParentId && currParentId !== 'root' && attempts < 100) {
      const parent = allData.find(f => String(f.id) === currParentId);
      if (parent) {
        parts.unshift(parent.name);
        currParentId = parent.path;
      } else {
        break;
      }
      attempts++;
    }
    return parts.join('/');
  };

  const handleSelectCurrentDirectory = () => {
    // Construct path for current directory
    if (currentPath === 'root') {
      onSelect({ name: '', path: 'root', is_folder: true, logical_path: '' }); // Root
      return;
    }
    const currentFolder = allData.find(f => String(f.id) === currentPath);
    if (currentFolder) {
      const fullPath = constructFullPath(currentFolder);
      onSelect({ ...currentFolder, logical_path: fullPath });
    }
  };

  return (
    <Modal
      title={title}
      open={visible}
      onCancel={onCancel}
      footer={
        selectionType === 'directory' ? (
          <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '10px 16px' }}>
            <Button onClick={onCancel} style={{ marginRight: 8 }}>Cancel</Button>
            <Button type="primary" onClick={handleSelectCurrentDirectory}>
              Select Current Directory
            </Button>
          </div>
        ) : null
      }
      width={600}
      bodyStyle={{ padding: 0 }}
    >
      <div style={{ padding: '12px', borderBottom: '1px solid #f0f0f0', display: 'flex', alignItems: 'center' }}>
        <Button
          icon={<ArrowUpOutlined />}
          onClick={goUp}
          disabled={currentPath === 'root'}
          style={{ marginRight: '12px' }}
        />
        <Breadcrumb>
          {getBreadcrumbs().map(b => (
            <Breadcrumb.Item key={b.id}>
              <a onClick={() => setCurrentPath(b.id)}>{b.name}</a>
            </Breadcrumb.Item>
          ))}
        </Breadcrumb>
      </div>

      <div style={{ height: '400px', overflow: 'auto' }}>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '40px' }}>
            <Spin />
          </div>
        ) : (
          <List
            dataSource={items}
            renderItem={item => (
              <List.Item
                style={{ cursor: 'pointer', padding: '8px 16px' }}
                className="file-picker-item"
                onClick={() => {
                  if (item.is_folder) {
                    setCurrentPath(String(item.id));
                  } else {
                    if (selectionType === 'file') {
                      const fullPath = constructFullPath(item);
                      onSelect({ ...item, logical_path: fullPath });
                    }
                  }
                }}
                actions={[
                  selectionType === 'file' && !item.is_folder && (
                    <Button type="link" size="small" onClick={(e) => {
                      e.stopPropagation();
                      const fullPath = constructFullPath(item);
                      onSelect({ ...item, logical_path: fullPath });
                    }}>Select</Button>
                  ),
                  selectionType === 'directory' && item.is_folder && (
                    <Button type="link" size="small" onClick={(e) => {
                      e.stopPropagation();
                      const fullPath = constructFullPath(item);
                      onSelect({ ...item, logical_path: fullPath });
                    }}>Select</Button>
                  )
                ]}
              >
                <List.Item.Meta
                  avatar={item.is_folder ? <FolderFilled style={{ color: '#1890ff', fontSize: '20px' }} /> : <FileOutlined style={{ fontSize: '20px' }} />}
                  title={item.name}
                  description={item.size ? item.size : null}
                />
              </List.Item>
            )}
          />
        )}
      </div>
    </Modal>
  );
};

export default FilePickerModal;
