import React, { useContext, useState } from "react";
import { Button, Input, message, Modal, Space, Upload } from "antd";
import { InboxOutlined } from "@ant-design/icons";
import { AppContext } from "../contexts/GlobalContext";
import { DEFAULT_IMAGE } from "../utils/utils";

const path = require('path');

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
    if (status === 'done') {
      // Keep only the part of the pytc-relative path
      let pathSegments = info.file.originFileObj.path.split('/');
      let pytcClientIndex = pathSegments.indexOf('pytc-client');
      let relativePath = pathSegments.slice(pytcClientIndex).join('/');
      // Check if 'pytc-client' was found in the path
      if (pytcClientIndex === -1) {
        // Handle the error: 'pytc-client' not found
        console.error("Error: Please upload from the sample folder. File path: " + info.file.originFileObj.path);
        message.error(`${info.file.name} file upload failed.`);
        return;
      }

      message.success(`${info.file.name} file uploaded successfully.`);
      if (window.require) {
          const modifiedFile = { ...info.file, path: relativePath };
          context.setFiles([...context.files, modifiedFile]);
      } else {
          context.setFiles([...info.fileList]);
      }
      console.log('done');
    } else if (status === 'error') {
      console.log('error');
      message.error(`${info.file.name} file upload failed.`);
    } else if (status === 'removed') {
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
  const [fileType, setFileType] = useState("");

  const handleText = (event) => {
    setValue(event.target.value);
  };

  const handleDropdownChange = (event) => { 
    setFileType(event.target.value);
  };

  const fetchFile = async (file) => {
    try {
      if (fileType === "Label") {
        context.setLabelFileList((prevLabelList) => [...prevLabelList, file]);
      } else if (fileType === "Image") {
        context.setImageFileList((prevImageList) => [...prevImageList, file]);
      }
    } catch (error) {
      console.error(error);
    }
  };

  const handleSubmit = (type) => {
    console.log("submitting path", previewFileFolderPath);
  
    const fileInContext = context.files.find((targetFile) => targetFile.uid === fileUID);
    const fileInFileList = context.fileList.find((targetFile) => targetFile.value === fileUID);
  
    if (previewFileFolderPath !== "" && fileInContext) {
      fileInContext.folderPath = previewFileFolderPath;
      setPreviewFileFolderPath("");
    }
  
    if (value !== "" && fileInContext && fileInFileList) {
      fileInContext.name = value;
      fileInFileList.label = value;
      setValue("");
    }
  
    if (fileInContext) {
      fetchFile(fileInContext);
    } else {
      message.error("Error: File selection error. Please try again.");
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
        if (file.type !== 'image/tiff' || file.type !== 'image/tif') {
            if (file.path) { // Use the local path for Electron environment
                const fs = window.require('fs');
                const buffer = fs.readFileSync(file.path);
                const base64 = buffer.toString('base64');
                file.preview = `data:${file.type};base64,${base64}`;
            } else {
                file.preview = await getBase64(file.originFileObj);
            }
        } else {
            file.preview = file.thumbUrl;
        }
    }
    setPreviewImage(file.url || file.preview);
    setPreviewOpen(true);
    setPreviewTitle(file.name || file.url.substring(file.url.lastIndexOf('/') + 1));
    if (
      context.files.find(targetFile => targetFile.uid === file.uid) && 
      context.files.find(targetFile => targetFile.uid === file.uid).folderPath) 
      {
        processAndSetPath(
          context.files.find(targetFile => targetFile.uid === file.uid)
        .folderPath)
    } else {
      processAndSetPath(path.dirname(file.originFileObj.path));
    }
  };

  function processAndSetPath(path) {
    let pathSegments = path.split('/');
    let pytcClientIndex = pathSegments.indexOf('samples_pytc');

    // Check if 'pytc-client' was found in the path
    if (pytcClientIndex === -1) {
        // Handle the error: 'sample' not found
        console.error("Error: Please upload from the sample folder. File path: " + path);
        message.error(`${path.name} file upload failed.`);
        return false;
    }

    let relativePath = pathSegments.slice(pytcClientIndex).join('/');
    console.log("file uploaded: ", relativePath);
    setPreviewFileFolderPath(relativePath + "/");

    return true;
  };

  const listItemStyle = {
    width: "185px",
  };

  const handleBeforeUpload = (file) => {
    // Create a URL for the thumbnail using object URL
    if (file.type !== "image/tiff" || file.type !== "image/tif") {
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
          
        <select onChange={handleDropdownChange}>
          <option value="" disabled selected>Please select input filetype</option>
          <option value="Image">Image</option>
          <option value="Label">Label</option>
        </select>
        <Button onClick={() => handleSubmit()}>Submit</Button>
        <Button onClick={handleRevert}>Revert</Button>
      </Space.Compact>
          <Space.Compact block>
            <Input
              value={value}
              placeholder={"Alternative file name"}
              onChange={handleText}
            />
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
