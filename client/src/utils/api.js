import axios from "axios";
import { message } from "antd";

export async function getNeuroglancerViewer(
  image,
  label,
  scales
  // image_path,
  // label_path
) {
  // console.log(image, label, image_path, label_path);
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

    /*if (error.response) {
      throw new Error(
          `${error.response.status}: ${error.response.data?.detail?.error}`
      );

    }
    throw error;*/
  }
}

export async function startModelTraining(
  inputs,
  configurationYamlFile,
  trainingConfig,
  outputPath,
  logPath
) {
  try {
    let data = JSON.stringify({
      arguments: {
        // "config-file":
        //   "../pytorch_connectomics/configs/Lucchi-Mitochondria.yaml",
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

export async function startModelInference(
  inputs,
  configurationYamlFile,
  outputPath,
  checkpointPath
) {
  try {
    let data = JSON.stringify({
      arguments: {
        "config-file":
          "../pytorch_connectomics/configs/Lucchi-Mitochondria.yaml",
        inference: "",
        checkpoint: checkpointPath,
      },
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
