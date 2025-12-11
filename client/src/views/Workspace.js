import React, { useState, useEffect } from 'react'
import DataLoader from './DataLoader'
import Visualization from '../views/Visualization'
import ModelTraining from '../views/ModelTraining'
import ModelInference from '../views/ModelInference'
import Monitoring from '../views/Monitoring'
import ProofReading from '../views/ProofReading'
import EHTool from '../views/EHTool'
import ProofreadingTab from '../views/ProofreadingTab'
import Chatbot from '../components/Chatbot'
import { Layout, Menu, Button } from 'antd'
import { MessageOutlined } from '@ant-design/icons'
import { getNeuroglancerViewer } from '../utils/api'

const { Content, Sider } = Layout

function Workspace() {
  const [current, setCurrent] = useState('visualization')
  const [viewers, setViewers] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [isInferring, setIsInferring] = useState(false)
  const [isChatOpen, setIsChatOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const [ehToolSession, setEhToolSession] = useState(null)
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  const onClick = (e) => {
    setCurrent(e.key)
  }

  const items = [
    { label: 'Visualization', key: 'visualization' },
    { label: 'Model Training', key: 'training' },
    { label: 'Model Inference', key: 'inference' },
    { label: 'Tensorboard', key: 'monitoring' },
    { label: 'SynAnno', key: 'synanno' },
    { label: 'Error Handling', key: 'ehtool' },
    { label: 'Proof Reading', key: 'proofreading-ehtool' }
  ]

  const renderContent = () => {
    return (
      <>
        <div style={{ display: current === 'visualization' ? 'block' : 'none', height: '100%' }}>
          <Visualization viewers={viewers} setViewers={setViewers} />
        </div>
        <div style={{ display: current === 'training' ? 'block' : 'none', height: '100%' }}>
          <ModelTraining />
        </div>
        <div style={{ display: current === 'monitoring' ? 'block' : 'none', height: '100%' }}>
          <Monitoring />
        </div>
        <div style={{ display: current === 'inference' ? 'block' : 'none', height: '100%' }}>
          <ModelInference isInferring={isInferring} setIsInferring={setIsInferring} />
        </div>
        <div style={{ display: current === 'synanno' ? 'block' : 'none', height: '100%' }}>
          <ProofReading />
        </div>
        <div style={{ display: current === 'ehtool' ? 'block' : 'none', height: '100%' }}>
          <EHTool
            onStartProofreading={() => {
              setCurrent('proofreading-ehtool')
              setRefreshTrigger(prev => prev + 1)
            }}
            onSessionChange={setEhToolSession}
          />
        </div>
        <div style={{ display: current === 'proofreading-ehtool' ? 'block' : 'none', height: '100%' }}>
          <ProofreadingTab
            sessionId={ehToolSession}
            refreshTrigger={refreshTrigger}
            onComplete={() => setCurrent('ehtool')}
          />
        </div>
      </>
    )
  }

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

  useEffect(() => {
    if (current === 'inference' && isInferring) {
      console.log('Inference process is continuing...')
    }
  }, [current, isInferring])

  return (
    <Layout style={{ minHeight: 'calc(100vh - 64px)' }}>
      {isLoading
        ? (<div>Loading the viewer ...</div>)
        : (
          <>
            <Sider
              collapsed={collapsed}
              onCollapse={(value) => setCollapsed(value)}
              theme='light'
              collapsedWidth='0'
            >
              <DataLoader fetchNeuroglancerViewer={fetchNeuroglancerViewer} />
            </Sider>
            <Layout className='site-layout'>
              <Content style={{ margin: '0 16px' }}>
                <Menu
                  onClick={onClick}
                  selectedKeys={[current]}
                  mode='horizontal'
                  items={items}
                />
                {renderContent()}
              </Content>
            </Layout>
            {isChatOpen ? (
              <Sider width={400} theme='light'>
                <Chatbot onClose={() => setIsChatOpen(false)} />
              </Sider>
            ) : (
              <Button
                type="primary"
                shape="circle"
                icon={<MessageOutlined />}
                onClick={() => setIsChatOpen(true)}
                style={{ margin: '8px 8px' }}
              />
            )}
          </>
        )}
    </Layout>
  )
}

export default Workspace
