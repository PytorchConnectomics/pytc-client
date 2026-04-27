import {
  buildWorkflowPatchFromConfirmedProjectRoles,
  buildWorkflowPatchFromProjectSuggestion,
  getProjectRoleDefaultsFromSuggestion,
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
});
