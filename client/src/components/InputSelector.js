import { Form, Input, InputNumber, Select } from "antd";
import React, { useContext, useState } from "react";
import { AppContext } from "../contexts/GlobalContext";

function InputSelector(props) {
  const context = useContext(AppContext);
  const { fileList } = props;
  console.log(fileList, context.files);

  return (
    <div>
      <Form
        labelCol={{
          span: 4,
        }}
        wrapperCol={{
          span: 14,
        }}
        layout="horizontal"
        style={{
          maxWidth: 600,
        }}
      >
        <Form.Item label="Input Images">
          <Select
            mode="multiple"
            allowClear
            style={{
              width: "100%",
            }}
            placeholder="Please select"
            // onChange={handleImageChange}
            // allowClear={true}
            options={context.fileList}
            size="middle"
          />
        </Form.Item>
      </Form>
    </div>
  );
}
export default InputSelector;
