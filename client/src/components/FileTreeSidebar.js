import React, { useMemo } from "react";
import { Tree } from "antd";
import {
  FolderFilled,
  FileOutlined,
  FolderOpenFilled,
} from "@ant-design/icons";

const { DirectoryTree } = Tree;

const FileTreeSidebar = ({
  folders,
  files,
  currentFolder,
  onSelect,
  onDrop,
  onContextMenu,
  width = 250,
}) => {
  // Convert flat folders list to tree data
  const treeData = useMemo(() => {
    const buildTree = (parentId) => {
      const children = folders
        .filter((f) => f.parent === parentId)
        .map((f) => ({
          title: f.title,
          key: `folder-${f.key}`,
          isLeaf: false,
          icon: ({ expanded }) =>
            expanded ? <FolderOpenFilled /> : <FolderFilled />,
          children: buildTree(f.key),
        }));

      // Add files to tree
      if (files && files[parentId]) {
        children.push(
          ...files[parentId].map((f) => ({
            title: f.name,
            key: `file-${f.key}`,
            isLeaf: true,
            icon: <FileOutlined />,
          })),
        );
      }

      return children;
    };

    // Start with root folders (parent is 'root' or null)
    const rootNodes = folders
      .filter((f) => f.key === "root" || f.parent === null) // Handle 'root' key explicitly if it exists
      .map((f) => ({
        title: f.title,
        key: `folder-${f.key}`,
        isLeaf: false,
        icon: ({ expanded }) =>
          expanded ? <FolderOpenFilled /> : <FolderFilled />,
        children: buildTree(f.key),
      }));

    // If no explicit root node in folders, find orphans or treat 'root' as implicit
    if (rootNodes.length === 0) {
      return buildTree("root");
    }

    return rootNodes;
  }, [folders, files]);

  const onSelectHandler = (keys, info) => {
    if (keys.length > 0) {
      const key = keys[0];
      // Only navigate if it's a folder
      if (key.startsWith("folder-")) {
        onSelect(key.replace("folder-", ""));
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
        borderRight: "1px solid #f0f0f0",
        height: "100%",
        overflow: "auto",
        backgroundColor: "#fafafa",
        display: width === 0 ? "none" : "block", // Hide if collapsed
      }}
    >
      <div
        style={{
          padding: "10px 16px",
          fontWeight: "bold",
          borderBottom: "1px solid #f0f0f0",
        }}
      >
        Explorer
      </div>
      <DirectoryTree
        multiple={false}
        defaultExpandAll
        selectedKeys={[`folder-${currentFolder}`]}
        onSelect={onSelectHandler}
        treeData={treeData}
        expandAction="click"
        style={{ backgroundColor: "transparent", fontSize: 13 }}
        titleRender={(nodeData) => (
          <span
            style={{
              display: "inline-block",
              maxWidth: `calc(${width}px - 92px)`,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              verticalAlign: "middle",
              lineHeight: "22px",
            }}
            title={String(nodeData.title)}
          >
            {nodeData.title}
          </span>
        )}
        draggable
        blockNode
        onDrop={handleDrop}
        onRightClick={handleRightClick}
      />
      <style>
        {`
          .ant-tree .ant-tree-treenode {
            min-height: 28px;
            padding: 0;
          }
          .ant-tree .ant-tree-node-content-wrapper {
            min-height: 28px;
            padding: 2px 6px;
            display: flex;
            align-items: center;
            gap: 6px;
          }
          .ant-tree .ant-tree-iconEle {
            margin-right: 2px;
          }
          .ant-tree .ant-tree-switcher {
            width: 16px;
          }
          .ant-tree .ant-tree-indent-unit {
            width: 14px;
          }
          .ant-tree .ant-tree-list-holder-inner {
            gap: 0;
          }
        `}
      </style>
    </div>
  );
};

export default FileTreeSidebar;
