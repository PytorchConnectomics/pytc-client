import axios from "axios";
import {message} from "antd";
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
    message.error(`Invalid Data Path(s). Be sure to include all "/" and that data path is correct.`);

    /*if (error.response) {
      throw new Error(
          `${error.response.status}: ${error.response.data?.detail?.error}`
      );

    }
    throw error;*/
  }
}
