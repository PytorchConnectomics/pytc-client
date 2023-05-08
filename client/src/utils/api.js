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
