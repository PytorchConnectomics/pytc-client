import React, { useState } from 'react'
import { Button, Tabs, Timeline } from 'antd'
import {
  ArrowRightOutlined,
  DownOutlined,
  EyeOutlined,
  InboxOutlined
} from '@ant-design/icons'

function Visualization (props) {
  const { viewers, setViewers } = props
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
              label: viewer.title,
              key: viewer.key,
              children: (
                <iframe
                  title='Viewer Display'
                  width='100%'
                  height='800'
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
                    <InboxOutlined /> Upload your files
                  </>
                )
              },
              {
                children: (
                  <>
                    Input folder path of file in <EyeOutlined /> preview
                  </>
                )
              },
              {
                children: (
                  <>
                    <DownOutlined /> Select your image and label in dropdown menus
                  </>
                )
              },
              {
                children: 'Input scales of image in z,y,x order'
              },
              {
                children: (
                  <>
                    Click{' '}
                    <Button
                      type='primary'
                      size='small'
                      icon={<ArrowRightOutlined />}
                    >
                      Visualize
                    </Button>{' '}
                    button to render image and label in Neuroglancer
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
