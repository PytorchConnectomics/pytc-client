import React, { useState, useEffect } from 'react'
import DataLoader from './DataLoader'
import Visualization from '../views/Visualization'
import Chatbot from '../components/Chatbot'
import { Layout, Button } from 'antd'
import { MessageOutlined } from '@ant-design/icons'
import { getNeuroglancerViewer } from '../utils/api'

const { Content, Sider } = Layout

function Views() {
  const [viewers, setViewers] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [isInferring, setIsInferring] = useState(false)
  const [isChatOpen, setIsChatOpen] = useState(false)
  console.log(viewers)

  const [collapsed, setCollapsed] = useState(false)

  const fetchNeuroglancerViewer = async (
    currentImage,
    currentLabel,
    scales
  ) => {
    setIsLoading(true)
    try {
      const viewerId = currentImage.uid + currentLabel.uid + JSON.stringify(scales)
      let updatedViewers = viewers
      const exists = viewers.find(
        // (viewer) => viewer.key === currentImage.uid + currentLabel.uid
        (viewer) => viewer.key === viewerId
      )
      // console.log(exists, viewers)
      if (exists) {
        updatedViewers = viewers.filter((viewer) => viewer.key !== viewerId)
      }
      const res = await getNeuroglancerViewer(
        currentImage,
        currentLabel,
        scales
      )
      const newUrl = res.replace(/\/\/[^:/]+/, '//localhost')
      console.log('Current Viewer at ', newUrl)

      setViewers([
        ...updatedViewers,
        {
          key: viewerId,
          title: currentImage.name + ' & ' + currentLabel.name,
          viewer: newUrl
        }
      ])
      setIsLoading(false)
    } catch (e) {
      console.log(e)
      setIsLoading(false)
    }
  }

  return (
    <Layout
      style={{
        minHeight: '99vh',
        minWidth: '90vw'
      }}
    >
      {isLoading
        ? (<div>Loading the viewer ...</div>)
        : (
          <>
            <Sider
              // collapsible
              collapsed={collapsed}
              onCollapse={(value) => setCollapsed(value)}
              theme='light'
              collapsedWidth='0'
            >
              <DataLoader
                fetchNeuroglancerViewer={fetchNeuroglancerViewer}
                isInferring={isInferring}
                setIsInferring={setIsInferring}
              />
            </Sider>
            <Layout className='site-layout'>
              <Content
                style={{
                  margin: '0 16px'
                }}
              >
                <Visualization viewers={viewers} setViewers={setViewers} />
              </Content>
            </Layout>
            {isChatOpen ? (
              <Sider
                width={400}
                theme='light'
              >
                <Chatbot onClose={() => setIsChatOpen(false)} />
              </Sider>
            ) : (
              <Button
                type="primary"
                shape="circle"
                icon={<MessageOutlined />}
                onClick={() => setIsChatOpen(true)}
                style={{
                  margin: '8px 8px'
                }}
              />
            )}
          </>
        )}
    </Layout>
  )
}

export default Views
