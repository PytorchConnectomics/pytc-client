import {
  buildWorkflowPatchFromConfirmedProjectRoles,
  buildWorkflowPatchFromProjectSuggestion,
  getProjectVolumeSetsFromSuggestion,
  getProjectRoleDefaultsFromSuggestion,
  getProjectContextDefaultsFromSuggestion,
  evaluateProjectContextCompleteness,
  formatVoxelSizeNm,
  inferProjectContextFromDescription,
} from "./projectSuggestions";

const suggestion = {
  directory_path: "/projects/demo",
  profile: {
    schema: {
      primary_paths: {
        image: "data/raw.h5",
        label: "data/mask.h5",
        prediction: "predictions/baseline.tif",
        checkpoint: "checkpoints/model.pth.tar",
        config: "configs/preset.yaml",
      },
    },
  },
};

const batchSuggestion = {
  directory_path: "/projects/batch-demo",
  profile: {
    counts: {
      image: 4,
      label: 4,
      prediction: 2,
      config: 1,
      checkpoint: 1,
    },
    volume_sets: [
      {
        id: "set-1",
        name: "train",
        image_root: "data/Image/train",
        label_root: "data/Label/train",
        image_count: 4,
        label_count: 4,
        pair_count: 4,
      },
    ],
    schema: {
      primary_paths: {
        image: "data/Image/train/img_000.h5",
        image_root: "data/Image/train",
        label: "data/Label/train/img_000.h5",
        label_root: "data/Label/train",
        prediction: "outputs/baseline.h5",
        prediction_root: "outputs",
        checkpoint: "checkpoints/model.pth.tar",
        config: "configs/preset.yaml",
      },
    },
  },
};

describe("project suggestion utilities", () => {
  it("derives absolute default role paths from a profiled project", () => {
    expect(getProjectRoleDefaultsFromSuggestion(suggestion)).toEqual({
      image: "/projects/demo/data/raw.h5",
      label: "/projects/demo/data/mask.h5",
      prediction: "/projects/demo/predictions/baseline.tif",
      checkpoint: "/projects/demo/checkpoints/model.pth.tar",
      config: "/projects/demo/configs/preset.yaml",
    });
  });

  it("converts confirmed roles into workflow patch fields", () => {
    expect(
      buildWorkflowPatchFromConfirmedProjectRoles({
        rootPath: "/projects/demo",
        roles: {
          image: "/projects/demo/raw.h5",
          label: "/projects/demo/labels.h5",
          prediction: "",
          checkpoint: "/models/model.pth.tar",
          config: "/projects/demo/config.yaml",
        },
      }),
    ).toEqual({
      dataset_path: "/projects/demo",
      image_path: "/projects/demo/raw.h5",
      label_path: "/projects/demo/labels.h5",
      mask_path: "/projects/demo/labels.h5",
      checkpoint_path: "/models/model.pth.tar",
      config_path: "/projects/demo/config.yaml",
    });
  });

  it("copies confirmed imaging resolution into workflow metadata", () => {
    expect(
      buildWorkflowPatchFromConfirmedProjectRoles({
        rootPath: "/projects/demo",
        roles: {
          image: "raw.h5",
          label: "labels.h5",
        },
        metadata: {
          project_context: {
            voxel_size_nm: [30, 6, 6],
            voxel_size_source: "project_description",
          },
        },
      }),
    ).toEqual(
      expect.objectContaining({
        metadata: expect.objectContaining({
          visualization_scales: [30, 6, 6],
          visualization_scales_source: "project_description",
        }),
      }),
    );
  });

  it("keeps the legacy suggestion patch behavior backed by confirmed role defaults", () => {
    expect(buildWorkflowPatchFromProjectSuggestion(suggestion)).toEqual({
      dataset_path: "/projects/demo",
      image_path: "/projects/demo/data/raw.h5",
      label_path: "/projects/demo/data/mask.h5",
      mask_path: "/projects/demo/data/mask.h5",
      inference_output_path: "/projects/demo/predictions/baseline.tif",
      checkpoint_path: "/projects/demo/checkpoints/model.pth.tar",
      config_path: "/projects/demo/configs/preset.yaml",
    });
  });

  it("prefers project folders when a profile contains multiple volume pairs", () => {
    expect(getProjectRoleDefaultsFromSuggestion(batchSuggestion)).toEqual({
      image: "/projects/batch-demo/data/Image/train",
      label: "/projects/batch-demo/data/Label/train",
      prediction: "/projects/batch-demo/outputs",
      checkpoint: "/projects/batch-demo/checkpoints/model.pth.tar",
      config: "/projects/batch-demo/configs/preset.yaml",
    });
    expect(getProjectVolumeSetsFromSuggestion(batchSuggestion)).toEqual([
      expect.objectContaining({
        image_root: "data/Image/train",
        label_root: "data/Label/train",
        pair_count: 4,
      }),
    ]);
  });

  it("extracts lightweight project context from a biologist description", () => {
    expect(
      inferProjectContextFromDescription(
        "Mouse micro-CT nuclei dataset; segment nuclei at 4 x 4 x 40 nm and prioritize accuracy.",
      ),
    ).toEqual({
      freeform_note:
        "Mouse micro-CT nuclei dataset; segment nuclei at 4 x 4 x 40 nm and prioritize accuracy.",
      imaging_modality: "CT",
      target_structure: "nuclei",
      task_family: "nuclei instance segmentation",
      task_goal: "segmentation",
      optimization_priority: "accuracy",
      voxel_size_nm: [4, 4, 40],
      voxel_size_source: "project_description",
    });
  });

  it("derives guided defaults for the TapeReader XRI case study", () => {
    expect(
      getProjectContextDefaultsFromSuggestion({
        id: "yixiao-tapereader-xri-case-study",
        name: "yixiao_tapereader_xri_case_study",
        directory_path: "/home/weidf/demo_data/yixiao_tapereader_xri_case_study",
        description: "Yixiao TapeReader XRI fibre segmentation case study.",
        profile: {
          counts: { image: 10, label: 8, config: 3 },
          context_hints: {
            imaging_modality: "X-ray / XRI volumetric microscopy",
            target_structure: "CytoTape fibres",
            voxel_size_nm: [40, 16.3, 16.3],
          },
        },
      }),
    ).toEqual(
      expect.objectContaining({
        imaging_modality: "X-ray / XRI volumetric microscopy",
        target_structure: "CytoTape fibres",
        task_family: "XRI fibre instance segmentation",
        mask_status: "mixed: some masks, some image-only volumes",
        image_only_strategy: "run inference on image-only volumes later",
        training_policy: "train only on confirmed ground-truth masks",
        voxel_size_nm: [40, 16.3, 16.3],
      }),
    );
    expect(
      inferProjectContextFromDescription(
        "XRI CytoTape fibre masks at 40 x 16.3 x 16.3 nm.",
      ),
    ).toEqual(
      expect.objectContaining({
        imaging_modality: "X-ray / XRI volumetric microscopy",
        target_structure: "fibres",
        task_family: "XRI fibre instance segmentation",
        voxel_size_nm: [40, 16.3, 16.3],
      }),
    );
  });

  it("parses and formats isotropic imaging resolution", () => {
    const context = inferProjectContextFromDescription(
      "EM mitochondria stack; segmentation from one volume; prioritize accuracy; isotropic 5 nm voxels.",
    );
    expect(context).toEqual(
      expect.objectContaining({
        voxel_size_nm: [5, 5, 5],
      }),
    );
    expect(formatVoxelSizeNm(context.voxel_size_nm)).toBe("5 x 5 x 5 nm");
  });

  it("does not invent generic defaults from profiled folders", () => {
    expect(getProjectContextDefaultsFromSuggestion(batchSuggestion)).toEqual({});
    expect(
      getProjectContextDefaultsFromSuggestion({
        name: "prepilot_cremi_official",
        directory_path: "/projects/prepilot_cremi_official",
        profile: { counts: { image: 3, label: 3 } },
      }),
    ).toEqual({});
  });

  it("uses backend content hints instead of biological name guesses", () => {
    expect(
      getProjectContextDefaultsFromSuggestion({
        name: "opaque-project-name",
        directory_path: "/projects/opaque-project-name",
        profile: {
          counts: { image: 3, label: 3 },
          context_hints: {
            imaging_modality: "EM",
            target_structure: "neurites",
            task_goal: "proofreading",
            optimization_priority: "accuracy",
            voxel_size_nm: [40, 4, 4],
          },
        },
      }),
    ).toEqual(
      expect.objectContaining({
        imaging_modality: "EM",
        target_structure: "neurites",
        voxel_size_nm: [40, 4, 4],
        voxel_size_source: "project_profile",
      }),
    );
  });

  it("uses high-confidence audit facts for voxel size defaults", () => {
    expect(
      getProjectContextDefaultsFromSuggestion({
        name: "audit-project",
        directory_path: "/projects/audit-project",
        profile: {
          counts: { image: 1, label: 1 },
          context_hints: {
            imaging_modality: "EM",
            target_structure: "mitochondria",
            voxel_size_nm: [30, 6, 6],
          },
          audit: {
            context_facts: [
              {
                key: "voxel_size_nm",
                value: [30, 8, 8],
                source: "volume_metadata:data/image/sample.h5",
                confidence: "high",
              },
            ],
          },
        },
      }),
    ).toEqual(
      expect.objectContaining({
        imaging_modality: "EM",
        target_structure: "mitochondria",
        voxel_size_nm: [30, 8, 8],
        voxel_size_source: "volume_metadata:data/image/sample.h5",
      }),
    );
  });

  it("reports missing project context fields deterministically", () => {
    expect(
      evaluateProjectContextCompleteness("EM!", {}),
    ).toEqual(
      expect.objectContaining({
        context: expect.objectContaining({
          imaging_modality: "EM",
        }),
      }),
    );
    expect(
      evaluateProjectContextCompleteness("EM mitochondria", {}),
    ).toEqual(
      expect.objectContaining({
        complete: false,
        missing: ["imaging resolution"],
        next_question:
          "What is the voxel size or imaging resolution in z, y, x nanometers?",
      }),
    );
    expect(
      evaluateProjectContextCompleteness(
        "EM mitochondria segmentation from a single volume at 30 x 6 x 6 nm; prioritize accuracy.",
      ),
    ).toEqual(
      expect.objectContaining({
        complete: true,
        context: expect.objectContaining({
          imaging_modality: "EM",
          target_structure: "mitochondria",
          voxel_size_nm: [30, 6, 6],
        }),
      }),
    );
  });

  it("uses project defaults to avoid blocking on inferable context", () => {
    expect(
      evaluateProjectContextCompleteness("EM!", {
        defaultContext: getProjectContextDefaultsFromSuggestion({
          name: "opaque-project-name",
          directory_path: "/projects/opaque-project-name",
          profile: {
            counts: { image: 3, label: 3 },
            context_hints: {
              target_structure: "neurites",
              voxel_size_nm: [8, 8, 8],
            },
          },
        }),
      }),
    ).toEqual(
      expect.objectContaining({
        complete: true,
        missing: [],
        context: expect.objectContaining({
          imaging_modality: "EM",
          target_structure: "neurites",
          voxel_size_nm: [8, 8, 8],
          voxel_size_source: "project_profile",
        }),
      }),
    );
  });
});
