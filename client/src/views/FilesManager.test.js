import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import FilesManager from "./FilesManager";
import { AppContext } from "../contexts/GlobalContext";
import { apiClient } from "../api";
import { openLocalFile } from "../electronApi";

jest.mock("../api", () => ({
  apiClient: {
    defaults: { baseURL: "http://localhost:4242" },
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
  },
}));

jest.mock("../electronApi", () => ({
  openLocalFile: jest.fn(),
  revealInFinder: jest.fn(),
}));

jest.mock("../components/FileTreeSidebar", () => () => null);
jest.mock("../components/FilePickerModal", () => ({
  visible,
  onSelect,
  title,
}) =>
  visible ? (
    <div>
      <div>{title}</div>
      <button
        type="button"
        onClick={() =>
          onSelect({
            name: "override-prediction.tif",
            physical_path: "/tmp/override/override-prediction.tif",
          })
        }
      >
        Choose mocked file
      </button>
    </div>
  ) : null,
);

jest.mock("../logging/appEventLog", () => ({
  logClientEvent: jest.fn(),
}));

const mockWorkflowContext = {
  workflow: { id: 1, stage: "setup" },
  updateWorkflow: jest.fn(),
  appendEvent: jest.fn(),
  refreshPreflight: jest.fn(),
  refreshAgentRecommendation: jest.fn(),
};

jest.mock("../contexts/WorkflowContext", () => ({
  useWorkflow: () => mockWorkflowContext,
}));

jest.mock("@ant-design/icons", () => {
  const Icon = () => <span />;
  return {
    FolderFilled: Icon,
    FolderOpenOutlined: Icon,
    FileOutlined: Icon,
    FileTextOutlined: Icon,
    ArrowLeftOutlined: Icon,
    AppstoreOutlined: Icon,
    BarsOutlined: Icon,
    UploadOutlined: Icon,
    EyeOutlined: Icon,
    LayoutOutlined: Icon,
    MoreOutlined: Icon,
    DeleteOutlined: Icon,
  };
});

jest.mock("antd", () => {
  const React = require("react");

  const Button = ({ children, icon, loading, type, ...props }) => (
    <button type="button" {...props}>
      {icon}
      {children}
    </button>
  );
  const Dropdown = ({ children }) => <div>{children}</div>;
  const Input = React.forwardRef((props, ref) => <input ref={ref} {...props} />);
  const Menu = ({ items = [], onClick }) => (
    <div>
      {items.map((item) =>
        item.type === "divider" ? null : (
          <button
            key={item.key}
            onClick={() => onClick?.({ key: item.key })}
            type="button"
          >
            {item.label}
          </button>
        ),
      )}
    </div>
  );
  const Breadcrumb = ({ children }) => <div>{children}</div>;
  Breadcrumb.Item = ({ children, onClick }) => (
    <button onClick={onClick} type="button">
      {children}
    </button>
  );
  const Modal = ({ children, open, title, footer }) =>
    open ? (
      <div role="dialog">
        {title ? <div>{title}</div> : null}
        {children}
        {footer ? <div>{footer}</div> : null}
      </div>
    ) : null;
  Modal.confirm = jest.fn();

  return {
    Button,
    Dropdown,
    Input,
    Modal,
    Menu,
    Breadcrumb,
    Empty: ({ description }) => <div>{description}</div>,
    Image: ({ alt }) => <img alt={alt} />,
    Spin: () => <div>Loading</div>,
    message: {
      error: jest.fn(),
      success: jest.fn(),
      warning: jest.fn(),
      info: jest.fn(),
    },
  };
});

const smokeSuggestion = {
  id: "mito25-paper-loop-smoke",
  name: "mito25-paper-loop-smoke",
  directory_path: "/tmp/mito25_paper_loop_smoke",
  description: "Curated smoke project",
  recommended: true,
  already_mounted: false,
  profile: {
    ready_for_smoke: true,
    counts: {
      image: 1,
      label: 1,
      prediction: 2,
      config: 1,
      checkpoint: 1,
    },
    schema: {
      mode: "closed_loop_ready",
      stages: {
        visualization: true,
        proofreading: true,
        training: true,
        evaluation: true,
      },
      primary_paths: {
        image: "data/image/mito25_smoke_im.h5",
        label: "data/seg/mito25_smoke_seg.h5",
        prediction: "predictions/baseline.tif",
        checkpoint: "checkpoints/checkpoint_00200.pth.tar",
        config: "configs/MitoEM.yaml",
      },
    },
    paired_examples: [
      {
        image: "data/image/mito25_smoke_im.h5",
        label: "data/seg/mito25_smoke_seg.h5",
      },
    ],
    examples: {
      image: ["data/image/mito25_smoke_im.h5"],
      label: ["data/seg/mito25_smoke_seg.h5"],
      prediction: ["predictions/baseline.tif"],
      checkpoint: ["checkpoints/checkpoint_00200.pth.tar"],
      config: ["configs/MitoEM.yaml"],
    },
    missing_roles: [],
  },
};

const imageOnlySuggestion = {
  id: "image-only-project",
  name: "image-only-project",
  directory_path: "/tmp/image_only_project",
  description: "Detected image volume",
  recommended: true,
  already_mounted: false,
  profile: {
    counts: { image: 1 },
    schema: {
      workable: true,
      mode: "image_only",
      stages: { visualization: true, proofreading: false },
      primary_paths: { image: "volume/raw_image.tif" },
    },
    examples: { image: ["volume/raw_image.tif"] },
    missing_roles: ["label"],
  },
};

const renderFilesManager = () =>
  render(
    <AppContext.Provider value={{ resetFileState: jest.fn() }}>
      <FilesManager />
    </AppContext.Provider>,
  );

const mockProjectSuggestionResponses = (suggestions) => {
  apiClient.get.mockImplementation((url) => {
    if (url === "/files/project-suggestions") {
      return Promise.resolve({ data: suggestions });
    }
    return Promise.resolve({ data: [] });
  });
};

describe("FilesManager", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockWorkflowContext.updateWorkflow.mockResolvedValue({});
    mockWorkflowContext.appendEvent.mockResolvedValue({});
    mockWorkflowContext.refreshPreflight.mockResolvedValue({});
    mockWorkflowContext.refreshAgentRecommendation.mockResolvedValue({});
  });

  it("loads root-level files with a parent-scoped request on initial render", async () => {
    apiClient.get.mockResolvedValue({ data: [] });

    renderFilesManager();

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith("/files", {
        params: { parent: "root" },
      });
    });

    expect(apiClient.get).not.toHaveBeenCalledWith("/files");
  });

  it("opens a confirmation modal before registering a suggested smoke project", async () => {
    mockProjectSuggestionResponses([smokeSuggestion]);
    apiClient.post.mockResolvedValue({
      data: { mounted_root_id: 7, message: "Mounted smoke project" },
    });

    renderFilesManager();

    expect(
      await screen.findByText("Project setup: mito25-paper-loop-smoke"),
    ).toBeTruthy();
    expect(screen.getByText("2 prediction")).toBeTruthy();
    fireEvent.click(await screen.findByText("Use project"));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        "/files/mount",
        {
          directory_path: "/tmp/mito25_paper_loop_smoke",
          destination_path: "root",
          mount_name: "mito25-paper-loop-smoke",
        },
        { withCredentials: true },
      );
    });
    expect(apiClient.get).toHaveBeenCalledWith("/files", {
      params: { parent: "7" },
    });
    expect(await screen.findByText("Confirm project data")).toBeTruthy();
    expect(
      screen.getByDisplayValue(
        "/tmp/mito25_paper_loop_smoke/data/image/mito25_smoke_im.h5",
      ),
    ).toBeTruthy();
    expect(mockWorkflowContext.updateWorkflow).not.toHaveBeenCalled();

    fireEvent.click(screen.getByText("Start project"));

    await waitFor(() => {
      expect(mockWorkflowContext.updateWorkflow).toHaveBeenCalledWith({
        dataset_path: "/tmp/mito25_paper_loop_smoke",
        image_path: "/tmp/mito25_paper_loop_smoke/data/image/mito25_smoke_im.h5",
        label_path: "/tmp/mito25_paper_loop_smoke/data/seg/mito25_smoke_seg.h5",
        mask_path: "/tmp/mito25_paper_loop_smoke/data/seg/mito25_smoke_seg.h5",
        inference_output_path:
          "/tmp/mito25_paper_loop_smoke/predictions/baseline.tif",
        checkpoint_path:
          "/tmp/mito25_paper_loop_smoke/checkpoints/checkpoint_00200.pth.tar",
        config_path: "/tmp/mito25_paper_loop_smoke/configs/MitoEM.yaml",
      });
    });
    expect(mockWorkflowContext.appendEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        event_type: "dataset.loaded",
        summary: "Confirmed project data for mito25-paper-loop-smoke.",
        payload: expect.objectContaining({
          source: "file_management_project_confirmation",
          setup_source: "suggested_mount",
          confirmed_roles: expect.objectContaining({
            config: "/tmp/mito25_paper_loop_smoke/configs/MitoEM.yaml",
          }),
        }),
      }),
    );
  });

  it("uses edited and cleared role paths when confirming project setup", async () => {
    mockProjectSuggestionResponses([smokeSuggestion]);
    apiClient.post.mockResolvedValue({
      data: { mounted_root_id: 7, message: "Mounted smoke project" },
    });

    renderFilesManager();

    fireEvent.click(await screen.findByText("Use project"));
    await screen.findByText("Confirm project data");

    fireEvent.change(
      screen.getByDisplayValue(
        "/tmp/mito25_paper_loop_smoke/predictions/baseline.tif",
      ),
      { target: { value: "" } },
    );
    fireEvent.change(
      screen.getByDisplayValue(
        "/tmp/mito25_paper_loop_smoke/checkpoints/checkpoint_00200.pth.tar",
      ),
      { target: { value: "/tmp/custom/checkpoint.pth.tar" } },
    );
    fireEvent.click(screen.getByText("Start project"));

    await waitFor(() => {
      expect(mockWorkflowContext.updateWorkflow).toHaveBeenCalledWith({
        dataset_path: "/tmp/mito25_paper_loop_smoke",
        image_path: "/tmp/mito25_paper_loop_smoke/data/image/mito25_smoke_im.h5",
        label_path: "/tmp/mito25_paper_loop_smoke/data/seg/mito25_smoke_seg.h5",
        mask_path: "/tmp/mito25_paper_loop_smoke/data/seg/mito25_smoke_seg.h5",
        checkpoint_path: "/tmp/custom/checkpoint.pth.tar",
        config_path: "/tmp/mito25_paper_loop_smoke/configs/MitoEM.yaml",
      });
    });
    expect(
      mockWorkflowContext.updateWorkflow.mock.calls[0][0].inference_output_path,
    ).toBeUndefined();
  });

  it("lets a user browse to override a detected role before confirmation", async () => {
    mockProjectSuggestionResponses([smokeSuggestion]);
    apiClient.post.mockResolvedValue({
      data: { mounted_root_id: 7, message: "Mounted smoke project" },
    });

    renderFilesManager();

    fireEvent.click(await screen.findByText("Use project"));
    await screen.findByText("Confirm project data");
    fireEvent.click(screen.getAllByText("Browse")[2]);
    fireEvent.click(await screen.findByText("Choose mocked file"));
    fireEvent.click(screen.getByText("Start project"));

    await waitFor(() => {
      expect(mockWorkflowContext.updateWorkflow).toHaveBeenCalledWith(
        expect.objectContaining({
          inference_output_path: "/tmp/override/override-prediction.tif",
        }),
      );
    });
  });

  it("allows image-only projects to start without mask or checkpoint roles", async () => {
    mockProjectSuggestionResponses([imageOnlySuggestion]);
    apiClient.post.mockResolvedValue({
      data: { mounted_root_id: 12, message: "Mounted image-only project" },
    });

    renderFilesManager();

    expect(await screen.findByText("Project setup: image-only-project")).toBeTruthy();
    fireEvent.click(await screen.findByText("Use project"));
    await screen.findByText("Confirm project data");
    fireEvent.click(screen.getByText("Start project"));

    await waitFor(() => {
      expect(mockWorkflowContext.updateWorkflow).toHaveBeenCalledWith({
        dataset_path: "/tmp/image_only_project",
        image_path: "/tmp/image_only_project/volume/raw_image.tif",
      });
    });
  });

  it("opens confirmation after a manual project mount and leaves workflow unchanged when canceled", async () => {
    apiClient.get.mockResolvedValue({ data: [] });
    openLocalFile.mockResolvedValue("/tmp/manual_project");
    apiClient.post.mockResolvedValue({
      data: {
        mounted_root_id: 15,
        mount_name: "manual_project",
        message: "Mounted manual project",
        profile: {
          schema: {
            mode: "image_only",
            primary_paths: { image: "raw/manual.h5" },
          },
          examples: { image: ["raw/manual.h5"] },
          counts: { image: 1 },
        },
      },
    });

    renderFilesManager();

    fireEvent.click(await screen.findByText("Mount Project"));
    await screen.findByText("Confirm project data");
    expect(
      screen.getByDisplayValue("/tmp/manual_project/raw/manual.h5"),
    ).toBeTruthy();
    fireEvent.click(screen.getByText("Cancel"));

    expect(mockWorkflowContext.updateWorkflow).not.toHaveBeenCalled();
  });
});
