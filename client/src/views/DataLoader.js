import React, { useState, useEffect, useContext } from "react";
import Dragger from "../components/Dragger";
import { Button, Space, Select, Divider } from "antd";
import { ArrowRightOutlined } from "@ant-design/icons";
import { AppContext } from "../contexts/GlobalContext";
import "./DataLoader.css";
import axios from "axios";
import { getNeuroglancerViewer } from "../utils/api";

function DataLoader() {
  const context = useContext(AppContext);
  const [currentImage, setCurrentImage] = useState(null);
  const [currentLabel, setCurrentLabel] = useState(null);

  const [currentImagePath, setCurrentImagePath] = useState("");
  const [currentLabelPath, setCurrentLabelPath] = useState("");

  /*const getImagePath = async () => {
    const data = { currentImagePath }
    try {
      const response = await axios.post('/imagepath', {data});
    } catch(error) {
      console.error(error);
    }
  };

  const getLabelPath = async () => {
    const data  = { currentLabelPath }
    try {
      const response = await axios.post('/labelpath', {data})
    } catch(error) {
      console.error(error);
    }
  };*/

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
    // console.log(currentImage, currentLabel, currentImagePath, currentLabelPath);
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
  const [fileList, setFileList] = useState([]);

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
          options={fileList}
          placeholder="Select image"
          size="middle"
          allowClear={true}
        />
        <label>Label:</label>
        <Select
          onChange={handleLabelChange}
          options={fileList}
          placeholder="Select label"
          size="middle"
          allowClear={true}
        />
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
