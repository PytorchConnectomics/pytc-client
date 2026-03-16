// global localStorage
import React, { useContext, useEffect, useMemo, useState } from "react";
import { Alert, Button, message, Steps, theme } from "antd";
import YamlFileUploader from "./YamlFileUploader";
import YamlFileEditor from "./YamlFileEditor";
import InputSelector from "./InputSelector";
import { AppContext } from "../contexts/GlobalContext";

function Configurator(props) {
  const { fileList, type } = props;
  const context = useContext(AppContext);
  const [current, setCurrent] = useState(0);
  const [hasAttemptedAdvance, setHasAttemptedAdvance] = useState(false);
  const storageKey = `configStep:${type}`;

  const next = () => {
    if (missingByStep.length > 0) {
      setHasAttemptedAdvance(true);
      return;
    }
    setCurrent(current + 1);
    setHasAttemptedAdvance(false);
  };

  const prev = () => {
    setCurrent(current - 1);
  };

  const handleDoneButton = () => {
    if (missingByStep.length > 0) {
      setHasAttemptedAdvance(true);
      return;
    }
    const label = type === "training" ? "Training" : "Inference";
    message.success(`${label} configuration saved.`);
    if (type === "training") {
      localStorage.setItem("trainingConfig", context.trainingConfig);
    } else {
      localStorage.setItem("inferenceConfig", context.inferenceConfig);
    }
  };

  const getPathValue = (val) => {
    if (!val) return "";
    if (typeof val === "string") return val;
    return val.path || val.folderPath || "";
  };

  const missingInputs = useMemo(() => {
    const missing = [];
    if (!getPathValue(context.inputImage)) missing.push("input image");
    if (!getPathValue(context.inputLabel)) missing.push("input label");
    if (!getPathValue(context.outputPath)) missing.push("output path");
    if (type === "inference" && !getPathValue(context.checkpointPath)) {
      missing.push("checkpoint path");
    }
    return missing;
  }, [
    context.inputImage,
    context.inputLabel,
    context.outputPath,
    context.checkpointPath,
    type,
  ]);

  const hasConfig =
    type === "training"
      ? Boolean(context.trainingConfig)
      : Boolean(context.inferenceConfig);

  const missingBase = useMemo(
    () => (hasConfig ? [] : ["base configuration (preset or upload)"]),
    [hasConfig],
  );

  const missingByStep = useMemo(() => {
    if (current === 0) return missingInputs;
    if (current === 1) return missingBase;
    if (current === 2) return missingBase;
    return [];
  }, [current, missingInputs, missingBase]);

  useEffect(() => {
    const stored = localStorage.getItem(storageKey);
    if (stored !== null) {
      const parsed = Number(stored);
      if (!Number.isNaN(parsed) && parsed >= 0 && parsed <= 2) {
        setCurrent(parsed);
      }
    }
  }, [storageKey]);

  useEffect(() => {
    localStorage.setItem(storageKey, String(current));
  }, [current, storageKey]);

  const items = [
    {
      title: "Set Inputs",
      content: <InputSelector fileList={fileList} type={type} />,
    },
    {
      title: "Base Configuration",
      content: <YamlFileUploader type={type} />,
    },
    {
      title: "Advanced Configuration",
      content: <YamlFileEditor type={type} />,
    },
  ];

  const { token } = theme.useToken();

  const contentStyle = {
    minHeight: "260px",
    textAlign: "left",
    color: token.colorTextTertiary,
    backgroundColor: token.colorFillAlter,
    borderRadius: token.borderRadiusLG,
    border: `1px dashed ${token.colorBorder}`,
    marginTop: 12,
  };

  return (
    <div style={{ marginTop: 12 }}>
      <Steps size="small" current={current} items={items} />
      <div style={contentStyle}>{items[current].content}</div>
      <div style={{ marginTop: 24 }}>
        {current > 0 && (
          <Button style={{ marginRight: "8px" }} onClick={() => prev()}>
            Previous
          </Button>
        )}
        {current < items.length - 1 && (
          <Button type="primary" onClick={() => next()}>
            Next
          </Button>
        )}
        {current === items.length - 1 && (
          <Button type="primary" onClick={handleDoneButton}>
            Done
          </Button>
        )}
      </div>
      {hasAttemptedAdvance && missingByStep.length > 0 && (
        <Alert
          style={{ marginTop: 12 }}
          type="warning"
          showIcon
          message={`Before you continue, add: ${missingByStep.join(", ")}`}
        />
      )}
    </div>
  );
}

export default Configurator;
