import React, { useState } from 'react'
import { Button, Tabs, Timeline } from 'antd'
import {
  EyeOutlined,
  InboxOutlined,
  ReloadOutlined,
  ScissorOutlined
} from '@ant-design/icons'

function Visualization (props) {
  const { viewers, setViewers, setCurrent } = props
  const [activeKey, setActiveKey] = useState(
    viewers.length > 0 ? viewers[0].key : null
  ) // Store the active tab key

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
    // This function refreshes the viewer specified by the key
    const updatedViewers = viewers.map((viewer) => {
      if (viewer.key === key) {
        // Refresh the viewer URL by adding a refresh request token to it
        // The refresh request token is only for node.js to force refresh the element
        // The appended token will be ignored when rendering
        return { ...viewer, viewer: viewer.viewer + '?refresh=' + new Date().getTime() }
      }
      return viewer
    })
    setViewers(updatedViewers)
  }

  return (
    <div style={{ marginTop: '20px' }}>
      {viewers.length > 0
        ? (
          <Tabs
            closeIcon
            type='editable-card'
            hideAdd
            onEdit={handleEdit}
            activeKey={activeKey}
            onChange={handleChange}
            items={viewers.map((viewer) => ({
              label: (
                <span style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '16px'}}>
                  <div>
                    <Button
                      type='link'
                      icon={<ReloadOutlined />}
                      onClick={() => refreshViewer(viewer.key)}
                    />
                    {viewer.title}
                  </div>
                  <div style={{ fontColor: 'red' }}>
                    <Button
                      type='link'
                      icon={<ScissorOutlined />}
                      onClick={() => setCurrent('inference')}
                    >
                      Segment it
                    </Button>
                  </div>
                </span>
              ),
              key: viewer.key,
              children: (
                <iframe
                  title='Viewer Display'
                  width='100%'
                  height='700'
                  frameBorder='0'
                  scrolling='no'
                  src={viewer.viewer}
                />
              )
            }))}
          />
          )
        : (
          <Timeline
            mode='left'
            items={[
              {
                children: (
                  <>
                    <InboxOutlined /> Upload your files to the left
                  </>
                )
              },
              {
                children: 'Input image scales in z, y, x order (optional)'
              },
              {
                children: (
                  <>
                    Click{' '}
                    <Button
                      type='primary'
                      size='small'
                      icon={<EyeOutlined />}
                    >
                      Visualize
                    </Button>{' '}
                      to render the image and label with Neuroglancer
                  </>
                )
              }
            ]}
          />
          )}
    </div>
  )
}

export default Visualization
