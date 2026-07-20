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
  canOpenLocalFile: jest.fn(() => true),
  openLocalFile: jest.fn(),
  revealInFinder: jest.fn(),
}));

jest.mock("../components/FileTreeSidebar", () => () => null);
jest.mock(
  "../components/FilePickerModal",
  () =>
    ({ visible, onSelect, title }) =>
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
  pendingRuntimeAction: null,
  consumeRuntimeAction: jest.fn(),
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
  const Input = React.forwardRef((props, ref) => (
    <input ref={ref} {...props} />
  ));
  Input.TextArea = React.forwardRef((props, ref) => (
    <textarea ref={ref} {...props} />
  ));
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
      schema_version: "pytc-project-profile/v1",
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
    role_directories: {
      image: [{ path: "data/image", count: 1 }],
      label: [{ path: "data/seg", count: 1 }],
      prediction: [{ path: "predictions", count: 2 }],
    },
    volume_sets: [
      {
        id: "set-1",
        name: "image + seg",
        image_root: "data/image",
        label_root: "data/seg",
        image_count: 1,
        label_count: 1,
        pair_count: 1,
      },
    ],
    paired_examples: [
      {
        image: "data/image/mito25_smoke_im.h5",
        label: "data/seg/mito25_smoke_seg.h5",
      },
    ],
    audit: {
      schema_version: "pytc-project-audit/v1",
      summary: {
        audited_volumes: 2,
        readable_volumes: 2,
        pair_checks: 1,
        shape_match_count: 1,
        shape_mismatch_count: 0,
        warnings: 0,
        errors: 0,
      },
      context_facts: [
        {
          key: "voxel_size_nm",
          label: "Voxel size",
          value: [30, 6, 6],
          source: "volume_metadata:data/image/mito25_smoke_im.h5",
          confidence: "high",
        },
      ],
      findings: [
        {
          level: "info",
          code: "pair_shape_match",
          message: "Image and mask shapes match.",
          path: "data/image/mito25_smoke_im.h5",
          related_path: "data/seg/mito25_smoke_seg.h5",
          source: "volume_metadata",
        },
      ],
    },
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

const completeSmokeSuggestion = {
  ...smokeSuggestion,
  profile: {
    ...smokeSuggestion.profile,
    context_hints: {
      imaging_modality: "EM",
      target_structure: "mitochondria",
      voxel_size_nm: [30, 6, 6],
      voxel_size_source: "volume_metadata:data/image/mito25_smoke_im.h5",
    },
    schema: {
      ...smokeSuggestion.profile.schema,
      context_hints: {
        imaging_modality: "EM",
        target_structure: "mitochondria",
        voxel_size_nm: [30, 6, 6],
        voxel_size_source: "volume_metadata:data/image/mito25_smoke_im.h5",
      },
    },
  },
};

const yixiaoLikeSmokeSuggestion = {
  ...completeSmokeSuggestion,
  name: "Yixiao TapeReader XRI Case Study",
  profile: {
    ...completeSmokeSuggestion.profile,
    context_hints: {
      ...completeSmokeSuggestion.profile.context_hints,
      task_family: "XRI fibre instance segmentation",
      training_policy: "train only on confirmed ground-truth masks",
      mask_status:
        "mixed: 6 ground-truth masks, 2 draft masks, 2 image-only targets",
    },
    schema: {
      ...completeSmokeSuggestion.profile.schema,
      context_hints: {
        ...(completeSmokeSuggestion.profile.schema &&
        completeSmokeSuggestion.profile.schema.context_hints
          ? completeSmokeSuggestion.profile.schema.context_hints
          : {}),
        task_family: "XRI fibre instance segmentation",
        training_policy: "train only on confirmed ground-truth masks",
        mask_status:
          "mixed: 6 ground-truth masks, 2 draft masks, 2 image-only targets",
      },
      manifest: {
        initial_progress_summary: {
          ground_truth: 6,
          needs_proofreading: 2,
          missing_segmentation: 2,
        },
      },
    },
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

const neutralSuggestion = {
  id: "neutral-project",
  name: "neutral-project",
  directory_path: "/tmp/neutral_project",
  description: "Generic image/mask project",
  recommended: true,
  already_mounted: false,
  profile: {
    counts: { image: 0, label: 0 },
    schema: {
      workable: true,
      mode: "image_mask_pair",
      primary_paths: {
        image: "data/image.h5",
        label: "data/label.h5",
      },
    },
    examples: {
      image: ["data/image.h5"],
      label: ["data/label.h5"],
    },
    missing_roles: [],
  },
};

const batchSuggestion = {
  id: "nucmm-batch-project",
  name: "nucmm-batch-project",
  directory_path: "/tmp/nucmm_project",
  description: "Detected image/label batch",
  recommended: true,
  already_mounted: false,
  profile: {
    ready_for_smoke: false,
    counts: { image: 8, label: 8, checkpoint: 1, config: 1 },
    role_directories: {
      image: [{ path: "data/source/Image/train", count: 4 }],
      label: [{ path: "data/source/Label/train", count: 4 }],
    },
    volume_sets: [
      {
        id: "set-1",
        name: "train",
        image_root: "data/source/Image/train",
        label_root: "data/source/Label/train",
        image_count: 4,
        label_count: 4,
        pair_count: 4,
      },
      {
        id: "set-2",
        name: "val",
        image_root: "data/source/Image/val",
        label_root: "data/source/Label/val",
        image_count: 4,
        label_count: 4,
        pair_count: 4,
      },
    ],
    schema: {
      workable: true,
      mode: "image_mask_pair",
      stages: { visualization: true, proofreading: true, training: true },
      primary_paths: {
        image: "data/source/Image/train/img_000.h5",
        image_root: "data/source/Image/train",
        label: "data/source/Label/train/img_000.h5",
        label_root: "data/source/Label/train",
        checkpoint: "checkpoints/model.pth.tar",
        config: "configs/preset.yaml",
      },
    },
    examples: {
      image: ["data/source/Image/train/img_000.h5"],
      label: ["data/source/Label/train/img_000.h5"],
      checkpoint: ["checkpoints/model.pth.tar"],
      config: ["configs/preset.yaml"],
    },
    missing_roles: ["prediction"],
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
    if (url === "/files/project-context") {
      return Promise.resolve({ data: { exists: false, profile: null } });
    }
    return Promise.resolve({ data: [] });
  });
};

const clickSuggestedProject = async () => {
  const buttons = await screen.findAllByText("Use suggested project");
  fireEvent.click(buttons[0]);
};

const continueWithProjectContext = async (
  text = "EM mitochondria volumes from mouse tissue at 30 x 6 x 6 nm. Segment mitochondria from a single volume and prioritize accuracy.",
) => {
  await screen.findByText("Confirm project basics");
  fireEvent.change(screen.getByPlaceholderText(/Optional:/i), {
    target: { value: text },
  });
  fireEvent.click(screen.getByText("Continue"));
  await waitFor(() => {
    expect(screen.getAllByText("Start project").length).toBeGreaterThan(1);
  });
};

const continueWithDefaults = async () => {
  await screen.findByRole("dialog");
  if (screen.queryAllByText("Start project").length > 1) return;
  fireEvent.click(screen.getByText(/Use (safe defaults|detected context)/));
  await waitFor(() => {
    expect(screen.getAllByText("Start project").length).toBeGreaterThan(1);
  });
};

const reviewAndStartProject = async () => {
  const startButtons = screen
    .getAllByText("Start project")
    .filter((element) => element.tagName.toLowerCase() === "button");
  fireEvent.click(startButtons[0]);
};

describe("FilesManager", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockWorkflowContext.updateWorkflow.mockResolvedValue({});
    mockWorkflowContext.appendEvent.mockResolvedValue({});
    mockWorkflowContext.refreshPreflight.mockResolvedValue({});
    mockWorkflowContext.refreshAgentRecommendation.mockResolvedValue({});
    mockWorkflowContext.pendingRuntimeAction = null;
    mockWorkflowContext.consumeRuntimeAction.mockClear();
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
      await screen.findByText("Start a segmentation project"),
    ).toBeTruthy();
    await clickSuggestedProject();

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
    await continueWithProjectContext();
    await waitFor(() => {
      expect(screen.getAllByText("Start project").length).toBeGreaterThan(1);
    });
    expect(
      screen.getByDisplayValue("data/image/mito25_smoke_im.h5"),
    ).toBeTruthy();
    expect(mockWorkflowContext.updateWorkflow).not.toHaveBeenCalled();

    await reviewAndStartProject();
    expect(await screen.findByText("Project brief")).toBeTruthy();
    expect(
      screen.getByText("EM mitochondria project at 30 x 6 x 6 nm."),
    ).toBeTruthy();
    expect(screen.getByText("Editable project context")).toBeTruthy();
    expect(screen.getByText("What I checked automatically")).toBeTruthy();
    expect(
      screen.getByText(/I inspected 2 volumes and 1 image\/mask pair/i),
    ).toBeTruthy();
    expect(screen.getByText(/Image and mask shapes match/i)).toBeTruthy();
    expect(screen.queryByText(/^Priority$/)).toBeNull();
    expect(screen.queryByText(/^Goal$/)).toBeNull();
    expect(screen.queryByText(/^Labels$/)).toBeNull();
    expect(screen.queryByText(/^Data$/)).toBeNull();
    expect(screen.getByText("How the agent will use this")).toBeTruthy();

    await waitFor(() => {
      expect(mockWorkflowContext.updateWorkflow).toHaveBeenCalledWith({
        dataset_path: "/tmp/mito25_paper_loop_smoke",
        image_path:
          "/tmp/mito25_paper_loop_smoke/data/image/mito25_smoke_im.h5",
        label_path: "/tmp/mito25_paper_loop_smoke/data/seg/mito25_smoke_seg.h5",
        mask_path: "/tmp/mito25_paper_loop_smoke/data/seg/mito25_smoke_seg.h5",
        inference_output_path:
          "/tmp/mito25_paper_loop_smoke/predictions/baseline.tif",
        checkpoint_path:
          "/tmp/mito25_paper_loop_smoke/checkpoints/checkpoint_00200.pth.tar",
        config_path: "/tmp/mito25_paper_loop_smoke/configs/MitoEM.yaml",
        metadata: {
          visualization_scales: [30, 6, 6],
          visualization_scales_source: "project_description",
          project_context: expect.objectContaining({
            freeform_note:
              "EM mitochondria volumes from mouse tissue at 30 x 6 x 6 nm. Segment mitochondria from a single volume and prioritize accuracy.",
            imaging_modality: "EM",
            target_structure: "mitochondria",
            voxel_size_nm: [30, 6, 6],
            source: "project_setup_confirmation",
          }),
        },
      });
    });
    expect(mockWorkflowContext.appendEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        event_type: "dataset.loaded",
        summary: "Confirmed project data for mito25-paper-loop-smoke.",
        payload: expect.objectContaining({
          source: "file_management_project_confirmation",
          setup_source: "suggested_mount",
          project_description:
            "EM mitochondria volumes from mouse tissue at 30 x 6 x 6 nm. Segment mitochondria from a single volume and prioritize accuracy.",
          project_context: expect.objectContaining({
            imaging_modality: "EM",
            target_structure: "mitochondria",
            voxel_size_nm: [30, 6, 6],
          }),
          project_brief: expect.objectContaining({
            summary: "EM mitochondria project at 30 x 6 x 6 nm.",
            fields: expect.arrayContaining([
              expect.objectContaining({
                label: "Target structure",
                value: "mitochondria",
              }),
              expect.objectContaining({
                label: "Voxel size (z, y, x)",
                value: "30 x 6 x 6 nm",
              }),
            ]),
            next_moves: expect.arrayContaining([
              "Use data/image/mito25_smoke_im.h5 as the active image data.",
              "Use 30 x 6 x 6 nm as the z/y/x voxel size for visualization and model defaults.",
            ]),
          }),
          detected_volume_sets: expect.arrayContaining([
            expect.objectContaining({ pair_count: 1 }),
          ]),
          project_audit: expect.objectContaining({
            schema_version: "pytc-project-audit/v1",
          }),
          context_facts: expect.arrayContaining([
            expect.objectContaining({ key: "voxel_size_nm" }),
          ]),
          confirmed_roles: expect.objectContaining({
            config: "configs/MitoEM.yaml",
          }),
        }),
      }),
    );
    expect(apiClient.put).toHaveBeenCalledWith(
      "/files/project-context",
      expect.objectContaining({
        directory_path: "/tmp/mito25_paper_loop_smoke",
        profile: expect.objectContaining({
          schema_version: "pytc-project-context/v1",
          semantic_context: expect.objectContaining({
            target_structure: "mitochondria",
          }),
          project_brief: expect.objectContaining({
            summary: "EM mitochondria project at 30 x 6 x 6 nm.",
          }),
          project_audit: expect.objectContaining({
            schema_version: "pytc-project-audit/v1",
          }),
          mechanistic_mapping: expect.objectContaining({
            image: "data/image/mito25_smoke_im.h5",
          }),
        }),
      }),
    );
  });

  it("skips the blank description prompt when project basics are already detected", async () => {
    mockProjectSuggestionResponses([completeSmokeSuggestion]);
    apiClient.post.mockResolvedValue({
      data: { mounted_root_id: 7, message: "Mounted smoke project" },
    });

    renderFilesManager();

    await clickSuggestedProject();

    await waitFor(() => {
      expect(screen.getAllByText("Start project").length).toBeGreaterThan(1);
    });
    expect(screen.queryByText("Confirm project basics")).toBeNull();
    expect(screen.queryByText("Anything else I should know?")).toBeNull();
    expect(screen.getByDisplayValue("EM")).toBeTruthy();
    expect(screen.getByDisplayValue("mitochondria")).toBeTruthy();
    expect(screen.getByDisplayValue("30, 6, 6")).toBeTruthy();
    expect(screen.getByText("What I checked automatically")).toBeTruthy();
  });

  it("shows compact shared facts including task/training policy and volume split", async () => {
    mockProjectSuggestionResponses([yixiaoLikeSmokeSuggestion]);
    apiClient.post.mockResolvedValue({
      data: { mounted_root_id: 7, message: "Mounted yixiao project" },
    });

    renderFilesManager();

    await clickSuggestedProject();
    await screen.findByText("Shared project facts");
    expect(screen.getAllByText("Shared project facts").length).toBeGreaterThan(
      0,
    );
    expect(screen.getAllByText("Modality").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Target").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Voxel size").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Volume split").length).toBeGreaterThan(0);
    expect(
      screen.getAllByText("XRI fibre instance segmentation").length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText("train only on confirmed ground-truth masks").length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText("6 ground-truth / 2 draft masks / 2 image-only")
        .length,
    ).toBeGreaterThan(0);

    await continueWithDefaults();
    expect(screen.getByText("Shared project facts")).toBeTruthy();
    await reviewAndStartProject();

    await waitFor(() => {
      expect(mockWorkflowContext.updateWorkflow).toHaveBeenCalledWith(
        expect.objectContaining({
          metadata: expect.objectContaining({
            project_context: expect.objectContaining({
              task_family: "XRI fibre instance segmentation",
              training_policy: "train only on confirmed ground-truth masks",
              volume_split: "6 ground-truth / 2 draft masks / 2 image-only",
            }),
          }),
        }),
      );
    });
  });

  it("asks semantic follow-up questions for context the app cannot infer", async () => {
    mockProjectSuggestionResponses([neutralSuggestion]);
    apiClient.post.mockResolvedValue({
      data: { mounted_root_id: 7, message: "Mounted neutral project" },
    });

    renderFilesManager();

    await clickSuggestedProject();
    await screen.findByText("Confirm project basics");
    const descriptionBox = screen.getByPlaceholderText(/Optional:/i);
    fireEvent.change(descriptionBox, {
      target: { value: "EM mitochondria from mouse brain tissue." },
    });
    fireEvent.click(screen.getByText("Continue"));
    expect(
      await screen.findByText(
        "What is the voxel size or imaging resolution in z, y, x nanometers?",
      ),
    ).toBeTruthy();
    expect(screen.queryAllByText("Start project")).toHaveLength(0);
    expect(descriptionBox.value).toBe("");

    fireEvent.change(descriptionBox, {
      target: {
        value: "30 x 6 x 6 nm",
      },
    });
    fireEvent.click(screen.getByText("Continue"));
    await waitFor(() => {
      expect(screen.getAllByText("Start project").length).toBeGreaterThan(1);
    });

    await reviewAndStartProject();

    await waitFor(() => {
      expect(mockWorkflowContext.updateWorkflow).toHaveBeenCalledWith(
        expect.objectContaining({
          metadata: expect.objectContaining({
            project_context: expect.objectContaining({
              freeform_note:
                "EM mitochondria from mouse brain tissue.\n30 x 6 x 6 nm",
              imaging_modality: "EM",
              target_structure: "mitochondria",
              voxel_size_nm: [30, 6, 6],
              completeness: expect.objectContaining({
                complete: true,
                missing: [],
              }),
            }),
          }),
        }),
      );
    });
  });

  it("lets users edit absorbed project context fields before confirming", async () => {
    mockProjectSuggestionResponses([smokeSuggestion]);
    apiClient.post.mockResolvedValue({
      data: { mounted_root_id: 7, message: "Mounted smoke project" },
    });

    renderFilesManager();

    await clickSuggestedProject();
    await continueWithProjectContext();

    fireEvent.change(screen.getByDisplayValue("EM"), {
      target: { value: "serial block-face EM" },
    });
    fireEvent.change(screen.getByDisplayValue("mitochondria"), {
      target: { value: "synapses" },
    });
    fireEvent.change(screen.getByDisplayValue("30, 6, 6"), {
      target: { value: "4, 4, 40" },
    });

    expect(
      screen.getByText(
        "serial block-face EM synapses project at 4 x 4 x 40 nm.",
      ),
    ).toBeTruthy();

    await reviewAndStartProject();

    await waitFor(() => {
      expect(mockWorkflowContext.updateWorkflow).toHaveBeenCalledWith(
        expect.objectContaining({
          metadata: expect.objectContaining({
            visualization_scales: [4, 4, 40],
            visualization_scales_source: "project_setup_confirmation",
            project_context: expect.objectContaining({
              imaging_modality: "serial block-face EM",
              target_structure: "synapses",
              voxel_size_nm: [4, 4, 40],
            }),
          }),
        }),
      );
    });
    const projectContext =
      mockWorkflowContext.updateWorkflow.mock.calls[0][0].metadata
        .project_context;
    expect(projectContext).not.toHaveProperty("task_goal");
    expect(projectContext).not.toHaveProperty("data_unit");
    expect(projectContext).not.toHaveProperty("optimization_priority");
    expect(projectContext).not.toHaveProperty("label_status");
  });

  it("uses edited and cleared role paths when confirming project setup", async () => {
    mockProjectSuggestionResponses([smokeSuggestion]);
    apiClient.post.mockResolvedValue({
      data: { mounted_root_id: 7, message: "Mounted smoke project" },
    });

    renderFilesManager();

    await clickSuggestedProject();
    await continueWithDefaults();

    fireEvent.change(screen.getByDisplayValue("predictions/baseline.tif"), {
      target: { value: "" },
    });
    fireEvent.change(
      screen.getByDisplayValue("checkpoints/checkpoint_00200.pth.tar"),
      { target: { value: "/tmp/custom/checkpoint.pth.tar" } },
    );
    await reviewAndStartProject();

    await waitFor(() => {
      expect(mockWorkflowContext.updateWorkflow).toHaveBeenCalledWith(
        expect.objectContaining({
          dataset_path: "/tmp/mito25_paper_loop_smoke",
          image_path:
            "/tmp/mito25_paper_loop_smoke/data/image/mito25_smoke_im.h5",
          label_path:
            "/tmp/mito25_paper_loop_smoke/data/seg/mito25_smoke_seg.h5",
          mask_path:
            "/tmp/mito25_paper_loop_smoke/data/seg/mito25_smoke_seg.h5",
          checkpoint_path: "/tmp/custom/checkpoint.pth.tar",
          config_path: "/tmp/mito25_paper_loop_smoke/configs/MitoEM.yaml",
        }),
      );
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

    await clickSuggestedProject();
    await continueWithDefaults();
    fireEvent.click(screen.getAllByText("Browse")[2]);
    fireEvent.click(await screen.findByText("Choose mocked file"));
    await reviewAndStartProject();

    await waitFor(() => {
      expect(mockWorkflowContext.updateWorkflow).toHaveBeenCalledWith(
        expect.objectContaining({
          inference_output_path: "/tmp/override/override-prediction.tif",
        }),
      );
    });
    expect(apiClient.put).toHaveBeenCalledWith(
      "/files/project-context",
      expect.objectContaining({
        directory_path: "/tmp/mito25_paper_loop_smoke",
        profile: expect.objectContaining({
          schema_version: "pytc-project-context/v1",
          semantic_context: expect.objectContaining({
            use_defaults: true,
          }),
          mechanistic_mapping: expect.objectContaining({
            prediction: "/tmp/override/override-prediction.tif",
          }),
        }),
      }),
    );
  });

  it("defaults multi-volume projects to confirmed folders instead of one file", async () => {
    mockProjectSuggestionResponses([batchSuggestion]);
    apiClient.post.mockResolvedValue({
      data: { mounted_root_id: 21, message: "Mounted batch project" },
    });

    renderFilesManager();

    await clickSuggestedProject();
    await continueWithProjectContext(
      "Mouse micro-CT nuclei dataset with train/val folders at 8 x 8 x 8 nm. Segment nuclei and prioritize accuracy.",
    );
    expect(screen.getByDisplayValue("data/source/Image/train")).toBeTruthy();
    expect(screen.getByDisplayValue("data/source/Label/train")).toBeTruthy();
    expect(screen.getByText(/4 matched pairs/)).toBeTruthy();

    await reviewAndStartProject();

    await waitFor(() => {
      expect(mockWorkflowContext.updateWorkflow).toHaveBeenCalledWith(
        expect.objectContaining({
          dataset_path: "/tmp/nucmm_project",
          image_path: "/tmp/nucmm_project/data/source/Image/train",
          label_path: "/tmp/nucmm_project/data/source/Label/train",
          mask_path: "/tmp/nucmm_project/data/source/Label/train",
          checkpoint_path: "/tmp/nucmm_project/checkpoints/model.pth.tar",
          config_path: "/tmp/nucmm_project/configs/preset.yaml",
        }),
      );
    });
    expect(mockWorkflowContext.appendEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        payload: expect.objectContaining({
          detected_role_counts: expect.objectContaining({ image: 8, label: 8 }),
          detected_volume_sets: expect.arrayContaining([
            expect.objectContaining({ pair_count: 4 }),
          ]),
        }),
      }),
    );
  });

  it("submits repeated setup feedback with Enter and applies each correction", async () => {
    mockProjectSuggestionResponses([batchSuggestion]);
    apiClient.post.mockResolvedValue({
      data: { mounted_root_id: 21, message: "Mounted batch project" },
    });

    renderFilesManager();

    await clickSuggestedProject();
    await continueWithDefaults();

    const feedbackBox = screen.getByPlaceholderText(/Example correction/i);
    fireEvent.change(feedbackBox, { target: { value: "use val split" } });
    fireEvent.keyDown(feedbackBox, { key: "Enter", shiftKey: false });

    expect(await screen.findByText(/Updated the mapping/)).toBeTruthy();
    expect(screen.getByDisplayValue("data/source/Image/val")).toBeTruthy();
    expect(screen.getByDisplayValue("data/source/Label/val")).toBeTruthy();
    await waitFor(() => {
      expect(mockWorkflowContext.appendEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          event_type: "dataset.setup_feedback",
          payload: expect.objectContaining({
            feedback: "use val split",
            applied_changes: expect.objectContaining({
              image: "data/source/Image/val",
              label: "data/source/Label/val",
            }),
          }),
        }),
      );
    });

    fireEvent.change(feedbackBox, { target: { value: "use train split" } });
    fireEvent.keyDown(feedbackBox, { key: "Enter", shiftKey: false });

    expect(screen.getByDisplayValue("data/source/Image/train")).toBeTruthy();
    expect(screen.getByDisplayValue("data/source/Label/train")).toBeTruthy();
    await waitFor(() => {
      expect(mockWorkflowContext.appendEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          event_type: "dataset.setup_feedback",
          payload: expect.objectContaining({
            feedback: "use train split",
            applied_changes: expect.objectContaining({
              image: "data/source/Image/train",
              label: "data/source/Label/train",
            }),
          }),
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

    await clickSuggestedProject();
    await continueWithDefaults();
    await reviewAndStartProject();

    await waitFor(() => {
      expect(mockWorkflowContext.updateWorkflow).toHaveBeenCalledWith(
        expect.objectContaining({
          dataset_path: "/tmp/image_only_project",
          image_path: "/tmp/image_only_project/volume/raw_image.tif",
        }),
      );
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
    await screen.findByText("Confirm project basics");
    expect(screen.getByPlaceholderText(/Optional:/i)).toBeTruthy();
    fireEvent.click(screen.getByText("Cancel"));

    expect(mockWorkflowContext.updateWorkflow).not.toHaveBeenCalled();
  });

  it("opens project data confirmation for assistant choose-data actions", async () => {
    mockWorkflowContext.pendingRuntimeAction = {
      id: "choose-data-action",
      kind: "choose_project_data",
    };
    mockProjectSuggestionResponses([
      {
        ...smokeSuggestion,
        already_mounted: true,
        mounted_root_id: 7,
      },
    ]);

    renderFilesManager();

    await screen.findByText("Confirm project basics");
    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith("/files", {
        params: { parent: "7" },
      });
      expect(mockWorkflowContext.consumeRuntimeAction).toHaveBeenCalledWith(
        "choose-data-action",
      );
    });
  });
});
