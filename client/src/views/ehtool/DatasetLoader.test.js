import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";

import DatasetLoader from "./DatasetLoader";

beforeEach(() => {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: jest.fn((listener) => listener({ matches: false })),
      removeListener: jest.fn(),
      addEventListener: jest.fn((event, listener) => {
        if (event === "change") listener({ matches: false });
      }),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    }),
  });
});

jest.mock("../../components/UnifiedFileInput", () => {
  return function MockUnifiedFileInput({ placeholder, value, onChange }) {
    return (
      <input
        aria-label={placeholder}
        value={value?.path || value || ""}
        onChange={(event) => onChange?.({ path: event.target.value })}
      />
    );
  };
});

describe("DatasetLoader", () => {
  it("does not show global project suggestions when no workflow data exists", () => {
    render(<DatasetLoader onLoad={jest.fn()} loading={false} />);

    expect(screen.getByText("What should I proofread?")).toBeTruthy();
    expect(screen.queryByText("mito25-paper-loop-smoke")).toBeNull();
    expect(screen.queryByText("Start proofreading this pair")).toBeNull();
    expect(screen.queryByText("current project")).toBeNull();
  });

  it("offers only the current workflow pair when workflow data exists", () => {
    const onLoad = jest.fn();
    render(
      <DatasetLoader
        onLoad={onLoad}
        loading={false}
        workflow={{
          title: "prepilot_nucmm_mouse",
          image_path: "/projects/prepilot/data/image/train",
          label_path: "/projects/prepilot/data/label/train",
        }}
      />,
    );

    expect(screen.getByText("current project")).toBeTruthy();
    expect(screen.getByText("prepilot_nucmm_mouse")).toBeTruthy();
    expect(screen.getByText("train + train")).toBeTruthy();
    expect(screen.queryByText("mito25-paper-loop-smoke")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Start with current data" }));

    expect(onLoad).toHaveBeenCalledWith(
      "/projects/prepilot/data/image/train",
      "/projects/prepilot/data/label/train",
      "prepilot_nucmm_mouse",
    );
  });
});
