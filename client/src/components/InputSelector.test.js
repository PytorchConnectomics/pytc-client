import React from "react";
import { render, screen } from "@testing-library/react";

import InputSelector from "./InputSelector";
import { AppContext } from "../contexts/GlobalContext";

jest.mock("antd", () => {
  const Form = ({ children }) => <form>{children}</form>;
  Form.Item = ({ label, children, help }) => (
    <div>
      {label}
      {children}
      {help ? <div>{help}</div> : null}
    </div>
  );

  return {
    Form,
    Space: ({ children }) => <div>{children}</div>,
  };
});

jest.mock("./UnifiedFileInput", () => (props) => (
  <input
    aria-label={props.placeholder}
    data-selection-type={props.selectionType}
    readOnly
    value={typeof props.value === "string" ? props.value : ""}
  />
));

jest.mock("./InlineHelpChat", () => () => null);

beforeAll(() => {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: jest.fn().mockImplementation((query) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: jest.fn(),
      removeListener: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    })),
  });
});

function renderWithContext(type) {
  const contextValue = {
    trainingState: {
      inputImage: "",
      inputLabel: "",
      outputPath: "",
      logPath: "",
      checkpointPath: "",
      setInputImage: jest.fn(),
      setInputLabel: jest.fn(),
      setOutputPath: jest.fn(),
      setLogPath: jest.fn(),
      setCheckpointPath: jest.fn(),
    },
    inferenceState: {
      inputImage: "",
      inputLabel: "/tmp/stale-label.tif",
      outputPath: "",
      logPath: "",
      checkpointPath: "",
      setInputImage: jest.fn(),
      setInputLabel: jest.fn(),
      setOutputPath: jest.fn(),
      setLogPath: jest.fn(),
      setCheckpointPath: jest.fn(),
    },
  };

  return render(
    <AppContext.Provider value={contextValue}>
      <InputSelector type={type} />
    </AppContext.Provider>,
  );
}

describe("InputSelector", () => {
  it("shows an input label field for training", () => {
    renderWithContext("training");

    expect(screen.getByText("Input Label")).toBeTruthy();
  });

  it("does not show an input label field for inference", () => {
    renderWithContext("inference");

    expect(screen.queryByText("Input Label")).toBeNull();
    expect(screen.queryByText("Input Label (Optional)")).toBeNull();
  });
});
