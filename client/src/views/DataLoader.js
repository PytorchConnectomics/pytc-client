import React, { useState, useEffect, useContext } from "react";
import Dragger from "../components/Dragger";
import { Button, Space, Select, Divider } from "antd";
import { ArrowRightOutlined } from "@ant-design/icons";
import { AppContext } from "../contexts/GlobalContext";
import "./DataLoader.css";
import axios from "axios";

function DataLoader() {
  const context = useContext(AppContext);
  const [currentImage, setCurrentImage] = useState(null);
  const [currentLabel, setCurrentLabel] = useState(null);

  const [currentImagePath,setCurrentImagePath] = useState('');
  const [currentLabelPath, setCurrentLabelPath] = useState('');

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

  const handleButtonClick = async (event) => {
    event.preventDefault();

    context.setCurrentImage(currentImage);
    context.setCurrentLabel(currentLabel);
    context.setCurrentImagePath(currentImagePath);
    context.setCurrentLabelPath(currentLabelPath);

    try {
      const response_im = await axios.post('http://localhost:8000/neuroglancer',
          { input1: currentImagePath });
      const response_lab = await axios.post('http://localhost:8000/neuroglancer',
          { input2: currentLabelPath });
      console.log(response_im.data);
      console.log(response_lab.data)
    } catch (error) {
      console.error(error);
    }
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
  }

  const handleLabelPath = (e) => {
    setCurrentLabelPath(e.target.value);
  }

/*  const handleImagePath = async () => {
    try {
      const response = await axios.post('http://localhost:8000/neuroglancer',
          {currentImagePath})
      setCurrentImagePath(response.data)
    } catch (error) {
      console.error(error)
    }
  }

  const handleLabelPath = async () => {
    try {
      const response = await axios.post('http://localhost:8000/neuroglancer',
          {currentLabelPath})
      setCurrentLabelPath(response.data)
    } catch (error) {
      console.error(error)
    }
  }*/



  const [fileList, setFileList] = useState([]);

  useEffect(() => {
    if (context.files) {
      setFileList(
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
        <label>Image:
          <Select
            onChange={handleImageChange}
            options={fileList}
            placeholder="Select image"
            size="middle"
            allowClear={true}
          />
        </label>
        <label> Image Path:
          <textarea className= "textarea"
            value = {currentImagePath}
            placeholder = "Enter Image Base Path..."
                    onChange={handleImagePath}
          />
        </label>
        <label>Label:
          <Select
            onChange={handleLabelChange}
            options={fileList}
            placeholder="Select label"
            size="middle"
            allowClear={true}
          />
        </label>
        <label> Label Path:
          <textarea className= "textarea"
            value = {currentLabelPath}
            placeholder = "Enter Label Base Path..."
                    onChange={handleLabelPath}
          />
        </label>
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
