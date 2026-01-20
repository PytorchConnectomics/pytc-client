import React, { useMemo } from 'react';
import { Tree } from 'antd';
import { FolderFilled, FileOutlined, FolderOpenFilled } from '@ant-design/icons';

const { DirectoryTree } = Tree;

const FileTreeSidebar = ({ folders, files, currentFolder, onSelect, onDrop, onContextMenu, width = 250 }) => {
  // Convert flat folders list to tree data
  const treeData = useMemo(() => {
    const buildTree = (parentId) => {
      const children = folders
        .filter((f) => f.parent === parentId)
        .map((f) => ({
          title: f.title,
          key: `folder-${f.key}`,
          isLeaf: false,
          icon: ({ expanded }) => (expanded ? <FolderOpenFilled /> : <FolderFilled />),
          children: buildTree(f.key),
        }));

      // Add files to tree
      if (files && files[parentId]) {
        children.push(...files[parentId].map(f => ({
          title: f.name,
          key: `file-${f.key}`,
          isLeaf: true,
          icon: <FileOutlined />
        })));
      }

      return children;
    };

    // Start with root folders (parent is 'root' or null)
    const rootNodes = folders
      .filter((f) => f.key === 'root' || f.parent === null) // Handle 'root' key explicitly if it exists
      .map((f) => ({
        title: f.title,
        key: `folder-${f.key}`,
        isLeaf: false,
        icon: ({ expanded }) => (expanded ? <FolderOpenFilled /> : <FolderFilled />),
        children: buildTree(f.key),
      }));

    // If no explicit root node in folders, find orphans or treat 'root' as implicit
    if (rootNodes.length === 0) {
      return buildTree('root');
    }

    return rootNodes;
  }, [folders, files]);

  const onSelectHandler = (keys, info) => {
    if (keys.length > 0) {
      const key = keys[0];
      // Only navigate if it's a folder
      if (key.startsWith('folder-')) {
        onSelect(key.replace('folder-', ''));
      }
    }
  };

  const handleDrop = (info) => {
    if (onDrop) {
      onDrop(info);
    }
  };

  const handleRightClick = ({ event, node }) => {
    if (onContextMenu) {
      onContextMenu(event, node);
    }
  };

  return (
    <div
      style={{
        width: width,
        borderRight: '1px solid #f0f0f0',
        height: '100%',
        overflow: 'auto',
        backgroundColor: '#fafafa',
        display: width === 0 ? 'none' : 'block', // Hide if collapsed
      }}
    >
      <div style={{ padding: '10px 16px', fontWeight: 'bold', borderBottom: '1px solid #f0f0f0' }}>
        Explorer
      </div>
      <DirectoryTree
        multiple={false}
        defaultExpandAll
        selectedKeys={[`folder-${currentFolder}`]}
        onSelect={onSelectHandler}
        treeData={treeData}
        expandAction="click"
        style={{ backgroundColor: 'transparent' }}
        draggable
        blockNode
        onDrop={handleDrop}
        onRightClick={handleRightClick}
      />
    </div>
  );
};

export default FileTreeSidebar;
