import {
  isAuthoritativeMaskForPlane,
  parsePyramidHeaders,
  resolvePyramidLevelForQuality,
} from "./pyramidMetadata";

describe("DetectionWorkflow pyramid metadata", () => {
  test("parses encoded coordinate metadata", () => {
    expect(
      parsePyramidHeaders({
        "x-pyramid-level": "2",
        "x-pyramid-authoritative-level": "0",
        "x-pyramid-scale": "[4,2,2]",
        "x-pyramid-translation": "[0,0,0]",
        "x-pyramid-base-shape": "[64,512,512]",
        "x-pyramid-dataset-key": "pyramid%2F2",
        "x-pyramid-source": "%2Fdata%2Fimage.zarr",
        "x-pyramid-revision": "revision%3A7",
      }),
    ).toEqual({
      level: 2,
      authoritativeLevel: 0,
      scale: [4, 2, 2],
      translation: [0, 0, 0],
      baseShape: [64, 512, 512],
      datasetKey: "pyramid/2",
      source: "/data/image.zarr",
      revision: "revision:7",
    });
  });

  test("rejects malformed level metadata and ignores invalid vectors", () => {
    expect(parsePyramidHeaders({})).toBeNull();
    expect(parsePyramidHeaders({ "x-pyramid-level": "coarse" })).toBeNull();
    expect(
      parsePyramidHeaders({
        "x-pyramid-level": "1",
        "x-pyramid-scale": '[2,"bad",2]',
      }).scale,
    ).toBeNull();
  });

  test("preview labels share the observed server preview level", () => {
    const levels = new Map([["preview", 2]]);
    expect(resolvePyramidLevelForQuality(levels, "thumb-192")).toBe(2);
    expect(resolvePyramidLevelForQuality(levels, "preview-384")).toBe(2);
    expect(resolvePyramidLevelForQuality(levels, "full")).toBe("auto");
  });

  test("only full-resolution masks are eligible for save", () => {
    const base = {
      axis: "xy",
      zIndex: 6,
      instanceId: 12,
      maskRawBase64: "blob:mask",
    };
    const matches = (planeState) =>
      isAuthoritativeMaskForPlane({
        planeState,
        axis: "xy",
        targetIndex: 6,
        instanceId: 12,
      });

    expect(matches({ ...base, maskRawAuthoritative: false })).toBe(false);
    expect(matches({ ...base, maskRawAuthoritative: true })).toBe(true);
    expect(matches({ ...base, zIndex: 5, maskRawAuthoritative: true })).toBe(
      false,
    );
  });
});
