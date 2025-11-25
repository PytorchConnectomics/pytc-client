import React, { useContext, useEffect, useState } from 'react'
import { Dragger } from '../components/Dragger'
import { Button, Input, Select, Space, Typography } from 'antd'
import { ArrowRightOutlined, PlayCircleOutlined, StopOutlined } from '@ant-design/icons'
import { AppContext } from '../contexts/GlobalContext'
import { startModelInference, stopModelInference } from '../utils/api'
import './DataLoader.css'

const { Title } = Typography

function DataLoader(props) {
  const context = useContext(AppContext)
  // Initialize local state from context to support pre-loaded demo files
  const [currentImage, setCurrentImage] = useState(context.currentImage)
  const [currentLabel, setCurrentLabel] = useState(context.currentLabel)
  const [scales, setScales] = useState('30,6,6')
  const { fetchNeuroglancerViewer, isInferring, setIsInferring } = props

  // Sync local state if context changes (e.g. reset)
  useEffect(() => {
    setCurrentImage(context.currentImage)
  }, [context.currentImage])

  useEffect(() => {
    setCurrentLabel(context.currentLabel)
  }, [context.currentLabel])

  const handleVisualizeButtonClick = async (event) => {
    event.preventDefault()
    // Update global context before visualizing
    context.setCurrentImage(currentImage)
    context.setCurrentLabel(currentLabel)
    fetchNeuroglancerViewer(
      currentImage,
      currentLabel,
      scales.split(',').map(Number)
    )
  }

  const handleStartInference = async () => {
    try {
      const res = await startModelInference(
        context.inferenceConfig,
        context.outputPath,
        context.checkpointPath,
        currentImage ? currentImage.path : null
      )
      console.log(res)
    } catch (e) {
      console.log(e)
    } finally {
      setIsInferring(true)
    }
  }

  const handleStopInference = async () => {
    try {
      await stopModelInference()
    } catch (e) {
      console.log(e)
    } finally {
      setIsInferring(false)
    }
  }

  const handleImageChange = (value) => {
    console.log(`selected ${value}`)
    setCurrentImage(context.files.find((image) => image.uid === value))
  }

  const handleLabelChange = (value) => {
    console.log(`selected ${value}`)
    setCurrentLabel(context.files.find((file) => file.uid === value))
  }

  const handleInputScales = (event) => {
    setScales(event.target.value)
  }

  const { files, setFileList } = context
  useEffect(() => {
    if (files) {
      setFileList(
        files.map((file) => ({
          label: file.name,
          value: file.uid
        }))
      )
    }
  }, [files, setFileList])

  return (
    <Space
      direction='vertical'
      size='small'
      align='start'
      style={{ margin: '7px', display: 'flex' }}
    >
      <Dragger />
      <Title level={5} style={{ marginBottom: '-5px' }}>
        Image
      </Title>
      <Select
        onChange={handleImageChange}
        options={context.imageFileList.map((file) => ({
          label: file.name,
          value: file.uid
        }))}
        value={currentImage ? currentImage.uid : undefined}
        style={{ width: '185px' }}
        placeholder='Select image'
        size='middle'
        allowClear
      />

      <Title level={5} style={{ marginTop: '0px', marginBottom: '-5px' }}>
        Label
      </Title>
      <Select
        onChange={handleLabelChange}
        options={context.labelFileList.map((file) => ({
          label: file.name,
          value: file.uid
        }))}
        value={currentLabel ? currentLabel.uid : undefined}
        style={{ width: '185px' }}
        placeholder='Select label'
        size='middle'
        allowClear
      />

      <Title level={5} style={{ marginTop: '0px', marginBottom: '-5px' }}>
        Scales
      </Title>
      <Input
        placeholder='Input in z, y, x order'
        allowClear
        onChange={handleInputScales}
        style={{ width: '185px' }}
      />
      <Button
        type='primary'
        onClick={handleVisualizeButtonClick}
        icon={<ArrowRightOutlined />}
        style={{ width: '185px' }}
      >
        Visualize
      </Button>

      <div style={{ marginTop: '10px', width: '100%', borderTop: '1px solid #eee', paddingTop: '10px' }}>
        <Title level={5} style={{ marginTop: '0px', marginBottom: '5px' }}>
          Inference
        </Title>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Button
            onClick={handleStartInference}
            disabled={isInferring}
            icon={<PlayCircleOutlined />}
            style={{ width: '185px', backgroundColor: '#52c41a', color: 'white' }}
          >
            Segment
          </Button>
          <Button
            onClick={handleStopInference}
            disabled={!isInferring}
            icon={<StopOutlined />}
            danger
            style={{ width: '185px' }}
          >
            Stop
          </Button>
        </Space>
      </div>
    </Space>
  )
}

export default DataLoader
