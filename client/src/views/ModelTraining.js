import React, { useState } from "react";
import {
  Button,
  Cascader,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Radio,
  Select,
  Switch,
  TreeSelect,
} from "antd";
import axios from "axios";
import {
  getNeuroglancerViewer,
  startModelTraining,
  startTensorboard,
} from "../utils/api";

function ModelTraining() {
  const [isTraining, setIsTraining] = useState(false);
  const [tensorboardURL, setTensorboardURL] = useState(null);
  const handleStartButton = () => {
    try {
      const res = startModelTraining();
      console.log(res);
    } catch (e) {
      console.log(e);
    }
  };

  const handleStopButton = () => {};

  const handleTensorboardButton = async () => {
    try {
      const res = await startTensorboard();
      console.log(res);
      setTensorboardURL(res);
    } catch (e) {
      console.log(e);
    }
  };
  console.log(tensorboardURL);
  const [componentSize, setComponentSize] = useState("default");
  const onFormLayoutChange = ({ size }) => {
    setComponentSize(size);
  };

  return (
    <>
      <div>
        {"ModelTraining"}

        <Form
          labelCol={{
            span: 4,
          }}
          wrapperCol={{
            span: 14,
          }}
          layout="horizontal"
          size="default"
          style={{
            maxWidth: 600,
          }}
        >
          <Form.Item label="Model">
            <Input />
          </Form.Item>
          <Form.Item label="Select">
            <Select>
              <Select.Option value="demo">Demo</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item label="TreeSelect">
            <TreeSelect
              treeData={[
                {
                  title: "Light",
                  value: "light",
                  children: [
                    {
                      title: "Bamboo",
                      value: "bamboo",
                    },
                  ],
                },
              ]}
            />
          </Form.Item>
          <Form.Item label="Cascader">
            <Cascader
              options={[
                {
                  value: "zhejiang",
                  label: "Zhejiang",
                  children: [
                    {
                      value: "hangzhou",
                      label: "Hangzhou",
                    },
                  ],
                },
              ]}
            />
          </Form.Item>
          <Form.Item label="DatePicker">
            <DatePicker />
          </Form.Item>
          <Form.Item label="InputNumber">
            <InputNumber />
          </Form.Item>
          <Form.Item label="Switch" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item label="Button">
            <Button>Button</Button>
          </Form.Item>
        </Form>

        <Button onClick={handleStartButton}>Start Trainig</Button>
        <Button onClick={handleStopButton}>Stop Training</Button>
        <Button onClick={handleTensorboardButton}>Tensorboard</Button>
      </div>
      {tensorboardURL && (
        <iframe
          width="100%"
          height="800"
          frameBorder="0"
          scrolling="no"
          src={tensorboardURL}
        />
      )}
    </>
  );
}

export default ModelTraining;
