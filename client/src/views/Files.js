import React, { useContext, useState } from 'react'
import { UserContext } from '../contexts/UserContext'
import { Card, Typography, List, Button, Upload, Modal, Input, message } from 'antd'
import { UploadOutlined, EditOutlined, DeleteOutlined, FileOutlined } from '@ant-design/icons'

const { Title } = Typography

function Files () {
  const { getCurrentUser, setUserFile } = useContext(UserContext)
  const user = getCurrentUser()
  const files = user?.files || [null, null, null]
  const [renameIdx, setRenameIdx] = useState(null)
  const [renameVal, setRenameVal] = useState('')

  const handleUpload = (idx, info) => {
    if (info.file.status === 'done' || info.file.status === 'removed' || info.file.originFileObj) {
      const fileMeta = {
        name: info.file.name,
        size: info.file.size,
        type: info.file.type,
        lastModified: info.file.lastModified,
      }
      setUserFile(idx, fileMeta)
      message.success('File uploaded')
    }
  }

  const handleDelete = (idx) => {
    setUserFile(idx, null)
    message.success('File deleted')
  }

  const openRename = (idx) => {
    setRenameIdx(idx)
    setRenameVal(files[idx]?.name || '')
  }
  const handleRename = () => {
    if (renameIdx !== null && renameVal) {
      const file = files[renameIdx]
      if (file) {
        setUserFile(renameIdx, { ...file, name: renameVal })
        message.success('File renamed')
      }
    }
    setRenameIdx(null)
    setRenameVal('')
  }

  return (
    <Card style={{ maxWidth: 700, margin: '32px auto' }}>
      <Title level={3}>Your Files</Title>
      <List
        grid={{ gutter: 16, column: 3 }}
        dataSource={[0, 1, 2]}
        renderItem={idx => {
          const file = files[idx]
          return (
            <List.Item>
              <Card
                size='small'
                title={<span><FileOutlined /> File {idx + 1}</span>}
                actions={[
                  <Upload
                    showUploadList={false}
                    beforeUpload={() => false}
                    onChange={info => handleUpload(idx, info)}
                  >
                    <Button icon={<UploadOutlined />}>Upload</Button>
                  </Upload>,
                  file ? <Button icon={<EditOutlined />} onClick={() => openRename(idx)}>Rename</Button> : null,
                  file ? <Button danger icon={<DeleteOutlined />} onClick={() => handleDelete(idx)}>Delete</Button> : null
                ]}
              >
                {file ? (
                  <div>
                    <div><strong>Name:</strong> {file.name}</div>
                    <div><strong>Size:</strong> {file.size} bytes</div>
                    <div><strong>Type:</strong> {file.type}</div>
                  </div>
                ) : (
                  <div style={{ color: '#888' }}><em>Empty</em></div>
                )}
              </Card>
            </List.Item>
          )
        }}
      />
      <Modal
        title='Rename File'
        open={renameIdx !== null}
        onCancel={() => setRenameIdx(null)}
        onOk={handleRename}
      >
        <Input value={renameVal} onChange={e => setRenameVal(e.target.value)} placeholder='New file name' />
      </Modal>
    </Card>
  )
}

export default Files
