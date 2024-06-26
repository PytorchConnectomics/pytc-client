/* global localStorage */
import React, { useContext, useState } from 'react'
import { Button, Space } from 'antd'
import { startModelTraining, stopModelTraining } from '../utils/api'
import Configurator from '../components/Configurator'
import { AppContext } from '../contexts/GlobalContext'

function ModelTraining () {
  const context = useContext(AppContext)
  const [isTraining, setIsTraining] = useState(false)
  const [trainingStatus, setTrainingStatus] = useState('')
  // const [tensorboardURL, setTensorboardURL] = useState(null);
  const handleStartButton = async () => {
    try {
      // let fmData = new FormData();
      // fmData.append(
      //   "configBase",
      //   "--config-base configs/SNEMI/SNEMI-Base.yaml"
      // );
      console.log(context.uploadedYamlFile)
      const trainingConfig = localStorage.getItem('trainingConfig')
      console.log(trainingConfig)
      const res = await startModelTraining(
        context.uploadedYamlFile.name,
        trainingConfig,
        context.outputPath,
        context.logPath
      )
      console.log(res)
      setIsTraining(true)
      setTrainingStatus('Training in Progress... Please wait, this may take a while.')
    } catch (e) {
      console.log(e)
      setTrainingStatus('Training error! Please inspect console.')
      setIsTraining(false)
      return
    }

    setIsTraining(false)
    setTrainingStatus('Training complete!')
  }

  const handleStopButton = async () => {
    try {
      stopModelTraining()
    } catch (e) {
      console.log(e)
      setTrainingStatus('Training error! Please inspect console.')
    } finally {
      setIsTraining(false)
      setTrainingStatus('Training stopped.')
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
