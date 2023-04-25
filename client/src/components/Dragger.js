import React, { useContext } from "react";
import { message, Upload } from "antd";
import { InboxOutlined } from "@ant-design/icons";
import { AppContext } from "../contexts/GlobalContext";

function Dragger() {
  const context = useContext(AppContext);
  const { Dragger } = Upload;

  const onChange = (info) => {
    const { status } = info.file;
    if (status !== "uploading") {
      console.log(info.file, info.fileList);
    }
    if (status === "done") {
      console.log(info);
      message.success(`${info.file.name} file uploaded successfully.`);
      // context.setImages();
    } else if (status === "error") {
      message.error(`${info.file.name} file upload failed.`);
    }
  };
  const onDrop = (e) => {
    console.log("Dropped files", e.dataTransfer.files);
  };

  const uploadImage = async (options) => {
    const { onSuccess, onError, file } = options;
    console.log(file);
    // const fmData = new FormData();
    //
    // fmData.append("file", file);
    console.log(file, file.name);
    try {
      // const res = await axios.post(
      //   `${process.env.REACT_APP_API_PROTOCOL}://${process.env.REACT_APP_API_URL}/uploadImage`,
      //   fmData
      // );
      context.setImages([...context.images, file]);
      context.setCurrentImage(file);

      onSuccess("Ok");
      // console.log("server res: ", res);
    } catch (err) {
      console.log("Eroor: ", err);
      const error = new Error("Some error");
      onError({ err });
    }
  };
  return (
    <>
      <Dragger
        name="file"
        multiple={true}
        onChange={onChange}
        onDrop={onDrop}
        customRequest={uploadImage}
        style={{ maxHeight: "20vh" }}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">
          Click or drag file to this area to upload
        </p>
        {/*<p className="ant-upload-hint">*/}
        {/*  Support for a single or bulk upload. Strictly prohibited from uploading*/}
        {/*  company data or other banned files.*/}
        {/*</p>*/}
      </Dragger>
    </>
  );
}

export default Dragger;
