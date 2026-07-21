import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import Visualization from "./Visualization";
import { AppContext } from "../contexts/GlobalContext";
import { useWorkflow } from "../contexts/WorkflowContext";
import { QueryClientProvider } from "@tanstack/react-query";
import { createAppQueryClient } from "../queryClient";

jest.mock("../contexts/WorkflowContext", () => ({
  useWorkflow: jest.fn(),
}));

jest.mock("../api", () => ({
  apiClient: {
    get: jest.fn(),
    defaults: { baseURL: "http://localhost:4242" },
  },
  getNeuroglancerViewer: jest.fn(),
}));

describe("Visualization workflow defaults", () => {
  const renderWithQueryClient = (ui) => {
    const queryClient = createAppQueryClient();
    return render(ui, {
      wrapper: ({ children }) => (
        <QueryClientProvider client={queryClient}>
          {children}
        </QueryClientProvider>
      ),
    });
  };

  it("hydrates the canonical volume pair and voxel scales", async () => {
    const setCurrentImage = jest.fn();
    const setCurrentLabel = jest.fn();
    const setVisualizationScales = jest.fn();
    useWorkflow.mockReturnValue({
      workflow: {
        id: 1,
        image_path: "/project/data/raw",
        label_path: "/project/data/seg",
        metadata: {
          visualization_scales: [40, 8, 8],
          project_observation: {
            volume_sets: [
              {
                is_current: true,
                image_path: "/project/data/raw/train-01_image.h5",
                label_path:
                  "/project/data/seg/ground_truth/train-01_ground_truth.h5",
              },
            ],
          },
        },
      },
    });

    renderWithQueryClient(
      <AppContext.Provider
        value={{
          currentImage: null,
          currentLabel: null,
          visualizationScales: "",
          setCurrentImage,
          setCurrentLabel,
          setVisualizationScales,
        }}
      >
        <Visualization viewers={[]} setViewers={jest.fn()} />
      </AppContext.Provider>,
    );

    expect(
      screen.getByPlaceholderText("Please select or input image path").value,
    ).toBe("/project/data/raw/train-01_image.h5");
    expect(
      screen.getByPlaceholderText("Please select or input label path").value,
    ).toBe("/project/data/seg/ground_truth/train-01_ground_truth.h5");
    expect(screen.getByPlaceholderText("z,y,x nm").value).toBe("40,8,8");
    await waitFor(() =>
      expect(setCurrentImage).toHaveBeenCalledWith(
        "/project/data/raw/train-01_image.h5",
      ),
    );
    expect(setCurrentLabel).toHaveBeenCalledWith(
      "/project/data/seg/ground_truth/train-01_ground_truth.h5",
    );
    expect(setVisualizationScales).toHaveBeenCalledWith("40,8,8");
  });

  it("does not restore old workflow defaults while context is being reset", () => {
    const setCurrentImage = jest.fn();
    const setCurrentLabel = jest.fn();
    const setVisualizationScales = jest.fn();
    useWorkflow.mockReturnValue({
      workflow: {
        id: 7,
        image_path: "/project/train-01_image.h5",
        label_path: "/project/train-01_ground_truth.h5",
        metadata: { visualization_scales: [40, 8, 8] },
      },
    });
    const context = {
      currentImage: "/project/custom-image.h5",
      currentLabel: "/project/custom-label.h5",
      visualizationScales: "20,4,4",
      setCurrentImage,
      setCurrentLabel,
      setVisualizationScales,
    };
    const { rerender } = renderWithQueryClient(
      <AppContext.Provider value={context}>
        <Visualization viewers={[]} setViewers={jest.fn()} />
      </AppContext.Provider>,
    );

    rerender(
      <AppContext.Provider
        value={{
          ...context,
          currentImage: null,
          currentLabel: null,
          visualizationScales: "",
        }}
      >
        <Visualization viewers={[]} setViewers={jest.fn()} />
      </AppContext.Provider>,
    );

    expect(setCurrentImage).not.toHaveBeenCalled();
    expect(setCurrentLabel).not.toHaveBeenCalled();
    expect(setVisualizationScales).not.toHaveBeenCalled();
  });
});
