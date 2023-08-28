import React, { useContext, useEffect, useState } from "react";
import Dragger from "../components/Dragger";
import { Button, Input, Select, Space } from "antd";
import { ArrowRightOutlined } from "@ant-design/icons";
import { AppContext } from "../contexts/GlobalContext";
import "./DataLoader.css";
import { checkFiles } from "../utils/api";

function DataLoader(props) {
  const context = useContext(AppContext);
  const [currentImage, setCurrentImage] = useState(null);
  const [currentLabel, setCurrentLabel] = useState(null);
  const [scales, setScales] = useState("30,6,6");
  const { fetchNeuroglancerViewer } = props;

  const fetchFiles = async (files) => {
    try {
      await Promise.all(
        files.map(async (file) => {
          try {
            const data = await checkFiles(file);
            console.log(data);
            if (data) {
              context.setLabelFileList((prevLabelList) => [
                ...prevLabelList,
                file,
              ]);
              // context.setLabelFileList(file);
            } else {
              context.setImageFileList((prevImageList) => [
                ...prevImageList,
                file,
              ]);
              // context.setImageFileList(file);
            }
          } catch (error) {
            console.error(error);
          }
        })
      );
    } catch (e) {
      console.log(e);
    }
  };

  const [imageFileList, setImageFileList] = useState([]);
  const [labelFileList, setLabelFileList] = useState([]);

  const handleVisualizeButtonClick = async (event) => {
    event.preventDefault();
    context.setCurrentImage(currentImage);
    context.setCurrentLabel(currentLabel);
    fetchNeuroglancerViewer(
      currentImage,
      currentLabel,
      scales.split(",").map(Number)
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

  const handleInputScales = (event) => {
    setScales(event.target.value);
  };

  useEffect(() => {
    if (context.files) {
      context.setFileList(
        context.files.map((file) => ({
          label: file.name,
          value: file.uid,
        }))
      );
      fetchFiles(context.files);
    }
  }, [context.files]);

  return (
    <Space wrap size="large" style={{ margin: "7px" }}>
      <Space size="middle">
        <Dragger />
      </Space>
      <Space wrap size="middle">
        <label style={{ width: "185px" }}>
          Image:
          <Select
            onChange={handleImageChange}
            //options={context.fileList}
            options={context.imageFileList}
            placeholder="Select image"
            size="middle"
            allowClear={true}
          />
        </label>
        <label>
          Label:
          <Select
            onChange={handleLabelChange}
            //options={context.fileList}
            options={context.labelFileList}
            placeholder="Select label"
            size="middle"
            allowClear={true}
          />
        </label>
        <label>
          Scales:
          <Input
            placeholder="Input in z, y, x order"
            allowClear
            onChange={handleInputScales}
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
