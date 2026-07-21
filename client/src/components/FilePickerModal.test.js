import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import FilePickerModal from "./FilePickerModal";
import { apiClient } from "../api";

jest.mock("../api", () => ({
  apiClient: {
    get: jest.fn(),
    post: jest.fn(),
    defaults: { baseURL: "http://localhost:4242" },
  },
}));

describe("FilePickerModal", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    window.matchMedia = jest.fn().mockImplementation((query) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: jest.fn(),
      removeListener: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    }));
  });

  it("keeps a retryable error state when files cannot be loaded", async () => {
    apiClient.get
      .mockRejectedValueOnce(new Error("Network Error"))
      .mockResolvedValueOnce({ data: [] });

    render(
      <FilePickerModal visible onCancel={jest.fn()} onSelect={jest.fn()} />,
    );

    expect(await screen.findByText("Files unavailable")).toBeTruthy();
    expect(
      screen.getByText("Check the server connection and try again."),
    ).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /try again/i }));

    await waitFor(() => expect(apiClient.get).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect(screen.queryByText("Files unavailable")).toBeNull(),
    );
  });
});
