import React, { useContext, useEffect, useState } from "react";
import Dragger from "../components/Dragger";
import { Button, Input, Select, Space, Typography } from "antd";
import { ArrowRightOutlined } from "@ant-design/icons";
import { AppContext } from "../contexts/GlobalContext";
import "./DataLoader.css";

const { Title } = Typography;

function DataLoader(props) {
  const context = useContext(AppContext);
  const [currentImage, setCurrentImage] = useState(null);
  const [currentLabel, setCurrentLabel] = useState(null);
  const [scales, setScales] = useState("30,6,6");
  const { fetchNeuroglancerViewer } = props;

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
    }
  }, [context.files]);

  return (
    <Space
      direction="vertical"
      size="small"
      align="start"
      style={{ margin: "7px", display: "flex" }}
    >
      <Dragger/>
      <Title level={5} style={{ marginBottom: "-5px" }}>
        Image
      </Title>
      <Select
        onChange={handleImageChange}
        options={context.imageFileList.map((file) => ({
          label: file.name,
          value: file.uid,
        }))}
        style={{ width: "185px" }}
        placeholder="Select image"
        size="middle"
        allowClear={true}
      />

      <Title level={5} style={{ marginTop: "0px", marginBottom: "-5px" }}>
        Label
      </Title>
      <Select
        onChange={handleLabelChange}
        options={context.labelFileList.map((file) => ({
          label: file.name,
          value: file.uid,
        }))}
        style={{ width: "185px" }}
        placeholder="Select label"
        size="middle"
        allowClear={true}
      />

      <Title level={5} style={{ marginTop: "0px", marginBottom: "-5px" }}>
        Scales
      </Title>
      <Input
        placeholder="Input in z, y, x order"
        allowClear
        onChange={handleInputScales}
        style={{ width: "185px" }}
      />
      <Button
        type="primary"
        onClick={handleVisualizeButtonClick}
        icon={<ArrowRightOutlined />}
        style={{ width: "185px" }}
      >
        Visualize
      </Button>
    </Space>
  );
}

export default DataLoader;
