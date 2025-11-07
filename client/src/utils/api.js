import axios from 'axios'
import { message } from 'antd'

// TODO: Add proper environment configuration
const API_PROTOCOL = process.env.REACT_APP_API_PROTOCOL || 'http'
const API_URL = process.env.REACT_APP_API_URL || 'localhost:4242'

const buildFilePath = (file) => {
  if (!file) return ''
  if (file.folderPath) return file.folderPath + file.name
  if (file.path) return file.path
  if (file.originFileObj && file.originFileObj.path) {
    return file.originFileObj.path
  }
  return file.name
}

const hasBrowserFile = (file) =>
  file && file.originFileObj instanceof File

export async function getNeuroglancerViewer (image, label, scales) {
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
function handleError (error) {
  if (error.response) {
    throw new Error(
      `${error.response.status}: ${error.response.data?.detail?.data || error.response.statusText}`
    )
  }
  throw error
}

export async function makeApiRequest (url, method, data = null) {
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

export async function startModelTraining (
  trainingConfig,
  logPath
) {
  try {
    const data = JSON.stringify({
      arguments: {
        // nproc_per_node: 4,
        // master_port: 2345,
        // distributed: "",
      },
      logPath,
      trainingConfig
    })

    return makeApiRequest('start_model_training', 'post', data)
  } catch (error) {
    handleError(error)
  }
}

export async function stopModelTraining () {
  try {
    await axios.post(
      `${API_PROTOCOL}://${API_URL}/stop_model_training`
    )
  } catch (error) {
    handleError(error)
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

export async function getTensorboardURL () {
  return makeApiRequest('get_tensorboard_url', 'get')
}

export async function startModelInference (
  // configurationYamlFile,
  inferenceConfig,
  outputPath,
  checkpointPath
) {
  try {
    const data = JSON.stringify({
      arguments: {
        // inference: " ",
        checkpoint: checkpointPath
      },
      outputPath,
      inferenceConfig
    })

    const res = await axios.post(
      `${API_PROTOCOL}://${API_URL}/start_model_inference`,
      data
    )
    return res.data
  } catch (error) {
    handleError(error)
  }
}

export async function stopModelInference () {
  try {
    await axios.post(
      `${API_PROTOCOL}://${API_URL}/stop_model_inference`
    )
  } catch (error) {
    handleError(error)
  }
}

export async function queryChatBot (query) {
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

export async function clearChat () {
  try {
    await axios.post(
      `${process.env.REACT_APP_API_PROTOCOL}://${process.env.REACT_APP_API_URL}/chat/clear`
    )
  } catch (error) {
    handleError(error)
  }
}
