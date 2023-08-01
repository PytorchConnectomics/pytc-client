import React, { useContext, useEffect, useState } from "react";
import Dragger from "../components/Dragger";
import { Button, Select, Space } from "antd";
import { ArrowRightOutlined } from "@ant-design/icons";
import { AppContext } from "../contexts/GlobalContext";
import "./DataLoader.css";
import { getNeuroglancerViewer } from "../utils/api";

function DataLoader() {
  const context = useContext(AppContext);
  const [currentImage, setCurrentImage] = useState(null);
  const [currentLabel, setCurrentLabel] = useState(null);

  const [currentImagePath, setCurrentImagePath] = useState("");
  const [currentLabelPath, setCurrentLabelPath] = useState("");

  const fetchNeuroglancerViewer = async (
    currentImage,
    currentLabel,
    currentImagePath,
    currentLabelPath
  ) => {
    try {
      const res = await getNeuroglancerViewer(
        currentImage,
        currentLabel,
        currentImagePath,
        currentLabelPath
      );
      console.log(res);
      context.setViewer(res);
    } catch (e) {
      console.log(e);
    }
  };
  const handleVisualizeButtonClick = async (event) => {
    event.preventDefault();

    context.setCurrentImage(currentImage);
    context.setCurrentLabel(currentLabel);
    context.setCurrentImagePath(currentImagePath);
    context.setCurrentLabelPath(currentLabelPath);
    fetchNeuroglancerViewer(
      currentImage,
      currentLabel,
      currentImagePath,
      currentLabelPath
    );
  };
  const handleImageChange = (value) => {
    console.log(`selected ${value}`);
    setCurrentImage(context.files.find((image) => image.uid === value));
  };
  const handleLabelChange = (value) => {
    console.log(`selected ${value}`);
    setCurrentLabel(context.files.find((file) => file.uid === value));
  };

  const handleImagePath = (e) => {
    setCurrentImagePath(e.target.value);
  };

  const handleLabelPath = (e) => {
    setCurrentLabelPath(e.target.value);
  };

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
        <label>
          Image:
          <Select
            onChange={handleImageChange}
            options={context.fileList}
            placeholder="Select image"
            size="middle"
            allowClear={true}
          />
        </label>
        <label>
          {" "}
          Image Path:
          <textarea
            className="textarea"
            value={currentImagePath}
            placeholder="Enter Image Base Path..."
            onChange={handleImagePath}
          />
        </label>
        <label>
          Label:
          <Select
            onChange={handleLabelChange}
            options={context.fileList}
            placeholder="Select label"
            size="middle"
            allowClear={true}
          />
        </label>
        <label>
          {" "}
          Label Path:
          <textarea
            className="textarea"
            value={currentLabelPath}
            placeholder="Enter Label Base Path..."
            onChange={handleLabelPath}
          />
        </label>

        <Button
          type="primary"
          onClick={handleVisualizeButtonClick}
          icon={<ArrowRightOutlined />}
        >
          Visualize
        </Button>
      </Space>
    </Space>
  );
}

export default DataLoader;
