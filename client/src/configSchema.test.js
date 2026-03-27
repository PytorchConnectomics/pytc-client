import { applyInputPaths, setInferenceExecutionDefaults } from "./configSchema";

describe("setInferenceExecutionDefaults", () => {
  it("preserves existing legacy GPU values", () => {
    const config = {
      SYSTEM: {
        NUM_GPUS: -1,
      },
    };

    setInferenceExecutionDefaults(config);

    expect(config.SYSTEM.NUM_GPUS).toBe(-1);
  });

  it("preserves existing v2 GPU values", () => {
    const config = {
      system: {
        num_gpus: 4,
      },
    };

    setInferenceExecutionDefaults(config);

    expect(config.system.num_gpus).toBe(4);
  });

  it("adds a GPU default only when the config is missing one", () => {
    const config = {};

    setInferenceExecutionDefaults(config);

    expect(config.system.num_gpus).toBe(1);
  });
});

describe("applyInputPaths", () => {
  it("supports inference configs without a label path", () => {
    const config = {
      test: {
        data: {
          test: {
            image: "datasets/old-image.h5",
            label: "datasets/old-label.h5",
          },
        },
      },
      inference: {
        save_prediction: {
          output_path: "outputs/old",
        },
      },
    };

    applyInputPaths(config, {
      mode: "inference",
      inputImagePath: "/tmp/new-image.h5",
      inputLabelPath: "",
      inputPath: "",
      outputPath: "/tmp/out",
    });

    expect(config.test.data.test.image).toBe("/tmp/new-image.h5");
    expect("label" in config.test.data.test).toBe(false);
    expect(config.inference.save_prediction.output_path).toBe("/tmp/out");
  });
});
