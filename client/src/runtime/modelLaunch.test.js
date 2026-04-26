import yaml from "js-yaml";

import {
  buildInferenceLaunchRequest,
  buildTrainingLaunchRequest,
} from "./modelLaunch";

jest.mock("../api", () => ({
  startModelInference: jest.fn(),
  startModelTraining: jest.fn(),
}));

describe("modelLaunch helpers", () => {
  it("builds a training launch request from app context state", () => {
    const request = buildTrainingLaunchRequest(
      {
        trainingConfig: `
DATASET:
  INPUT_PATH: ""
  IMAGE_NAME: ""
  LABEL_NAME: ""
  OUTPUT_PATH: ""
`,
        trainingState: {
          inputImage: "/tmp/image.tif",
          inputLabel: "/tmp/label.tif",
          outputPath: "/tmp/train-out",
          logPath: "",
          configOriginPath: "/tmp/training.yaml",
        },
      },
      7,
    );

    const parsed = yaml.load(request.trainingConfig);
    expect(parsed.DATASET.OUTPUT_PATH).toBe("/tmp/train-out");
    expect(request.logPath).toBe("/tmp/train-out");
    expect(request.configOriginPath).toBe("/tmp/training.yaml");
    expect(request.workflowId).toBe(7);
  });

  it("uses runtime overrides when building an inference launch request", () => {
    const request = buildInferenceLaunchRequest(
      {
        inferenceConfig: `
INFERENCE:
  OUTPUT_PATH: ""
`,
        inferenceState: {
          inputImage: "/tmp/default-image.tif",
          outputPath: "/tmp/default-out",
          checkpointPath: "/tmp/default.ckpt",
        },
      },
      9,
      {
        outputPath: "/tmp/runtime-out",
        checkpointPath: "/tmp/runtime.ckpt",
      },
    );

    expect(request.outputPath).toBe("/tmp/runtime-out");
    expect(request.checkpointPath).toBe("/tmp/runtime.ckpt");
    expect(request.workflowId).toBe(9);
  });

  it("rejects inference launches without a checkpoint", () => {
    expect(() =>
      buildInferenceLaunchRequest({
        inferenceConfig: "INFERENCE: {}",
        inferenceState: {},
      }),
    ).toThrow("Please set checkpoint path first.");
  });

  it("falls back to the training config when the persisted inference config is incompatible", () => {
    const request = buildInferenceLaunchRequest({
      trainingConfig: `
DATASET:
  INPUT_PATH: ""
  IMAGE_NAME: ""
INFERENCE:
  OUTPUT_PATH: ""
`,
      inferenceConfig: `
default:
  inference:
    batch_size: 1
`,
      trainingState: {
        configOriginPath: "configs/MitoEM/Mito25-Local-BC.yaml",
      },
      inferenceState: {
        configOriginPath: "tutorials/neuron_nisb_9nm_base.yaml",
        inputImage: "/tmp/inference-image.h5",
        outputPath: "/tmp/inference-out",
        checkpointPath: "/tmp/model.ckpt",
      },
    });

    const parsed = yaml.load(request.inferenceConfig);
    expect(parsed.DATASET.IMAGE_NAME).toBe("/tmp/inference-image.h5");
    expect(request.configOriginPath).toBe("configs/MitoEM/Mito25-Local-BC.yaml");
  });
});
