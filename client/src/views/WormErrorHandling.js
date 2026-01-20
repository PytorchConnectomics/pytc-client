import React, { useState } from 'react'
import { Layout } from 'antd'
import EHTool from './EHTool'

function WormErrorHandling() {
  const [ehToolSession, setEhToolSession] = useState(null)
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  return (
    <div style={{ height: '100%', overflow: 'hidden' }}>
      <EHTool
        refreshTrigger={refreshTrigger}
        savedSessionId={ehToolSession}
        onSessionChange={setEhToolSession}
        onStartProofreading={() => {
          // This prop is now nominally used to trigger internal modal
          setRefreshTrigger((prev) => prev + 1)
        }}
      />
    </div>
  )
}

export default WormErrorHandling
