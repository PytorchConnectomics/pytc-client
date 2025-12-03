import React, { useState, useContext } from 'react'
import { Layout, Menu, Avatar, Typography, Space, Button, Tooltip } from 'antd'
import { FolderOpenOutlined, DesktopOutlined, UserOutlined, LogoutOutlined } from '@ant-design/icons'
import FilesManager from './FilesManager'
import Workspace from './Workspace'
import { UserContext } from '../contexts/UserContext'

const { Content } = Layout
const { Text } = Typography

function Views() {
  const [current, setCurrent] = useState('files')
  const { currentUser, autoSignOut } = useContext(UserContext)

  const items = [
    { label: 'File Management', key: 'files', icon: <FolderOpenOutlined /> },
    { label: 'Work Space', key: 'workspace', icon: <DesktopOutlined /> }
  ]

  const onClick = (e) => {
    setCurrent(e.key)
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <div style={{ display: 'flex', alignItems: 'center', background: '#fff', paddingRight: 24 }}>
        <Menu
          onClick={onClick}
          selectedKeys={[current]}
          mode='horizontal'
          items={items}
          style={{ lineHeight: '64px', paddingLeft: '16px', flex: 1, borderBottom: 'none' }}
        />
        <Space size="large">
          <Space>
            <Avatar icon={<UserOutlined />} style={{ backgroundColor: '#87d068' }} />
            <Text strong>{currentUser ? currentUser.name : 'Guest'}</Text>
          </Space>
          <Tooltip title="Sign Out">
            <Button icon={<LogoutOutlined />} onClick={autoSignOut} type="text" danger />
          </Tooltip>
        </Space>
      </div>
      <Content style={{ padding: '24px', height: 'calc(100vh - 64px)', overflow: 'auto' }}>
        {current === 'files' ? <FilesManager /> : <Workspace />}
      </Content>
    </Layout>
  )
}

export default Views
