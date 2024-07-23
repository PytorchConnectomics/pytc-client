import axios from 'axios'
import { message } from 'antd'

export async function getNeuroglancerViewer (image, label, scales) {
  try {
    const data = JSON.stringify({
      image: image.folderPath + image.name,
      label: label.folderPath + label.name,
      scales
    })
    const res = await axios.post(
      `${process.env.REACT_APP_API_PROTOCOL}://${process.env.REACT_APP_API_URL}/neuroglancer`,
      data
    )
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
      `${error.response.status}: ${error.response.data?.detail?.data}`
    )
  };
  throw error
}
export async function makeApiRequest (url, method, data = null) {
  try {
    const fullUrl = `${process.env.REACT_APP_API_PROTOCOL}://${process.env.REACT_APP_API_URL}/${url}`;
    const res = await axios[method](fullUrl, data)
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
      `${process.env.REACT_APP_API_PROTOCOL}://${process.env.REACT_APP_API_URL}/stop_model_training`
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
      `${process.env.REACT_APP_API_PROTOCOL}://${process.env.REACT_APP_API_URL}/start_model_inference`,
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
      `${process.env.REACT_APP_API_PROTOCOL}://${process.env.REACT_APP_API_URL}/stop_model_inference`
    )
  } catch (error) {
    handleError(error)
  }
}
