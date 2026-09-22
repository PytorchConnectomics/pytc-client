import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import FilePickerModal from "./FilePickerModal";
import { apiClient } from "../api";
import { QueryClientProvider } from "@tanstack/react-query";
import { createAppQueryClient } from "../queryClient";

jest.mock("../api", () => ({
  apiClient: {
    get: jest.fn(),
    post: jest.fn(),
    defaults: { baseURL: "http://localhost:4242" },
  },
}));

describe("FilePickerModal", () => {
  const renderPicker = (props = {}) => {
    const queryClient = createAppQueryClient();
    return render(
      <QueryClientProvider client={queryClient}>
        <FilePickerModal
          visible
          onCancel={jest.fn()}
          onSelect={jest.fn()}
          {...props}
        />
      </QueryClientProvider>,
    );
  };

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

    renderPicker();

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

  it("requests bounded pages for the visible folder", async () => {
    apiClient.get
      .mockResolvedValueOnce({
        data: {
          items: Array.from({ length: 100 }, (_, index) => ({
            id: index + 1,
            name: `volume-${index + 1}.tif`,
            path: "root",
            is_folder: false,
          })),
          total: 101,
          offset: 0,
          limit: 100,
          has_more: true,
        },
      })
      .mockResolvedValueOnce({
        data: {
          items: [
            {
              id: 101,
              name: "volume-101.tif",
              path: "root",
              is_folder: false,
            },
          ],
          total: 101,
          offset: 100,
          limit: 100,
          has_more: false,
        },
      });

    renderPicker();

    await waitFor(() => expect(apiClient.get).toHaveBeenCalled());
    expect(apiClient.get.mock.calls[0][1].params).toEqual({
      parent: "root",
      offset: 0,
      limit: 100,
      volume_only: false,
    });
    expect(apiClient.get.mock.calls[0][1].signal).toBeDefined();
    expect(apiClient.get.mock.calls.length).toBeLessThanOrEqual(2);
  });
});
