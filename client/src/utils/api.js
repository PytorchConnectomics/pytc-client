import axios from 'axios'
import { message } from 'antd'

// TODO: Add proper environment configuration
const API_PROTOCOL = process.env.REACT_APP_API_PROTOCOL || 'http'
const API_URL = process.env.REACT_APP_API_URL || 'localhost:4242'

const buildFilePath = (file) => {
  if (!file) return ''
  if (typeof file === 'string') return file
  if (file.folderPath) return file.folderPath + file.name
  if (file.path) return file.path
  if (file.originFileObj && file.originFileObj.path) {
    return file.originFileObj.path
  }
  return file.name
}

const hasBrowserFile = (file) =>
  file && file.originFileObj instanceof File

export async function getNeuroglancerViewer(image, label, scales) {
  try {
    const url = `${API_PROTOCOL}://${API_URL}/neuroglancer`
    if (hasBrowserFile(image)) {
      const formData = new FormData()
      formData.append(
        'image',
        image.originFileObj,
        image.originFileObj.name || image.name || 'image'
      )
      if (label && hasBrowserFile(label)) {
        formData.append(
          'label',
          label.originFileObj,
          label.originFileObj.name || label.name || 'label'
        )
      }
      formData.append('scales', JSON.stringify(scales))
      const res = await axios.post(url, formData)
      return res.data
    }

    const data = JSON.stringify({
      image: buildFilePath(image),
      label: buildFilePath(label),
      scales
    })
    const res = await axios.post(url, data)
    return res.data
  } catch (error) {
    message.error(
      'Invalid Data Path(s). Be sure to include all "/" and that data path is correct.'
    )
  }
}


export async function checkFile(file) {
  try {
    const url = `${API_PROTOCOL}://${API_URL}/check_files`
    const data = JSON.stringify({
      folderPath: file.folderPath || '',
      name: file.name,
      filePath: file.path || file.originFileObj?.path
    })
    const res = await axios.post(url, data)
    return res.data
  } catch (error) {
    handleError(error)
  }
}

function handleError(error) {
  if (error.response) {
    throw new Error(
      `${error.response.status}: ${error.response.data?.detail?.data || error.response.statusText}`
    )
  }
  throw error
}

export async function makeApiRequest(url, method, data = null) {
  try {
    const fullUrl = `${API_PROTOCOL}://${API_URL}/${url}`
    const config = {
      method,
      url: fullUrl,
      headers: {
        'Content-Type': 'application/json'
      }
    }

    if (data) {
      config.data = data
    }

    const res = await axios(config)
    return res.data
  } catch (error) {
    handleError(error)
  }
}

export async function startModelTraining(
  trainingConfig,
  logPath,
  outputPath
) {
  try {
    console.log('[API] ===== Starting Training Configuration =====')
    console.log('[API] logPath:', logPath)
    console.log('[API] outputPath:', outputPath)

    // Parse the YAML config and inject the outputPath
    let configToSend = trainingConfig

    if (outputPath) {
      try {
        // Parse YAML to object
        const yaml = require('js-yaml')
        const configObj = yaml.load(trainingConfig)

        console.log('[API] Original DATASET.OUTPUT_PATH:', configObj.DATASET?.OUTPUT_PATH)

        // Inject the output path from UI
        if (!configObj.DATASET) {
          configObj.DATASET = {}
        }
        configObj.DATASET.OUTPUT_PATH = outputPath

        // Convert back to YAML
        configToSend = yaml.dump(configObj)
        console.log('[API] Injected DATASET.OUTPUT_PATH:', outputPath)
        console.log('[API] Modified config preview:', configToSend.substring(0, 500))
      } catch (e) {
        console.warn('[API] Failed to parse/modify YAML, using original config:', e)
      }
    } else {
      console.warn('[API] No outputPath provided, config will use its original OUTPUT_PATH')
    }

    const data = JSON.stringify({
      arguments: {
        // nproc_per_node: 4,
        // master_port: 2345,
        // distributed: "",
      },
      logPath,  // Keep for backwards compatibility, but won't be used for TensorBoard
      outputPath,  // TensorBoard will use this instead
      trainingConfig: configToSend
    })

    console.log('[API] Request payload size:', data.length, 'bytes')
    console.log('[API] Note: TensorBoard will monitor outputPath, not logPath')
    console.log('[API] =========================================')

    return makeApiRequest('start_model_training', 'post', data)
  } catch (error) {
    handleError(error)
  }
}

export async function stopModelTraining() {
  try {
    await axios.post(
      `${API_PROTOCOL}://${API_URL}/stop_model_training`
    )
  } catch (error) {
    handleError(error)
  }
}

export async function getTrainingStatus() {
  try {
    const res = await axios.get(
      `${API_PROTOCOL}://${API_URL}/training_status`
    )
    return res.data
  } catch (error) {
    console.error('Failed to get training status:', error)
    return { isRunning: false, error: true }
  }
}

// export async function startTensorboard() {
//   try {
//     const res = await axios.get(
//       `${process.env.REACT_APP_API_PROTOCOL}://${process.env.REACT_APP_API_URL}/start_tensorboard`
//     );
//     return res.data;
//   } catch (error) {
//     if (error.response) {
//       throw new Error(
//         `${error.response.status}: ${error.response.data?.detail?.error}`
//       );
//     }
//     throw error;
//   }
// }

export async function getTensorboardURL() {
  return makeApiRequest('get_tensorboard_url', 'get')
}

export async function startModelInference(
  inferenceConfig,
  outputPath,
  checkpointPath
) {
  console.log('\n========== API.JS: START_MODEL_INFERENCE CALLED ==========')
  console.log('[API] Function arguments:')
  console.log('[API]   - inferenceConfig type:', typeof inferenceConfig)
  console.log('[API]   - inferenceConfig length:', inferenceConfig?.length || 'N/A')
  console.log('[API]   - outputPath:', outputPath)
  console.log('[API]   - outputPath type:', typeof outputPath)
  console.log('[API]   - checkpointPath:', checkpointPath)
  console.log('[API]   - checkpointPath type:', typeof checkpointPath)

  try {
    console.log('[API] ===== Starting Inference Configuration =====')

    // Parse the YAML config and inject the outputPath
    let configToSend = inferenceConfig

    if (outputPath) {
      console.log('[API] outputPath provided, will inject into YAML')
      try {
        // Parse YAML to object
        const yaml = require('js-yaml')
        console.log('[API] Parsing YAML config...')
        const configObj = yaml.load(inferenceConfig)
        console.log('[API] ✓ YAML parsed successfully')

        console.log('[API] Original config structure:')
        console.log('[API]   - Has INFERENCE section?', !!configObj.INFERENCE)
        console.log('[API]   - Original INFERENCE.OUTPUT_PATH:', configObj.INFERENCE?.OUTPUT_PATH)

        // Inject the output path from UI
        if (!configObj.INFERENCE) {
          console.log('[API] INFERENCE section missing, creating it')
          configObj.INFERENCE = {}
        }
        configObj.INFERENCE.OUTPUT_PATH = outputPath;
        // Ensure SYSTEM section exists and set NUM_GPUS to 1 for CPU inference
        if (!configObj.SYSTEM) {
          console.log('[API] SYSTEM section missing, creating it');
          configObj.SYSTEM = {};
        }
        configObj.SYSTEM.NUM_GPUS = 1;
        console.log('[API] ✓ Set SYSTEM.NUM_GPUS = 1');
        console.log('[API] ✓ Injected INFERENCE.OUTPUT_PATH:', outputPath)

        // Convert back to YAML
        console.log('[API] Converting back to YAML...')
        configToSend = yaml.dump(configObj)
        console.log('[API] ✓ YAML conversion successful')
        console.log('[API] Modified config preview (first 500 chars):', configToSend.substring(0, 500))
      } catch (e) {
        console.error('[API] ✗ YAML processing error:', e)
        console.error('[API] Error type:', e.constructor.name)
        console.error('[API] Error message:', e.message)
        console.warn('[API] Falling back to original config')
        configToSend = inferenceConfig
      }
    } else {
      console.warn('[API] ⚠ No outputPath provided, config will use its original OUTPUT_PATH')
    }

    console.log('[API] Building request payload...')
    const payload = {
      arguments: {
        checkpoint: checkpointPath
      },
      outputPath,
      inferenceConfig: configToSend
    }

    console.log('[API] Payload structure:')
    console.log('[API]   - arguments.checkpoint:', payload.arguments.checkpoint)
    console.log('[API]   - outputPath:', payload.outputPath)
    console.log('[API]   - inferenceConfig length:', payload.inferenceConfig?.length)

    const data = JSON.stringify(payload)
    console.log('[API] Request payload size:', data.length, 'bytes')
    console.log('[API] JSON payload preview (first 300 chars):', data.substring(0, 300))

    console.log('[API] Calling makeApiRequest...')
    console.log('[API] Target endpoint: start_model_inference')
    console.log('[API] Method: POST')
    console.log('[API] =========================================')

    const result = await makeApiRequest('start_model_inference', 'post', data)
    console.log('[API] ✓ makeApiRequest returned:', result)
    console.log('========== API.JS: END START_MODEL_INFERENCE ==========\n')
    return result
  } catch (error) {
    console.error('========== API.JS: ERROR IN START_MODEL_INFERENCE ==========')
    console.error('[API] Error caught:', error)
    console.error('[API] Error type:', error.constructor.name)
    console.error('[API] Error message:', error.message)
    console.error('[API] Error stack:', error.stack)
    console.error('========== API.JS: END ERROR ==========\n')
    handleError(error)
  }
}

export async function getInferenceStatus() {
  try {
    const res = await axios.get(
      `${API_PROTOCOL}://${API_URL}/inference_status`
    )
    return res.data
  } catch (error) {
    console.error('Failed to get inference status:', error)
    return { isRunning: false, error: true }
  }
}

export async function stopModelInference() {
  try {
    await axios.post(
      `${API_PROTOCOL}://${API_URL}/stop_model_inference`
    )
  } catch (error) {
    handleError(error)
  }
}

export async function queryChatBot(query) {
  try {
    const res = await axios.post(
      `${process.env.REACT_APP_API_PROTOCOL}://${process.env.REACT_APP_API_URL}/chat/query`,
      { query }
    )
    return res.data?.response
  } catch (error) {
    handleError(error)
  }
}

export async function clearChat() {
  try {
    await axios.post(
      `${process.env.REACT_APP_API_PROTOCOL}://${process.env.REACT_APP_API_URL}/chat/clear`
    )
  } catch (error) {
    handleError(error)
  }
}
