import {
  basename,
  getProofreadingImagePath,
  getProofreadingMaskPath,
  getProofreadingProjectName,
  getTrainingReadyCorrectedMask,
} from "./proofreadingPaths";

describe("proofreadingPaths", () => {
  it("uses image or dataset paths for the source image, not prediction outputs", () => {
    expect(
      getProofreadingImagePath({
        image_path: "/project/data/image/a.h5",
        dataset_path: "/project/data/image/fallback.h5",
        inference_output_path: "/project/outputs/pred.h5",
      }),
    ).toBe("/project/data/image/a.h5");

    expect(
      getProofreadingImagePath({
        dataset_path: "/project/data/image/fallback.h5",
        inference_output_path: "/project/outputs/pred.h5",
      }),
    ).toBe("/project/data/image/fallback.h5");

    expect(
      getProofreadingImagePath({
        inference_output_path: "/project/outputs/pred.h5",
      }),
    ).toBe("");
  });

  it("chooses the most useful mask candidate for proofreading", () => {
    expect(
      getProofreadingMaskPath({
        corrected_mask_path: "/project/corrected.tif",
        inference_output_path: "/project/pred.h5",
        mask_path: "/project/mask.h5",
        label_path: "/project/label.h5",
      }),
    ).toBe("/project/corrected.tif");

    expect(
      getProofreadingMaskPath({
        inference_output_path: "/project/pred.h5",
        mask_path: "/project/mask.h5",
        label_path: "/project/label.h5",
      }),
    ).toBe("/project/pred.h5");

    expect(
      getProofreadingMaskPath({
        mask_path: "/project/mask.h5",
        label_path: "/project/label.h5",
      }),
    ).toBe("/project/mask.h5");
  });

  it("only stages real corrected artifacts for retraining", () => {
    expect(
      getTrainingReadyCorrectedMask({
        persistence: {
          artifact_path: "/project/.pytc_instance_labels.tif",
          artifact_exists: false,
        },
        workflow: {
          mask_path: "/project/original-mask.h5",
          label_path: "/project/original-label.h5",
        },
      }),
    ).toEqual({ path: "", source: "" });

    expect(
      getTrainingReadyCorrectedMask({
        persistence: {
          artifact_path: "/project/.pytc_instance_labels.tif",
          artifact_exists: true,
        },
      }),
    ).toEqual({
      path: "/project/.pytc_instance_labels.tif",
      source: "proofreading_persistence",
    });

    expect(
      getTrainingReadyCorrectedMask({
        persistence: {
          artifact_path: "/project/.pytc_instance_labels.tif",
          artifact_exists: true,
          last_export_path: "/project/corrected/export.tif",
        },
      }),
    ).toEqual({
      path: "/project/corrected/export.tif",
      source: "proofreading_export",
    });
  });

  it("keeps display names stable", () => {
    expect(basename("/tmp/project/data/")).toBe("data");
    expect(getProofreadingProjectName({ metadata: { projectName: "Mouse EM" } })).toBe(
      "Mouse EM",
    );
  });
});
