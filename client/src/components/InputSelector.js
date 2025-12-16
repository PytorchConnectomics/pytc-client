import { Form } from 'antd'
import React, { useContext } from 'react'
import { AppContext } from '../contexts/GlobalContext'
import UnifiedFileInput from './UnifiedFileInput'

function InputSelector(props) {
  const context = useContext(AppContext)
  const { type } = props

  const handleLogPathChange = (value) => {
    context.setLogPath(value)
  }

  const handleOutputPathChange = (value) => {
    context.setOutputPath(value)
  }

  const handleCheckpointPathChange = (value) => {
    context.setCheckpointPath(value)
  }

  const handleImageChange = (value) => {
    console.log(`selected image:`, value)
    context.setInputImage(value)
  }

  const handleLabelChange = (value) => {
    console.log(`selected label:`, value)
    context.setInputLabel(value)
  }

  // Helper to get value for UnifiedFileInput (can be object or string)
  const getValue = (val) => {
    if (!val) return '';
    return val;
  }

  return (
    <div style={{ marginTop: '10px' }}>
      <Form
        labelCol={{
          span: 5
        }}
        wrapperCol={{
          span: 14
        }}
      >
        <Form.Item label='Input Image'>
          <UnifiedFileInput
            placeholder='Please select or input image path'
            onChange={handleImageChange}
            value={getValue(context.inputImage)}
          />
        </Form.Item>
        <Form.Item label='Input Label'>
          <UnifiedFileInput
            placeholder='Please select or input label path'
            onChange={handleLabelChange}
            value={getValue(context.inputLabel)}
          />
        </Form.Item>
        {type === 'training'
          ? (
            <Form.Item label='Output Path'>
              <UnifiedFileInput
                placeholder='Directory for outputs (e.g., /path/to/outputs/)'
                value={context.outputPath || ''}
                onChange={handleOutputPathChange}
                selectionType="directory"
              />
            </Form.Item>
          )
          : (
            <Form.Item label='Output Path' help='Directory where inference results will be saved'>
              <UnifiedFileInput
                placeholder='Directory for results (e.g., /path/to/inference_output/)'
                value={context.outputPath || ''}
                onChange={handleOutputPathChange}
                selectionType="directory"
              />
            </Form.Item>
          )}
        {type === 'training'
          ? (
            <Form.Item label='Log Path'>
              <UnifiedFileInput
                placeholder='Please type training log path'
                value={context.logPath || ''}
                onChange={handleLogPathChange}
                selectionType="directory"
              />
            </Form.Item>
          )
          : (
            <Form.Item label='Checkpoint Path' help='Path to trained model file (.pth.tar)'>
              <UnifiedFileInput
                placeholder='Model checkpoint file (e.g., /path/to/checkpoint_00010.pth.tar)'
                value={context.checkpointPath || ''}
                onChange={handleCheckpointPathChange}
                selectionType="directory"
              />
            </Form.Item>
          )}
      </Form>
    </div>
  )
}
export default InputSelector
