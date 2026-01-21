import React, { useState, useContext, useEffect } from 'react'
import { Button, Tabs, Input, Space, Typography, message } from 'antd'
import {
  ArrowRightOutlined,
  InboxOutlined,
  ReloadOutlined
} from '@ant-design/icons'
import { AppContext } from '../contexts/GlobalContext'
import { getNeuroglancerViewer } from '../utils/api'
import UnifiedFileInput from '../components/UnifiedFileInput'

const { Title } = Typography

function Visualization(props) {
  const { viewers, setViewers } = props
  const context = useContext(AppContext)
  const [activeKey, setActiveKey] = useState(
    viewers.length > 0 ? viewers[0].key : null
  )

  // Input states
  const [currentImage, setCurrentImage] = useState(null)
  const [currentLabel, setCurrentLabel] = useState(null)
  const [scales, setScales] = useState('30,6,6')
  const [isLoading, setIsLoading] = useState(false)

  // Update file list options - No longer needed for UnifiedFileInput but keeping context access
  const { files } = context

  const handleImageChange = (value) => {
    console.log(`selected image:`, value)
    setCurrentImage(value)
  }

  const handleLabelChange = (value) => {
    console.log(`selected label:`, value)
    setCurrentLabel(value)
  }

  const handleInputScales = (event) => {
    setScales(event.target.value)
  }

  // Helper to get path string from potential object
  const getPath = (val) => {
    if (!val) return '';
    if (typeof val === 'string') return val;
    return val.path || '';
  }

  // Helper to get display string from potential object
  const getDisplay = (val) => {
    if (!val) return '';
    if (typeof val === 'string') return val;
    return val.display || val.path || '';
  }

  const fetchNeuroglancerViewer = async () => {
    const imagePath = getPath(currentImage);
    const labelPath = getPath(currentLabel);

    if (!imagePath) {
      message.error('Please select an image')
      return
    }

    setIsLoading(true)
    try {
      const scalesArray = scales.split(',').map(Number)
      // Use path string for ID generation
      const viewerId = imagePath + (labelPath || '') + JSON.stringify(scalesArray)

      let updatedViewers = viewers
      const exists = viewers.find(
        (viewer) => viewer.key === viewerId
      )

      if (exists) {
        updatedViewers = viewers.filter((viewer) => viewer.key !== viewerId)
      }

      const res = await getNeuroglancerViewer(
        imagePath,
        labelPath,
        scalesArray
      )

      const newUrl = res.replace(/\/\/[^:/]+/, '//localhost')
      console.log('Current Viewer at ', newUrl)

      // Extract name from path for title
      const getImageName = (val) => {
        const display = getDisplay(val);
        if (!display) return '';
        const parts = display.split(/[/\\]/);
        return parts[parts.length - 1];
      };

      const newViewers = [
        ...updatedViewers,
        {
          key: viewerId,
          title: getImageName(currentImage) + (currentLabel ? ' & ' + getImageName(currentLabel) : ''),
          viewer: newUrl
        }
      ]

      setViewers(newViewers)
      setActiveKey(viewerId)

      setIsLoading(false)
    } catch (e) {
      console.log(e)
      setIsLoading(false)
      message.error('Failed to load viewer')
    }
  }

  const handleEdit = (targetKey, action) => {
    if (action === 'remove') {
      remove(targetKey)
    }
  }

  const remove = (targetKey) => {
    let newActiveKey = activeKey
    let lastIndex = -1
    viewers.forEach((item, i) => {
      if (item.key === targetKey) {
        lastIndex = i - 1
      }
    })
    const newPanes = viewers.filter((item) => item.key !== targetKey)
    if (newPanes.length && newActiveKey === targetKey) {
      if (lastIndex >= 0) {
        newActiveKey = newPanes[lastIndex].key
      } else {
        newActiveKey = newPanes[0].key
      }
    }
    setViewers(newPanes)
    setActiveKey(newActiveKey)
  }

  const handleChange = (newActiveKey) => {
    setActiveKey(newActiveKey)
  }

  const refreshViewer = (key) => {
    const updatedViewers = viewers.map((viewer) => {
      if (viewer.key === key) {
        return { ...viewer, viewer: viewer.viewer + '?refresh=' + new Date().getTime() }
      }
      return viewer
    })
    setViewers(updatedViewers)
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Input Section */}
      <div style={{ padding: '16px', background: '#f5f5f5', borderRadius: '8px', marginBottom: '16px' }}>
        <Space wrap align="end" size="large">
          <div>
            <Title level={5} style={{ margin: '0 0 8px 0' }}>Image</Title>
            <UnifiedFileInput
              placeholder='Please select or input image path'
              onChange={handleImageChange}
              value={currentImage}
              style={{ width: 240 }}
            />
          </div>

          <div>
            <Title level={5} style={{ margin: '0 0 8px 0' }}>Label</Title>
            <UnifiedFileInput
              placeholder='Please select or input label path'
              onChange={handleLabelChange}
              value={currentLabel}
              style={{ width: 240 }}
            />
          </div>

          <div>
            <Title level={5} style={{ margin: '0 0 8px 0' }}>Scales (z,y,x)</Title>
            <Input
              placeholder='30,6,6'
              value={scales}
              onChange={handleInputScales}
              style={{ width: 180 }}
            />
          </div>

          <Button
            type='primary'
            onClick={fetchNeuroglancerViewer}
            icon={<ArrowRightOutlined />}
            loading={isLoading}
          >
            Visualize
          </Button>
        </Space>
      </div>

      {/* Viewers Section */}
      <div style={{ flex: 1, minHeight: 0 }}>
        {viewers.length > 0 ? (
          <Tabs
            closeIcon
            type='editable-card'
            hideAdd
            onEdit={handleEdit}
            activeKey={activeKey}
            onChange={handleChange}
            style={{ height: '100%' }}
            items={viewers.map((viewer) => ({
              label: (
                <span>
                  {viewer.title}
                  <Button
                    type='link'
                    icon={<ReloadOutlined />}
                    onClick={(e) => {
                      e.stopPropagation()
                      refreshViewer(viewer.key)
                    }}
                  />
                </span>
              ),
              key: viewer.key,
              children: (
                <div style={{ height: '100%' }}>
                  <iframe
                    title='Viewer Display'
                    width='100%'
                    height='100%'
                    frameBorder='0'
                    scrolling='no'
                    src={viewer.viewer}
                    style={{ height: '100%', minHeight: 360, border: 0 }}
                  />
                </div>
              )
            }))}
          />
        ) : (
          <div style={{ textAlign: 'center', padding: '40px', color: '#999' }}>
            <InboxOutlined style={{ fontSize: '48px', marginBottom: '16px' }} />
            <p>Select an image and click Visualize to get started</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default Visualization
