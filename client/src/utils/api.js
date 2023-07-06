import axios from "axios";
export async function getNeuroglancerViewer(
  image,
  label,
  image_path,
  label_path
) {
  // console.log(image, label, image_path, label_path);
  try {
    let data = JSON.stringify({
      image: image_path + image.name,
      label: label_path + label.name,
    });
    const res = await axios.post(
      `${process.env.REACT_APP_API_PROTOCOL}://${process.env.REACT_APP_API_URL}/neuroglancer`,
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

export function stopModelTraining() {}

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
