import React, { useState, useEffect, useContext } from "react";
import Dragger from "../components/Dragger";
import { Button, Space, Select, Divider } from "antd";
import { ArrowRightOutlined } from "@ant-design/icons";
import { AppContext } from "../contexts/GlobalContext";
import "./DataLoader.css";

function DataLoader() {
  const context = useContext(AppContext);
  const [currentImage, setCurrentImage] = useState(null);
  const [currentLabel, setCurrentLabel] = useState(null);
  const handleButtonClick = () => {
    context.setCurrentImage(currentImage);
    context.setCurrentLabel(currentLabel);
  };
  const handleImageChange = (value) => {
    console.log(`selected ${value}`);
    setCurrentImage(context.files.find((image) => image.uid === value));
  };
  const handleLabelChange = (value) => {
    console.log(`selected ${value}`);
    setCurrentLabel(context.files.find((file) => file.uid === value));
  };
  // const [fileList, setFileList] = useState([]);

  useEffect(() => {
    if (context.files) {
      context.setFileList(
        context.files.map((file) => ({
          label: file.name,
          value: file.uid,
        }))
      );
    }
  }, [context.files]);

  return (
    <Space wrap size="large" style={{ margin: "7px" }}>
      <Space size="middle">
        <Dragger />
      </Space>
      <Space wrap size="middle">
        <label>Image:</label>
        <Select
          onChange={handleImageChange}
          options={context.fileList}
          placeholder="Select image"
          size="middle"
          allowClear={true}
        />
        <label>Label:</label>
        <Select
          onChange={handleLabelChange}
          options={context.fileList}
          placeholder="Select label"
          size="middle"
          allowClear={true}
        />
        <Button
          type="primary"
          onClick={handleButtonClick}
          icon={<ArrowRightOutlined />}
        >
          Visualize
        </Button>
      </Space>
    </Space>
  );
}

export default DataLoader;
