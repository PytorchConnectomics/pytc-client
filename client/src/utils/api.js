import axios from "axios";
export async function getNeuroglancerViewer(image, label, im_path, lab_path) {
  console.log(image, label, im_path, lab_path);
  try {
    let fmData = new FormData();

    image = im_path + image;
    label = lab_path + label;

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
