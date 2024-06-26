import React, { useContext, useEffect, useState } from 'react'
import { Input, message } from 'antd'
import yaml from 'js-yaml'
import { AppContext } from '../contexts/GlobalContext'

const YamlFileEditor = (props) => {
  const context = useContext(AppContext)
  const [yamlContent, setYamlContent] = useState('')

  const { type } = props

  const handleTextAreaChange = (event) => {
    const updatedYamlContent = event.target.value
    setYamlContent(updatedYamlContent)
    if (type === 'training') {
      context.setTrainingConfig(updatedYamlContent)
    } else {
      context.setInferenceConfig(updatedYamlContent)
    }
    try {
      // const yamlData = yaml.load(updatedYamlContent);
      yaml.load(updatedYamlContent)

      // YAMLContext.setNumGPUs(yamlData.SYSTEM.NUM_GPUS);
      // YAMLContext.setNumCPUs(yamlData.SYSTEM.NUM_CPUS);
      // YAMLContext.setLearningRate(yamlData.SOLVER.BASE_LR);
      // YAMLContext.setSamplesPerBatch(yamlData.SOLVER.SAMPLES_PER_BATCH);
    } catch (error) {
      message.error('Error parsing YAML content.')
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
    <div>
      {yamlContent && (
        <div>
          <h2>{context.uploadedYamlFile.name}</h2>
        </div>
      )}
      {yamlContent && (
        <Input.TextArea
          value={yamlContent}
          onChange={handleTextAreaChange}
          autoSize={{ minRows: 4, maxRows: 8 }}
        />
      )}
    </div>
  )
}
export default YamlFileEditor
