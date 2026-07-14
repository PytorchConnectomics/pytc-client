import React from "react";
import { render, screen } from "@testing-library/react";

import YamlFileEditor from "./YamlFileEditor";
import YamlFileUploader from "./YamlFileUploader";
import { AppContext } from "../contexts/GlobalContext";
import { YamlContext } from "../contexts/YamlContext";

jest.mock("antd", () => {
  const React = require("react");
  const message = {
    success: jest.fn(),
    error: jest.fn(),
    warning: jest.fn(),
    info: jest.fn(),
  };

  const Space = ({ children }) => <div>{children}</div>;
  Space.Compact = ({ children }) => <div>{children}</div>;

  const Input = ({ value = "", onChange, ...props }) => (
    <input value={value} onChange={onChange} {...props} />
  );
  Input.TextArea = ({ value = "", onChange, ...props }) => (
    <textarea value={value} onChange={onChange} {...props} />
  );

  return {
    Button: ({ children, ...props }) => <button {...props}>{children}</button>,
    Col: ({ children }) => <div>{children}</div>,
    Divider: ({ children }) => <div>{children}</div>,
    Input,
    InputNumber: ({ value = "", ...props }) => (
      <input type="number" value={value} readOnly {...props} />
    ),
    Modal: ({ children, open, title }) =>
      open ? (
        <div>
          <div>{title}</div>
          {children}
        </div>
      ) : null,
    Row: ({ children }) => <div>{children}</div>,
    Select: ({ placeholder, value, options = [] }) => (
      <select
        aria-label={placeholder || "select"}
        value={value || ""}
        onChange={() => {}}
      >
        <option value="" />
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    ),
    Slider: ({ value = 0 }) => <input type="range" readOnly value={value} />,
    Space,
    Switch: ({ checked }) => (
      <input type="checkbox" readOnly checked={Boolean(checked)} />
    ),
    Upload: ({ children }) => <div>{children}</div>,
    message,
  };
});

jest.mock("@ant-design/icons", () => ({
  UploadOutlined: () => <span />,
}));

jest.mock("./InlineHelpChat", () => (props) => (
  <span data-testid="inline-help-chat">
    {`help:${props.label}:${props.yamlKey || "none"}`}
  </span>
));

jest.mock("../api", () => ({
  getConfigPresets: jest.fn().mockResolvedValue({ configs: [] }),
  getConfigPresetContent: jest.fn(),
  getModelArchitectures: jest.fn().mockResolvedValue({
    architectures: ["UNet"],
  }),
}));

function createAppContextValue({ trainingConfig = "", inferenceConfig = "" } = {}) {
  return {
    trainingConfig,
    setTrainingConfig: jest.fn(),
    inferenceConfig,
    setInferenceConfig: jest.fn(),
    trainingState: {
      uploadedYamlFile: "",
      selectedYamlPreset: "",
      inputImage: "",
      inputLabel: "",
      outputPath: "",
      setUploadedYamlFile: jest.fn(),
      setSelectedYamlPreset: jest.fn(),
      setConfigOriginPath: jest.fn(),
    },
    inferenceState: {
      uploadedYamlFile: "",
      selectedYamlPreset: "",
      inputImage: "",
      inputLabel: "",
      outputPath: "",
      checkpointPath: "",
      setUploadedYamlFile: jest.fn(),
      setSelectedYamlPreset: jest.fn(),
      setConfigOriginPath: jest.fn(),
    },
  };
}

const yamlContextValue = {
  numGPUs: 1,
  setNumGPUs: jest.fn(),
  numCPUs: 8,
  setNumCPUs: jest.fn(),
  solverSamplesPerBatch: 4,
  setSolverSamplesPerBatch: jest.fn(),
  learningRate: 0.001,
  setLearningRate: jest.fn(),
  inferenceSamplesPerBatch: 2,
  setInferenceSamplesPerBatch: jest.fn(),
  augNum: 4,
  setAugNum: jest.fn(),
};

describe("config help chat", () => {
  it("renders on-demand help for base training knobs", async () => {
    const trainingConfig = `
MODEL:
  ARCHITECTURE: UNet
SOLVER:
  SAMPLES_PER_BATCH: 4
SYSTEM:
  NUM_GPUS: 1
  NUM_CPUS: 8
`;

    render(
      <AppContext.Provider
        value={createAppContextValue({ trainingConfig })}
      >
        <YamlContext.Provider value={yamlContextValue}>
          <YamlFileUploader type="training" />
        </YamlContext.Provider>
      </AppContext.Provider>,
    );

    expect(
      await screen.findByText("help:Model architecture:MODEL.ARCHITECTURE"),
    ).toBeTruthy();
    expect(
      screen.getByText("help:Batch size:SOLVER.SAMPLES_PER_BATCH"),
    ).toBeTruthy();
    expect(screen.getByText("help:GPUs:SYSTEM.NUM_GPUS")).toBeTruthy();
    expect(screen.getByText("help:CPUs:SYSTEM.NUM_CPUS")).toBeTruthy();
  });

  it("renders on-demand help for advanced inference controls", async () => {
    const inferenceConfig = `
INFERENCE:
  SAMPLES_PER_BATCH: 2
  AUG_NUM: 4
  BLENDING: gaussian
  DO_EVAL: true
`;

    render(
      <AppContext.Provider
        value={createAppContextValue({ inferenceConfig })}
      >
        <YamlFileEditor type="inference" />
      </AppContext.Provider>,
    );

    expect(
      await screen.findByText("help:Batch size:INFERENCE.SAMPLES_PER_BATCH"),
    ).toBeTruthy();
    expect(
      screen.getByText("help:Blending:INFERENCE.BLENDING"),
    ).toBeTruthy();
    expect(screen.getByText("help:Eval mode:INFERENCE.DO_EVAL")).toBeTruthy();
  });
});
