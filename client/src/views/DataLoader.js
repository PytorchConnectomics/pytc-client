import React, { useContext, useEffect, useState } from 'react'
import { Button, Input, Space, Typography, Upload } from 'antd'
import { InboxOutlined, EyeOutlined } from '@ant-design/icons'
import { AppContext } from '../contexts/GlobalContext'
import './DataLoader.css'

const { Title } = Typography

function DataLoader (props) {
  const context = useContext(AppContext)
  const [scales, setScales] = useState('30,6,6')
  const { fetchNeuroglancerViewer } = props

  const handleVisualizeButtonClick = async (event) => {
    event.preventDefault()
    fetchNeuroglancerViewer(
      context.currentImage,
      context.currentLabel,
      scales.split(',').map(Number)
    )
  }

  const handleImageChange = (info) => {
    const { file } = info
    if (file) {
      context.setInputImage(file)
      context.setCurrentImage(file)
    }
  };

  const handleLabelChange = (info) => {
    const { file } = info
    if (file) {
      context.setInputLabel(file)
      context.setCurrentLabel(file)
    }
  };

  const handleInputScales = (event) => {
    setScales(event.target.value)
  }

  const { files, setFileList } = context
  useEffect(() => {
    if (files) {
      setFileList(
        files.map((file) => ({
          label: file.name,
          value: file.uid
        }))
      )
    }
  }, [files, setFileList])

  return (
    <Space
      direction='vertical'
      size='small'
      align='start'
      style={{ margin: '7px', display: 'flex' }}
    >
      <Title level={5} style={{ marginBottom: '-5px' }}>
        Image
      </Title>
      <Upload.Dragger
        multiple={false}
        maxCount={1}
        onChange={handleImageChange}
      >
        <p className='ant-upload-drag-icon'>
          <InboxOutlined />
        </p>
        <p className='ant-upload-text'>
          Drag image here, or click to upload
        </p>
      </Upload.Dragger>

      <Title level={5} style={{ marginTop: '0px', marginBottom: '-5px' }}>
        Label
      </Title>
      <Upload.Dragger
        multiple={false}
        maxCount={1}
        onChange={handleLabelChange}
      >
        <p className='ant-upload-drag-icon'>
          <InboxOutlined />
        </p>
        <p className='ant-upload-text'>
          Drag label here, or click to upload
        </p>
      </Upload.Dragger>

      <Title level={5} style={{ marginTop: '0px', marginBottom: '-5px' }}>
        Scales
      </Title>
      <Input
        placeholder='Input in z, y, x order'
        allowClear
        onChange={handleInputScales}
        style={{ width: '185px' }}
      />
      <Button
        type='primary'
        onClick={handleVisualizeButtonClick}
        icon={<EyeOutlined />}
        style={{ width: '185px' }}
      >
        Visualize
      </Button>
    </Space>
  )
}

export default DataLoader
