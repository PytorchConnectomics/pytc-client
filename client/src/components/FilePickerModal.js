import React, { useState, useEffect } from 'react';
import { Modal, List, Breadcrumb, Button, Spin, message } from 'antd';
import { FolderFilled, FileOutlined, HomeOutlined, ArrowUpOutlined } from '@ant-design/icons';
import apiClient from '../services/apiClient';

const FilePickerModal = ({ visible, onCancel, onSelect, title = "Select File" }) => {
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

      // Update folders list for breadcrumbs if needed (simplified here)
      // In a real app, we might need a better way to build breadcrumbs from flat list
      // For now, we'll just rely on the path string or build it up
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
      // It's a file, select it? Or just highlight?
      // For now, let's just select it immediately or maybe we want a "Select" button
      // The user might want to select a folder too.
      // Let's assume we select on double click or have a select button.
      // For this implementation: Single click selects (highlights), Double click enters folder or chooses file.
    }
  };

  const handleNavigateUp = () => {
    // This is tricky with flat structure + ID based paths.
    // We need to find the parent of the current folder.
    // Since we don't have the full tree easily, we might need to fetch all folders or store parent info.
    // The backend 'files' endpoint returns everything.
    // Let's find the current folder object to get its parent.
    if (currentPath === 'root') return;

    // We need to find the folder object that corresponds to currentPath
    // But we only have the items IN the current path.
    // We should probably fetch ALL files once or change the API.
    // Assuming we fetch ALL files in fetchFiles (which we do):

    // Optimisation: Fetch all once and filter locally?
    // The current fetchFiles fetches ALL files every time (based on FilesManager logic).
    // Let's optimize: Fetch all once on mount/visible, then filter locally.
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

  return (
    <Modal
      title={title}
      open={visible}
      onCancel={onCancel}
      footer={null}
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
                    // Select file
                    // We need to construct the full path or just return the ID/Name?
                    // The backend likely needs the full path on the server disk.
                    // But wait, the 'files' API returns metadata. Does it have the absolute path?
                    // Looking at FilesManager, it seems to use IDs for operations.
                    // But DatasetLoader expects a string path.
                    // If the backend 'files' are virtual or in a specific root, we might need the real path.
                    // Let's assume for now we return the item and let the parent handle it, 
                    // OR we assume the 'name' is relative to the storage root.
                    // Actually, for the Python backend to load it, it needs an absolute path or relative to CWD.
                    // The 'files' endpoint usually serves files from a specific directory.
                    // If the user selects a file from the "Server", it implies a file in the managed storage.
                    // We might need to ask the backend for the full path or construct it.
                    // For now, let's return the item object.
                    onSelect(item);
                  }
                }}
                actions={[
                  !item.is_folder && <Button type="link" size="small" onClick={(e) => {
                    e.stopPropagation();
                    onSelect(item);
                  }}>Select</Button>
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
