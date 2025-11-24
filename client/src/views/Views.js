import React, { useState, useEffect } from 'react'
import DataLoader from './DataLoader'
import Visualization from '../views/Visualization'
import ModelTraining from '../views/ModelTraining'
import ModelInference from '../views/ModelInference'
import Monitoring from '../views/Monitoring'
import Chatbot from '../components/Chatbot'
import { Layout, Menu, Button } from 'antd'
import { MessageOutlined } from '@ant-design/icons'
import { getNeuroglancerViewer } from '../utils/api'

const { Content, Sider } = Layout

function Views () {
  const [current, setCurrent] = useState('visualization')
  const [viewers, setViewers] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [isInferring, setIsInferring] = useState(false)
  const [isChatOpen, setIsChatOpen] = useState(false)

  const onClick = (e) => {
    setCurrent(e.key)
  }

  const items = [
    { label: 'Visualization', key: 'visualization' },
    { label: 'Model Inference', key: 'inference' }
  ]

  const renderMenu = () => {
    if (current === 'visualization') {
      return <Visualization viewers={viewers} setViewers={setViewers} setCurrent={setCurrent} />
    } else if (current === 'training') {
      return <ModelTraining />
    } else if (current === 'monitoring') {
      return <Monitoring />
    } else if (current === 'inference') {
      return <ModelInference isInferring={isInferring} setIsInferring={setIsInferring} />
    }
  }

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
        (viewer) => viewer.key === viewerId
      )
      if (exists) {
        updatedViewers = viewers.filter((viewer) => viewer.key !== viewerId)
      }
      const res = await getNeuroglancerViewer(
        currentImage,
        currentLabel,
        scales
      )
      const newUrl = res.replace(/\/\/[^:/]+/, '//localhost')

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

  useEffect(() => { // This function makes sure that the inferring will continue when current tab changes
    if (current === 'inference' && isInferring) {
      console.log('Inference process is continuing...')
    }
  }, [current, isInferring])

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
              <DataLoader fetchNeuroglancerViewer={fetchNeuroglancerViewer} />
            </Sider>
            <Layout className='site-layout'>
              <Content
                style={{
                  margin: '0 16px'
                }}
              >
                <Menu
                  onClick={onClick}
                  selectedKeys={[current]}
                  mode='horizontal'
                  items={items}
                />
                {renderMenu()}
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
