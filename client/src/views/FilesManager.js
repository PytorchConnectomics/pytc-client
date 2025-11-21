import React, { useState } from 'react';
import { Card, Button, Input, Modal, List, Upload, Checkbox, message } from 'antd';
import { PlusOutlined, DeleteOutlined, EditOutlined, FolderOpenOutlined, FileImageOutlined, UploadOutlined } from '@ant-design/icons';

function initialFolders() {
  return [
    { key: 'root', title: 'My Drive', children: [] },
  ];
}

function FilesManager() {
  const [folders, setFolders] = useState(initialFolders());
  const [selectedFolder, setSelectedFolder] = useState('root');
  const [files, setFiles] = useState({ root: [] });
  const [showFolderModal, setShowFolderModal] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [renameFolderKey, setRenameFolderKey] = useState(null);
  const [renameFolderName, setRenameFolderName] = useState('');
  const [selectedFiles, setSelectedFiles] = useState([]);

  // Folder helpers
  const addFolder = () => {
    if (!newFolderName.trim()) return;
    const key = `${Date.now()}`;
    setFolders(folders => [
      ...folders,
      { key, title: newFolderName, children: [] },
    ]);
    setFiles(f => ({ ...f, [key]: [] }));
    setNewFolderName('');
    setShowFolderModal(false);
    message.success('Folder created');
  };

  const deleteFolder = key => {
    if (key === 'root') return;
    setFolders(folders => folders.filter(f => f.key !== key));
    setFiles(f => {
      const copy = { ...f };
      delete copy[key];
      return copy;
    });
    if (selectedFolder === key) setSelectedFolder('root');
    message.success('Folder deleted');
  };

  const renameFolder = () => {
    setFolders(folders => folders.map(f => f.key === renameFolderKey ? { ...f, title: renameFolderName } : f));
    setRenameFolderKey(null);
    setRenameFolderName('');
    message.success('Folder renamed');
  };

  // File helpers
  const handleUpload = info => {
    if (info.file.status === 'done' || info.file.originFileObj) {
      const fileMeta = {
        key: `${Date.now()}`,
        name: info.file.name,
        size: info.file.size,
        type: info.file.type,
        lastModified: info.file.lastModified,
      };
      setFiles(f => ({ ...f, [selectedFolder]: [...(f[selectedFolder] || []), fileMeta] }));
      message.success('File uploaded');
    }
  };

  const handleDeleteFile = key => {
    setFiles(f => ({
      ...f,
      [selectedFolder]: (f[selectedFolder] || []).filter(file => file.key !== key),
    }));
    setSelectedFiles(sel => sel.filter(k => k !== key));
    message.success('File deleted');
  };

  const handleRenameFile = (key, newName) => {
    setFiles(f => ({
      ...f,
      [selectedFolder]: (f[selectedFolder] || []).map(file => file.key === key ? { ...file, name: newName } : file),
    }));
    message.success('File renamed');
  };

  const handleMultiDelete = () => {
    setFiles(f => ({
      ...f,
      [selectedFolder]: (f[selectedFolder] || []).filter(file => !selectedFiles.includes(file.key)),
    }));
    setSelectedFiles([]);
    message.success('Files deleted');
  };

  // UI
  return (
    <Card style={{ maxWidth: 1000, margin: '32px auto', minHeight: 500 }}>
      <div style={{ display: 'flex', gap: 32 }}>
        {/* Folder sidebar */}
        <div style={{ minWidth: 220 }}>
          <div style={{ marginBottom: 12, fontWeight: 'bold' }}>Folders</div>
          <List
            bordered
            dataSource={folders}
            renderItem={folder => (
              <List.Item
                style={{ background: selectedFolder === folder.key ? '#e6f7ff' : undefined }}
                actions={folder.key !== 'root' ? [
                  <Button size='small' icon={<EditOutlined />} onClick={() => { setRenameFolderKey(folder.key); setRenameFolderName(folder.title); }}>Rename</Button>,
                  <Button size='small' danger icon={<DeleteOutlined />} onClick={() => deleteFolder(folder.key)}>Delete</Button>,
                ] : []}
                onClick={() => setSelectedFolder(folder.key)}
              >
                <FolderOpenOutlined style={{ marginRight: 8 }} />{folder.title}
              </List.Item>
            )}
          />
          <Button type='dashed' block icon={<PlusOutlined />} style={{ marginTop: 12 }} onClick={() => setShowFolderModal(true)}>
            New Folder
          </Button>
        </div>
        {/* Files in folder */}
        <div style={{ flex: 1 }}>
          <div style={{ marginBottom: 12, fontWeight: 'bold' }}>Files in "{folders.find(f => f.key === selectedFolder)?.title}"</div>
          <Upload
            showUploadList={false}
            beforeUpload={() => false}
            onChange={handleUpload}
            multiple
          >
            <Button icon={<UploadOutlined />}>Upload Files</Button>
          </Upload>
          {selectedFiles.length > 0 && (
            <Button danger style={{ marginLeft: 12 }} onClick={handleMultiDelete}>Delete Selected</Button>
          )}
          <List
            style={{ marginTop: 16 }}
            bordered
            dataSource={files[selectedFolder] || []}
            renderItem={file => (
              <List.Item
                actions={[
                  <Button size='small' icon={<EditOutlined />} onClick={() => {
                    Modal.confirm({
                      title: 'Rename File',
                      content: <Input defaultValue={file.name} onChange={e => file.newName = e.target.value} />,
                      onOk: () => handleRenameFile(file.key, file.newName || file.name),
                    });
                  }}>Rename</Button>,
                  <Button size='small' danger icon={<DeleteOutlined />} onClick={() => handleDeleteFile(file.key)}>Delete</Button>,
                ]}
              >
                <Checkbox
                  checked={selectedFiles.includes(file.key)}
                  onChange={e => {
                    setSelectedFiles(sel => e.target.checked ? [...sel, file.key] : sel.filter(k => k !== file.key));
                  }}
                  style={{ marginRight: 8 }}
                />
                <FileImageOutlined style={{ marginRight: 8 }} />
                <span style={{ fontWeight: 'bold' }}>{file.name}</span>
                <span style={{ marginLeft: 12, color: '#888' }}>{file.size} bytes</span>
              </List.Item>
            )}
          />
        </div>
      </div>
      {/* Folder modals */}
      <Modal
        title='New Folder'
        open={showFolderModal}
        onCancel={() => setShowFolderModal(false)}
        onOk={addFolder}
      >
        <Input value={newFolderName} onChange={e => setNewFolderName(e.target.value)} placeholder='Folder name' />
      </Modal>
      <Modal
        title='Rename Folder'
        open={!!renameFolderKey}
        onCancel={() => setRenameFolderKey(null)}
        onOk={renameFolder}
      >
        <Input value={renameFolderName} onChange={e => setRenameFolderName(e.target.value)} placeholder='New folder name' />
      </Modal>
    </Card>
  );
}

export default FilesManager;
