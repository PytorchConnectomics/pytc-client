import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import FilesManager from "./FilesManager";
import { AppContext } from "../contexts/GlobalContext";
import { apiClient } from "../api";

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

const mockWorkflowContext = {
  workflow: { id: 1, stage: "setup" },
  updateWorkflow: jest.fn(),
  appendEvent: jest.fn(),
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

  const Button = ({ children, ...props }) => <button {...props}>{children}</button>;
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
  const Modal = ({ children, open }) => (open ? <div>{children}</div> : null);
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

describe("FilesManager", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockWorkflowContext.updateWorkflow.mockResolvedValue({});
    mockWorkflowContext.appendEvent.mockResolvedValue({});
  });

  it("loads root-level files with a parent-scoped request on initial render", async () => {
    apiClient.get.mockResolvedValue({ data: [] });

    render(
      <AppContext.Provider value={{ resetFileState: jest.fn() }}>
        <FilesManager />
      </AppContext.Provider>,
    );

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith("/files", {
        params: { parent: "root" },
      });
    });

    expect(apiClient.get).not.toHaveBeenCalledWith("/files");
  });

  it("mounts a suggested smoke project without manually browsing for a path", async () => {
    apiClient.get.mockImplementation((url) => {
      if (url === "/files/project-suggestions") {
        return Promise.resolve({
          data: [
            {
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
                },
                missing_roles: [],
              },
            },
          ],
        });
      }
      return Promise.resolve({ data: [] });
    });
    apiClient.post.mockResolvedValue({
      data: { mounted_root_id: 7, message: "Mounted smoke project" },
    });

    render(
      <AppContext.Provider value={{ resetFileState: jest.fn() }}>
        <FilesManager />
      </AppContext.Provider>,
    );

    expect(
      await screen.findByText("Project setup: mito25-paper-loop-smoke"),
    ).toBeTruthy();
    expect(screen.getByText("2 prediction")).toBeTruthy();
    fireEvent.click(await screen.findByText("Mount Test Project"));

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
    expect(mockWorkflowContext.updateWorkflow).toHaveBeenCalledWith({
      dataset_path: "/tmp/mito25_paper_loop_smoke",
      image_path: "/tmp/mito25_paper_loop_smoke/data/image/mito25_smoke_im.h5",
      label_path: "/tmp/mito25_paper_loop_smoke/data/seg/mito25_smoke_seg.h5",
      mask_path: "/tmp/mito25_paper_loop_smoke/data/seg/mito25_smoke_seg.h5",
      inference_output_path: "/tmp/mito25_paper_loop_smoke/predictions/baseline.tif",
      checkpoint_path:
        "/tmp/mito25_paper_loop_smoke/checkpoints/checkpoint_00200.pth.tar",
    });
    expect(mockWorkflowContext.appendEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        event_type: "dataset.loaded",
        summary: "Registered project roles from mito25-paper-loop-smoke.",
      }),
    );
  });
});
