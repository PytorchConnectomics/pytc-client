import axios from "axios";
export async function getNeuroglancerViewer(file) {
  try {
    console.log(file);
    const fmData = new FormData();
    fmData.append("file", file);

    const res = await axios.post(
      `${process.env.REACT_APP_API_PROTOCOL}://${process.env.REACT_APP_API_URL}/neuroglancer`,
      fmData
    );
    console.log(file, res.data);
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
