import React, { useState } from "react";
import { Steps, Button, theme, message } from "antd";
import YamlFileUploader from "./YamlFileUploader";
import InputSelector from "./InputSelector";

function Configurator(props) {
  const { fileList } = props;
  const [current, setCurrent] = useState(0);

  const next = () => {
    setCurrent(current + 1);
  };

  const prev = () => {
    setCurrent(current - 1);
  };

  const items = [
    {
      title: "Set Inputs",
      content: <InputSelector fileList={fileList} />,
    },
    {
      title: "Base Configuration",
      content: <YamlFileUploader />,
    },
    {
      title: "Advanced Configuration",
      // content: <Advanced />,
    },
  ];

  const { token } = theme.useToken();

  const contentStyle = {
    height: "260px",
    textAlign: "left",
    color: token.colorTextTertiary,
    backgroundColor: token.colorFillAlter,
    borderRadius: token.borderRadiusLG,
    border: `1px dashed ${token.colorBorder}`,
    marginTop: 0,
  };

  return (
    <>
      <Steps size="small" current={current} items={items} />
      <div style={contentStyle}>{items[current].content}</div>
      <div style={{ marginTop: 24 }}>
        {current < items.length - 1 && (
          <Button type="primary" onClick={() => next()}>
            Next
          </Button>
        )}
        {current === items.length - 1 && (
          <Button
            type="primary"
            onClick={() => message.success("Processing complete!")}
          >
            Done
          </Button>
        )}
        {current > 0 && (
          <Button style={{ margin: "0 8px" }} onClick={() => prev()}>
            Previous
          </Button>
        )}
      </div>
    </>
  );
}

export default Configurator;
