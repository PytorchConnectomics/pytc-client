import React, { useContext, useState } from "react";
import { Button, Input, message, Modal, Space, Upload } from "antd";
import { InboxOutlined } from "@ant-design/icons";
import { AppContext } from "../contexts/GlobalContext";
import { DEFAULT_IMAGE } from "../utils/utils";

function Dragger() {
  const context = useContext(AppContext);
  const { Dragger } = Upload;

  const getBase64 = (file) =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => resolve(reader.result);
      reader.onerror = (error) => reject(error);
    });
  const onChange = (info) => {
    const { status } = info.file;
    if (status === "done") {
      console.log("done");
      message.success(`${info.file.name} file uploaded successfully.`);
      context.setFiles([...info.fileList]);
    } else if (status === "error") {
      console.log("error");
      message.error(`${info.file.name} file upload failed.`);
    } else if (status === "removed") {
      console.log(info.fileList);
      context.setFiles([...info.fileList]);
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

  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewImage, setPreviewImage] = useState("");
  const [previewTitle, setPreviewTitle] = useState("");
  const [value, setValue] = useState("");
  const [fileUID, setFileUID] = useState(null);
  const [previewFileFolderPath, setPreviewFileFolderPath] = useState("");

  const handleText = (event) => {
    setValue(event.target.value);
  };

  const handleInputFolderPath = (event) => {
    setPreviewFileFolderPath(event.target.value);
  };
  const handleSubmit = (type) => {
    if (type === "name") {
      if (value !== "") {
        context.files.find((targetFile) => targetFile.uid === fileUID).name =
          value;
        context.fileList.find(
          (targetFile) => targetFile.value === fileUID
        ).label = value;
        setValue("");
      }
    } else if (type === "path") {
      if (previewFileFolderPath !== "") {
        context.files.find(
          (targetFile) => targetFile.uid === fileUID
        ).folderPath = previewFileFolderPath;
        setPreviewFileFolderPath("");
      }
    }
    setPreviewOpen(false);
  };
  const handleRevert = () => {
    let oldName = context.files.find((targetFile) => targetFile.uid === fileUID)
      .originFileObj.name;
    context.files.find((targetFile) => targetFile.uid === fileUID).name =
      oldName;
    context.fileList.find((targetFile) => targetFile.value === fileUID).label =
      oldName;
    setPreviewOpen(false);
  };

  const handleCancel = () => setPreviewOpen(false);

  const handlePreview = async (file) => {
    setFileUID(file.uid);
    if (!file.url && !file.preview) {
      if (file.type !== "image/tiff") {
        file.preview = await getBase64(file.originFileObj);
      } else {
        file.preview = file.thumbUrl;
      }
    }
    setPreviewImage(file.url || file.preview);
    setPreviewOpen(true);
    setPreviewTitle(
      file.name || file.url.substring(file.url.lastIndexOf("/") + 1)
    );
    if (
      context.files.find((targetFile) => targetFile.uid === file.uid) &&
      context.files.find((targetFile) => targetFile.uid === file.uid).folderPath
    ) {
      setPreviewFileFolderPath(
        context.files.find((targetFile) => targetFile.uid === file.uid)
          .folderPath
      );
    } else {
      setPreviewFileFolderPath("");
    }
  };

  const listItemStyle = {
    width: "185px",
  };

  const handleBeforeUpload = (file) => {
    // Create a URL for the thumbnail using object URL
    if (file.type !== "image/tiff") {
      file.thumbUrl = URL.createObjectURL(file);
    } else {
      file.thumbUrl = DEFAULT_IMAGE;
    }
    return true; // Allow the upload
  };

  return (
    <>
      <Dragger
        multiple={true}
        onChange={onChange}
        customRequest={uploadImage}
        beforeUpload={handleBeforeUpload}
        onPreview={handlePreview}
        listType="picture-card"
        style={{ maxHeight: "20vh", maxWidth: "10vw%" }}
        itemRender={(originNode, file) => (
          <div style={listItemStyle}>{originNode}</div>
        )}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">
          Click or drag file to this area to upload
        </p>
      </Dragger>
      <Modal
        open={previewOpen}
        title={previewTitle}
        footer={null}
        onCancel={handleCancel}
      >
        <Space direction="vertical">
          <Space.Compact block>
            <Input
              value={previewFileFolderPath}
              placeholder={"Please Enter Folder Path of this File"}
              onChange={handleInputFolderPath}
            />
            <Button onClick={() => handleSubmit("path")}>Submit</Button>
          </Space.Compact>
          <Space.Compact block>
            <Input
              value={value}
              placeholder={"Rename File"}
              onChange={handleText}
            />
            <Button onClick={() => handleSubmit("name")}>Submit</Button>
            <Button onClick={handleRevert}>Revert</Button>
          </Space.Compact>
          <img
            alt="example"
            style={{
              width: "100%",
            }}
            src={previewImage}
          />
        </Space>
      </Modal>
    </>
  );
}

export default Dragger;
