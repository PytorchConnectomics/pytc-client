import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";

import UnifiedFileInput from "./UnifiedFileInput";

jest.mock("./FilePickerModal", () => (props) =>
  props.visible ? (
    <div data-testid="file-picker-modal" data-selection-type={props.selectionType} />
  ) : null,
);

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

describe("UnifiedFileInput", () => {
  it("opens the file picker from the folder icon", () => {
    render(
      <UnifiedFileInput
        value=""
        onChange={jest.fn()}
        placeholder="Image path"
        selectionType="fileOrDirectory"
      />,
    );

    fireEvent.click(screen.getByLabelText("Browse files"));

    const modal = screen.getByTestId("file-picker-modal");
    expect(modal).toBeTruthy();
    expect(modal.getAttribute("data-selection-type")).toBe("fileOrDirectory");
  });
});
