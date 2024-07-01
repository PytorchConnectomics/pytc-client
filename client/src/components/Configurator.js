// global localStorage
import React, { useContext, useState } from 'react'
import { Button, message, Steps, theme } from 'antd'
import YamlFileUploader from './YamlFileUploader'
import YamlFileEditor from './YamlFileEditor'
import InputSelector from './InputSelector'
import { AppContext } from '../contexts/GlobalContext'

function Configurator (props) {
  const { fileList, type } = props
  const context = useContext(AppContext)
  const [current, setCurrent] = useState(0)

  const next = () => {
    setCurrent(current + 1)
  }

  const prev = () => {
    setCurrent(current - 1)
  }

  const handleDoneButton = () => {
    message.success('Processing complete!')
    if (type === 'training') {
      localStorage.setItem('trainingConfig', context.trainingConfig)
    } else {
      localStorage.setItem('inferenceConfig', context.inferenceConfig)
    }
  }

  const items = [
    {
      title: 'Set Inputs',
      content: <InputSelector fileList={fileList} type={type} />
    },
    {
      title: 'Base Configuration',
      content: <YamlFileUploader type={type} />
    },
    {
      title: 'Advanced Configuration',
      content: <YamlFileEditor type={type} />
    }
  ]

  const { token } = theme.useToken()

  const contentStyle = {
    height: '260px',
    textAlign: 'left',
    color: token.colorTextTertiary,
    backgroundColor: token.colorFillAlter,
    borderRadius: token.borderRadiusLG,
    border: `1px dashed ${token.colorBorder}`,
    marginTop: 12
  }

  return (
    <div style={{ marginTop: 12 }}>
      <Steps size='small' current={current} items={items} />
      <div style={contentStyle}>{items[current].content}</div>
      <div style={{ marginTop: 24 }}>
        {current > 0 && (
          <Button style={{ margin: '0 8px' }} onClick={() => prev()}>
            Previous
          </Button>
        )}
        {current < items.length - 1 && (
          <Button type='primary' onClick={() => next()}>
            Next
          </Button>
        )}
        {current === items.length - 1 && (
          <Button type='primary' onClick={handleDoneButton}>
            Done
          </Button>
        )}
      </div>
    </div>
  )
}

export default Configurator
