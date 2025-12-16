import React, { useState } from 'react'
import { Tabs } from 'antd'
import { BugOutlined, ReadOutlined } from '@ant-design/icons'
import EHTool from './EHTool'
import ProofreadingTab from './ProofreadingTab'

function WormErrorHandling() {
  const [activeTab, setActiveTab] = useState('ehtool')
  const [ehToolSession, setEhToolSession] = useState(null)
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  const items = [
    {
      label: (
        <span>
          <BugOutlined />
          Error Handling
        </span>
      ),
      key: 'ehtool',
      children: (
        <div style={{ height: '100%', overflow: 'auto' }}>
          <EHTool
            refreshTrigger={refreshTrigger}
            savedSessionId={ehToolSession} // Pass persistent session
            onStartProofreading={() => {
              setActiveTab('proofreading')
              setRefreshTrigger((prev) => prev + 1)
            }}
            onSessionChange={setEhToolSession}
          />
        </div>
      )
    },
    {
      label: (
        <span>
          <ReadOutlined />
          Proof Reading
        </span>
      ),
      key: 'proofreading',
      children: (
        <div style={{ height: '100%', overflow: 'auto' }}>
          <ProofreadingTab
            sessionId={ehToolSession}
            refreshTrigger={refreshTrigger}
            onComplete={() => {
              setActiveTab('ehtool')
              setRefreshTrigger((prev) => prev + 1)
            }}
          />
        </div>
      )
    }
  ]

  return (
    <Tabs
      activeKey={activeTab}
      onChange={setActiveTab}
      items={items}
      style={{ height: '100%' }}
      tabBarStyle={{ marginBottom: 0, paddingLeft: 16 }}
      destroyInactiveTabPane={true}
    />
  )
}

export default WormErrorHandling
