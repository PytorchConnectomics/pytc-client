import {
  buildWorkflowPatchFromConfirmedProjectRoles,
  buildWorkflowPatchFromProjectSuggestion,
  getProjectVolumeSetsFromSuggestion,
  getProjectRoleDefaultsFromSuggestion,
  getProjectContextDefaultsFromSuggestion,
  evaluateProjectContextCompleteness,
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
        "Mouse micro-CT nuclei dataset; segment nuclei and prioritize accuracy.",
      ),
    ).toEqual({
      freeform_note:
        "Mouse micro-CT nuclei dataset; segment nuclei and prioritize accuracy.",
      imaging_modality: "CT",
      target_structure: "nuclei",
      task_goal: "segmentation",
      optimization_priority: "accuracy",
    });
  });

  it("infers only structural defaults from profiled folders", () => {
    expect(getProjectContextDefaultsFromSuggestion(batchSuggestion)).toEqual(
      expect.objectContaining({
        data_unit: "folder of volumes",
        task_goal: "segmentation",
        optimization_priority: "accuracy",
      }),
    );
    expect(
      getProjectContextDefaultsFromSuggestion({
        name: "prepilot_cremi_official",
        directory_path: "/projects/prepilot_cremi_official",
        profile: { counts: { image: 3, label: 3 } },
      }),
    ).toEqual({
      data_unit: "folder of volumes",
      task_goal: "segmentation",
      optimization_priority: "accuracy",
    });
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
          },
        },
      }),
    ).toEqual(
      expect.objectContaining({
        imaging_modality: "EM",
        target_structure: "neurites",
        task_goal: "proofreading",
        optimization_priority: "accuracy",
        data_unit: "folder of volumes",
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
        missing: expect.arrayContaining([
          "task goal",
          "data organization",
          "speed vs accuracy preference",
        ]),
        next_question:
          "Is the immediate goal segmentation, proofreading, training, or comparison?",
      }),
    );
    expect(
      evaluateProjectContextCompleteness(
        "EM mitochondria segmentation from a single volume; prioritize accuracy.",
      ),
    ).toEqual(
      expect.objectContaining({
        complete: true,
        context: expect.objectContaining({
          imaging_modality: "EM",
          target_structure: "mitochondria",
          task_goal: "segmentation",
          data_unit: "single volume",
          optimization_priority: "accuracy",
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
          data_unit: "folder of volumes",
          task_goal: "segmentation",
          optimization_priority: "accuracy",
        }),
      }),
    );
  });
});
