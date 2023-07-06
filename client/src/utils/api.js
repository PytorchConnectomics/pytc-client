import axios from "axios";
export async function getNeuroglancerViewer(image, label) {
  console.log(image, label);
  try {
    let fmData = new FormData();
    fmData.append("image", image.name);
    fmData.append("label", label.name);

    const res = await axios.post(
      `${process.env.REACT_APP_API_PROTOCOL}://${process.env.REACT_APP_API_URL}/neuroglancer`,
      fmData
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

export async function startModelTraining() {
  try {
    let data = JSON.stringify({
      log_dir: "--log_dir=../../logs/tensorboard/",
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
  try{
    const res = await axios.post(
    `${process.env.REACT_APP_API_PROTOCOL}://${process.env.REACT_APP_API_URL}/stop_model_training`);
    return;
  } catch(error){
    if (error.response) {
      throw new Error(
        `${error.response.status}: ${error.response.data?.detail?.error}`
      );
    }
    throw error;
  }
}

export async function startTensorboard() {
  try {
    const res = await axios.get(
      `${process.env.REACT_APP_API_PROTOCOL}://${process.env.REACT_APP_API_URL}/start_tensorboard`
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
