import React, { useState, useEffect } from 'react'
import { getTensorboardURL } from '../utils/api'

function Monitoring () {
  const [tensorboardURL, setTensorboardURL] = useState(null)

  const callGetTensorboardURL = async () => {
    try {
      const res = await getTensorboardURL()
      console.log(res)
      setTensorboardURL(res)
    } catch (e) {
      console.log(e)
    }
  }

  useEffect(() => {
    if (!tensorboardURL) {
      callGetTensorboardURL()
    }
  }, [tensorboardURL])

  return (
    <div style={{ height: '100%', minHeight: 0 }}>
      {tensorboardURL && (
        <iframe
          title='TensorBoard Display'
          width='100%'
          height='100%'
          frameBorder='0'
          scrolling='no'
          src={tensorboardURL}
          style={{ height: '100%', minHeight: 360, border: 0 }}
        />
      )}
    </div>
  )
}
export default Monitoring
