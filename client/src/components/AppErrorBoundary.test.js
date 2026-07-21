import React from "react";
import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import AppErrorBoundary from "./AppErrorBoundary";
import { logClientEvent } from "../logging/appEventLog";

jest.mock("../logging/appEventLog", () => ({ logClientEvent: jest.fn() }));

const Broken = ({ broken }) => {
  if (broken) throw new Error("render failed");
  return <div>Recovered content</div>;
};

describe("AppErrorBoundary", () => {
  let consoleError;

  beforeEach(() => {
    consoleError = jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    consoleError.mockRestore();
    jest.clearAllMocks();
  });

  it("shows recovery actions and records render failures", () => {
    const { rerender } = render(
      <AppErrorBoundary>
        <Broken broken />
      </AppErrorBoundary>,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "This screen could not be displayed",
    );
    expect(screen.getByText(/Error reference: ui-/)).toBeInTheDocument();
    expect(logClientEvent).toHaveBeenCalledWith(
      "ui_render_failed",
      expect.objectContaining({ source: "AppErrorBoundary" }),
    );

    rerender(
      <AppErrorBoundary>
        <Broken broken={false} />
      </AppErrorBoundary>,
    );
    fireEvent.click(screen.getByRole("button", { name: /try again/i }));

    expect(screen.getByText("Recovered content")).toBeInTheDocument();
  });
});
