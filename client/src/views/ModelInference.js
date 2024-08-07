// global localStorage
import React, { useContext, useState } from 'react'
import { Button, Space } from 'antd'
import { startModelInference, stopModelInference } from '../utils/api'
import Configurator from '../components/Configurator'
import { AppContext } from '../contexts/GlobalContext'

function ModelInference ({ isInferring, setIsInferring }) {
  const context = useContext(AppContext)
  // const [isInference, setIsInference] = useState(false)
  const handleStartButton = async () => {
    try {
      const inferenceConfig = localStorage.getItem('inferenceConfig')

      // const res = startModelInference(
      const res = await startModelInference(
        context.uploadedYamlFile.name,
        inferenceConfig,
        context.outputPath,
        context.checkpointPath
      ) // inputs, configurationYaml
      console.log(res)
    } catch (e) {
      console.log(e)
    } finally {
      // setIsInference(true)
      setIsInferring(true)
    }
  }

  const handleStopButton = async () => {
    try {
      await stopModelInference()
    } catch (e) {
      console.log(e)
    } finally {
      // setIsInference(false)
      setIsInferring(false)
    }
  }

  // const [componentSize, setComponentSize] = useState("default");
  const [componentSize] = useState('default')
  // const onFormLayoutChange = ({ size }) => {
  //   setComponentSize(size);
  // };

  return (
    <>
      <div>
        <Configurator fileList={context.files} type='inference' />
        <Space wrap style={{ marginTop: 12 }} size={componentSize}>
          <Button
            onClick={handleStartButton}
            disabled={isInferring} // Disables the button when inference is running
          >
            Start Inference
          </Button>
          <Button
            onClick={handleStopButton}
            disabled={!isInferring} // Disables the button when inference is not running
          >
            Stop Inference
          </Button>
        </Space>
      </div>
    </>
  )
}

export default ModelInference
