import axios from "axios";
import { message } from "antd";

export async function getNeuroglancerViewer(image, label, scales) {
  try {
    let data = JSON.stringify({
      image: image.folderPath + image.name,
      label: label.folderPath + label.name,
      scales: scales,
    });
    const res = await axios.post(
      `${process.env.REACT_APP_API_PROTOCOL}://${process.env.REACT_APP_API_URL}/neuroglancer`,
      data
    );
    return res.data;
  } catch (error) {
    message.error(
      `Invalid Data Path(s). Be sure to include all "/" and that data path is correct.`
    );
  }
}

export async function startModelTraining(
  configurationYamlFile,
  trainingConfig,
  outputPath,
  logPath
) {
  try {
    let data = JSON.stringify({
      arguments: {
        // nproc_per_node: 4,
        // master_port: 2345,
        // distributed: "",
      },
      logPath: logPath,
      trainingConfig: trainingConfig,
    });

    const res = await axios.post(
      `${process.env.REACT_APP_API_PROTOCOL}://${process.env.REACT_APP_API_URL}/start_model_training`,
      data
    );
    return res.data;
  } catch (error) {
    if (error.response) {
      throw new Error(
        `${error.response.status}: ${error.response.data?.detail?.error}`
      );
    }
    throw error;
  }
}

export async function stopModelTraining() {
  try {
    const res = await axios.post(
      `${process.env.REACT_APP_API_PROTOCOL}://${process.env.REACT_APP_API_URL}/stop_model_training`
    );
    return;
  } catch (error) {
    if (error.response) {
      throw new Error(
        `${error.response.status}: ${error.response.data?.detail?.error}`
      );
    }
    throw error;
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
  try {
    const res = await axios.get(
      `${process.env.REACT_APP_API_PROTOCOL}://${process.env.REACT_APP_API_URL}/get_tensorboard_url`
    );
    return res.data;
  } catch (error) {
    if (error.response) {
      throw new Error(
        `${error.response.status}: ${error.response.data?.detail?.error}`
      );
    }
    throw error;
  }
}

export async function checkFiles(file) {
  try {
    const res = await axios.post(
      `${process.env.REACT_APP_API_PROTOCOL}://${process.env.REACT_APP_API_URL}/check_files`,
      file
    );
    return res.data;
  } catch (error) {
    if (error.response) {
      throw new Error(
        `${error.response.status}: ${error.response.data?.detail?.error}`
      );
    }
    throw error;
  }
}

export async function startModelInference(
  configurationYamlFile,
  inferenceConfig,
  outputPath,
  checkpointPath
) {
  try {
    let data = JSON.stringify({
      arguments: {
        // inference: " ",
        checkpoint: checkpointPath,
      },
      outputPath: outputPath,
      inferenceConfig: inferenceConfig,
    });

    const res = await axios.post(
      `${process.env.REACT_APP_API_PROTOCOL}://${process.env.REACT_APP_API_URL}/start_model_inference`,
      data
    );
    return res.data;
  } catch (error) {
    if (error.response) {
      throw new Error(
        `${error.response.status}: ${error.response.data?.detail?.error}`
      );
    }
    throw error;
  }
}

export async function stopModelInference() {
  try {
    const res = await axios.post(
      `${process.env.REACT_APP_API_PROTOCOL}://${process.env.REACT_APP_API_URL}/stop_model_inference`
    );
    return;
  } catch (error) {
    if (error.response) {
      throw new Error(
        `${error.response.status}: ${error.response.data?.detail?.error}`
      );
    }
    throw error;
  }
}
