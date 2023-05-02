import React, { useContext } from "react";
import { message, Upload } from "antd";
import { InboxOutlined } from "@ant-design/icons";
import { AppContext } from "../contexts/GlobalContext";

function Dragger() {
  const context = useContext(AppContext);
  const { Dragger } = Upload;

  const onChange = (info) => {
    const { status } = info.file;
    // if (status !== "uploading") {
    //   console.log(info.file, info.fileList);
    // }
    if (status === "done") {
      console.log("done");
      message.success(`${info.file.name} file uploaded successfully.`);
      context.setFiles(info.fileList);
    } else if (status === "error") {
      console.log("error");
      message.error(`${info.file.name} file upload failed.`);
    } else if (status === "removed") {
      console.log("removed");
      message.alert(`${info.file.name} file removed.`);
      context.setFiles(info.fileList);
    }
  };

  const uploadImage = async (options) => {
    const { onSuccess, onError } = options;
    try {
      onSuccess("Ok");
    } catch (err) {
      onError({ err });
    }
  };

  const beforeUpload = (file) => {
    console.log(file);
    const isTiff = file.type === "image/tiff";
    if (!isTiff) {
      message.error(`${file.name} is not a tiff file`);
    }
    return isTiff || Upload.LIST_IGNORE;
  };

  return (
    <Dragger
      name="file"
      multiple={true}
      onChange={onChange}
      customRequest={uploadImage}
      // beforeUpload={beforeUpload}
      style={{ maxHeight: "20vh" }}
    >
      <p className="ant-upload-drag-icon">
        <InboxOutlined />
      </p>
      <p className="ant-upload-text">
        Click or drag file to this area to upload
      </p>
    </Dragger>
  );
}

export default Dragger;
