//  global FileReader
import React, { Fragment, useContext, useEffect, useState } from 'react'
import { Button, Col, message, Row, Slider, Upload } from 'antd'
import { UploadOutlined } from '@ant-design/icons'
import yaml from 'js-yaml'
import { AppContext } from '../contexts/GlobalContext'
import { YamlContext } from '../contexts/YamlContext'
import { findCommonPartOfString } from '../utils/utils'

const YamlFileUploader = (props) => {
  const context = useContext(AppContext)
  const YAMLContext = useContext(YamlContext)
  const { type } = props

  const [, setYamlContent] = useState('')

  const trainingParams = [
    {
      label: 'Number of GPUs',
      min: 0,
      max: 8,
      marks: { 0: 0, 4: 4, 8: 8 },
      value: YAMLContext.numGPUs,
      location: 'SYSTEM',
      property: 'NUM_GPUS',
      step: 1
    },
    {
      label: 'Number of CPUs',
      min: 1,
      max: 8,
      marks: { 1: 1, 4: 4, 8: 8 },
      value: YAMLContext.numCPUs,
      location: 'SYSTEM',
      property: 'NUM_CPUS',
      step: 1
    },
    {
      label: 'Learning Rate',
      min: 0.01,
      max: 0.1,
      marks: { 0.01: 0.01, 0.1: 0.1 },
      value: YAMLContext.learningRate,
      location: 'SOLVER',
      property: 'BASE_LR',
      step: 0.01
    },
    {
      label: 'Samples Per Batch',
      min: 2,
      max: 16,
      marks: { 2: 2, 8: 8, 16: 16 },
      value: YAMLContext.solverSamplesPerBatch,
      location: 'SOLVER',
      property: 'SAMPLES_PER_BATCH',
      step: 1
    }
  ]

  const inferenceParams = [
    {
      label: 'Augmentation Number',
      min: 2,
      max: 16,
      marks: { 2: 2, 8: 8, 16: 16 },
      value: YAMLContext.augNum,
      location: 'INFERENCE',
      property: 'AUG_NUM',
      step: 1
    },
    {
      label: 'Samples Per Batch',
      min: 2,
      max: 16,
      marks: { 2: 2, 8: 8, 16: 16 },
      value: YAMLContext.inferenceSamplesPerBatch,
      location: 'INFERENCE',
      property: 'SAMPLES_PER_BATCH',
      step: 1
    }
  ]

  const sliderData = type === 'training' ? trainingParams : inferenceParams

  const updateInputSelectorInformation = (context, yamlData) => {
    // update InputSelector's information
    if (
      context.inputImage &&
      context.inputImage.folderPath &&
      context.inputLabel &&
      context.inputLabel.folderPath
    ) {
      const inputImage =
        context.inputImage.folderPath + context.inputImage.name
      const inputLabel =
        context.inputLabel.folderPath + context.inputLabel.name

      const inputPath = findCommonPartOfString(inputImage, inputLabel)
      yamlData.DATASET.INPUT_PATH = inputPath
      yamlData.DATASET.IMAGE_NAME = inputImage.replace(inputPath, '')
      yamlData.DATASET.LABEL_NAME = inputLabel.replace(inputPath, '')
      yamlData.DATASET.OUTPUT_PATH = context.outputPath
    } else {
      message.error('Please input folder path of the file in preview')
    }
  }

  const handleFileUpload = (file) => {
    context.setUploadedYamlFile(file)
    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const contents = e.target.result
        const yamlData = yaml.load(contents)

        if (type === 'training') {
          context.setTrainingConfig(
            yaml.dump(yamlData, { indent: 2 }).replace(/^\s*\n/gm, '')
          )
          YAMLContext.setNumGPUs(yamlData.SYSTEM.NUM_GPUS)
          YAMLContext.setNumCPUs(yamlData.SYSTEM.NUM_CPUS)
          YAMLContext.setLearningRate(yamlData.SOLVER.BASE_LR)
          YAMLContext.setSolverSamplesPerBatch(
            yamlData.SOLVER.SAMPLES_PER_BATCH
          )
          updateInputSelectorInformation(context, yamlData)
        } else {
          // type === "inference"
          context.setInferenceConfig(
            yaml.dump(yamlData, { indent: 2 }).replace(/^\s*\n/gm, '')
          )
          YAMLContext.setInferenceSamplesPerBatch(
            yamlData.INFERENCE.SAMPLES_PER_BATCH
          )
          YAMLContext.setAugNum(yamlData.INFERENCE.AUG_NUM)
          // update InputSelector's information
          updateInputSelectorInformation(context, yamlData)
        }

        context.setTrainingConfig(
          yaml.dump(yamlData, { indent: 2 }).replace(/^\s*\n/gm, '')
        )

        context.setInferenceConfig(
          yaml.safeDump(yamlData, { indent: 2 }).replace(/^\s*\n/gm, '')
        )
        // these are for slider
        YAMLContext.setNumGPUs(yamlData.SYSTEM.NUM_GPUS)
        YAMLContext.setNumCPUs(yamlData.SYSTEM.NUM_CPUS)
        YAMLContext.setLearningRate(yamlData.SOLVER.BASE_LR)
        YAMLContext.setSolverSamplesPerBatch(yamlData.SOLVER.SAMPLES_PER_BATCH)
      } catch (error) {
        message.error('Error reading YAML file.')
      }
    }
    reader.readAsText(file)
  }

  // Add the values to the global context to ensure that the values will be held on page switching
  // It shouldnt need a glabal  context but rather make a local YAML context

  const handleSliderChange = (location, property, newValue) => {
    // Update the respective property based on the parameter
    switch (location + '_' + property) {
      case 'SYSTEM_NUM_GPUS':
        YAMLContext.setNumGPUs(newValue)
        break
      case 'SYSTEM_NUM_CPUS':
        YAMLContext.setNumCPUs(newValue)
        break
      case 'SOLVER_BASE_LR':
        YAMLContext.setLearningRate(newValue)
        break
      case 'SOLVER_SAMPLES_PER_BATCH':
        YAMLContext.setSolverSamplesPerBatch(newValue)
        break
      case 'INFERENCE_SAMPLES_PER_BATCH':
        YAMLContext.setInferenceSamplesPerBatch(newValue)
        break
      case 'INFERENCE_AUG_NUM':
        YAMLContext.setAugNum(newValue)
        break
      default:
        break
    }

    // Update the YAML file if it has been uploaded
    if (context.uploadedYamlFile) {
      const reader = new FileReader()
      reader.onload = (e) => {
        try {
          const contents = e.target.result
          const yamlData = yaml.load(contents)

          // Update the property value in the YAML data
          yamlData[location][property] = newValue

          if (type === 'training') {
            context.setTrainingConfig(
              yaml.dump(yamlData, { indent: 2 }).replace(/^\s*\n/gm, '')
            )
          } else {
            context.setInferenceConfig(
              yaml.dump(yamlData, { indent: 2 }).replace(/^\s*\n/gm, '')
            )
          }
        } catch (error) {
          console.log(error)
          message.error('Error reading YAML file.')
        }
      }
      reader.readAsText(context.uploadedYamlFile)

      updateYamlData(property, newValue)
      setYamlContent(
        type === 'training' ? context.trainingConfig : context.inferenceConfig
      )
    }
  }

  const updateYamlData = (property, value) => {
    const updatedYamlData = { ...context.yamlData, [property]: value }
    const updatedYamlContent = yaml
      .dump(updatedYamlData, { indent: 2 })
      .replace(/^\s*\n/gm, '')
    setYamlContent(updatedYamlContent)
    if (type === 'training') {
      context.setTrainingConfig(updatedYamlContent)
    } else {
      context.setInferenceConfig(updatedYamlContent)
    }
  }

  useEffect(() => {
    if (type === 'training') {
      setYamlContent(context.trainingConfig)
    }

    if (type === 'inference') {
      setYamlContent(context.inferenceConfig)
    }
  }, [
    context.uploadedYamlFile,
    context.trainingConfig,
    context.inferenceConfig,
    type
  ])

  return (
    <div style={{ margin: '10px' }}>
      <Upload beforeUpload={handleFileUpload} showUploadList={false}>
        <Button icon={<UploadOutlined />} size='small'>
          Upload YAML File
        </Button>
      </Upload>
      {((type === 'training' && context.trainingConfig !== null) ||
        (type === 'inference' && context.inferenceConfig !== null)) && (
          <>
            <div>
              <h3>Uploaded File: {context.uploadedYamlFile.name}</h3>
            </div>
            <div>
              <Row>
                {sliderData.map((param, index) => (
                  <Fragment key={index}>
                    <Col span={8} offset={2}>
                      <div>
                        <h4>{param.label}</h4>
                        <Slider
                          min={param.min}
                          max={param.max}
                          marks={param.marks}
                          value={param.value}
                          onChange={(newValue) =>
                            handleSliderChange(
                              param.location,
                              param.property,
                              newValue
                            )}
                          step={param.step}
                        />
                      </div>
                    </Col>
                  </Fragment>
                ))}
              </Row>
            </div>
          </>
      )}
    </div>
  )
}

export default YamlFileUploader
