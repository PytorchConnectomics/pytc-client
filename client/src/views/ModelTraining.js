//  global localStorage
import React, { useContext, useState, useEffect, useRef } from 'react'
import { Button, Space } from 'antd'
import { startModelTraining, stopModelTraining, getTrainingStatus } from '../utils/api'
import Configurator from '../components/Configurator'
import { AppContext } from '../contexts/GlobalContext'

function ModelTraining() {
  const context = useContext(AppContext)
  const [isTraining, setIsTraining] = useState(false)
  const [trainingStatus, setTrainingStatus] = useState('')
  const pollingIntervalRef = useRef(null)

  // Poll training status when training is active
  useEffect(() => {
    if (isTraining) {
      console.log('Starting training status polling...')
      pollingIntervalRef.current = setInterval(async () => {
        try {
          const status = await getTrainingStatus()
          console.log('Training status:', status)

          if (!status.isRunning) {
            // Training has finished
            console.log('Training completed!')
            setIsTraining(false)

            if (status.exitCode === 0) {
              setTrainingStatus('Training completed successfully! ✓')
            } else if (status.exitCode !== null) {
              setTrainingStatus(`Training finished with exit code: ${status.exitCode}`)
            } else {
              setTrainingStatus('Training stopped.')
            }

            // Clear the polling interval
            if (pollingIntervalRef.current) {
              clearInterval(pollingIntervalRef.current)
              pollingIntervalRef.current = null
            }
          }
        } catch (error) {
          console.error('Error polling training status:', error)
        }
      }, 2000) // Poll every 2 seconds
    }

    // Cleanup on unmount or when training stops
    return () => {
      if (pollingIntervalRef.current) {
        console.log('Clearing polling interval')
        clearInterval(pollingIntervalRef.current)
        pollingIntervalRef.current = null
      }
    }
  }, [isTraining])

  // const [tensorboardURL, setTensorboardURL] = useState(null);
  const handleStartButton = async () => {
    try {
      // TODO: Validate required context values before starting
      if (!context.uploadedYamlFile) {
        setTrainingStatus('Error: Please upload a YAML configuration file first.')
        return
      }

      if (!context.outputPath) {
        setTrainingStatus('Error: Please set output path first in Step 1.')
        return
      }

      if (!context.logPath) {
        setTrainingStatus('Error: Please set log path first in Step 1.')
        return
      }

      console.log(context.uploadedYamlFile)
      const trainingConfig = localStorage.getItem('trainingConfig') || context.trainingConfig
      console.log(trainingConfig)

      setIsTraining(true)
      setTrainingStatus('Starting training... Please wait, this may take a while.')

      const getPath = (val) => {
        if (!val) return '';
        if (typeof val === 'string') return val;
        return val.path || '';
      }

      // TODO: The API call should be non-blocking and return immediately
      // Real training status should be polled separately
      const res = await startModelTraining(
        trainingConfig,
        getPath(context.logPath),
        getPath(context.outputPath)
      )
      console.log(res)

      // TODO: Don't set training complete here - implement proper status polling
      setTrainingStatus('Training started successfully. Monitoring progress...')
    } catch (e) {
      console.error('Training start error:', e)
      setTrainingStatus(`Training error: ${e.message || 'Please check console for details.'}`)
      setIsTraining(false)
    }
  }

  const handleStopButton = async () => {
    try {
      setTrainingStatus('Stopping training...')
      await stopModelTraining()
      setIsTraining(false)
      setTrainingStatus('Training stopped successfully.')
    } catch (e) {
      console.error('Training stop error:', e)
      setTrainingStatus(`Error stopping training: ${e.message || 'Please check console for details.'}`)
    }
  }

  // const handleTensorboardButton = async () => {
  //   try {
  //     const res = await startTensorboard();
  //     console.log(res);
  //     setTensorboardURL(res);
  //   } catch (e) {
  //     console.log(e);
  //   }
  // };
  // const [componentSize, setComponentSize] = useState("default");
  // const onFormLayoutChange = ({ size }) => {
  //   setComponentSize(size);
  // };

  return (
    <>
      <div>
        {/* {"ModelTraining"} */}
        <Configurator fileList={context.files} type='training' />
        <Space wrap style={{ marginTop: 12 }}>
          <Button
            onClick={handleStartButton}
            disabled={isTraining}
          >
            Start Training
          </Button>
          <Button
            onClick={handleStopButton}
            disabled={!isTraining}
          >
            Stop Training
          </Button>
        </Space>
        {/* <Button onClick={handleTensorboardButton}>Tensorboard</Button> */}
        <p style={{ marginTop: 4 }}>{trainingStatus}</p>
      </div>
    </>
  )
}

export default ModelTraining
