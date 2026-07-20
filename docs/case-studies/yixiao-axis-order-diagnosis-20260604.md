# Yixiao Axis-Order Diagnosis (UG/UM Neuroglancer)

- Date (UTC): 2026-06-04
- Scope: `server_api/main.py`, `server_api/workflows/volume_io.py`, Yixiao TIFF pairs in
  `/home/weidf/demo_data/yixiao_tapereader_xri_case_study`
- Focus pair: `data/raw/1/1-xri_raw.tif` and `data/seg/1/1-mask.tif` (plus additional samples)

## Findings (TIFF ground-truth pairs)

Using `tifffile.imread` directly on raw/mask files:

- `1/1`: raw `(49, 500, 500)`, raw dtype `uint16`; mask `(49, 500, 500)`, mask dtype `int32`.
- `2/2`: raw `(49, 500, 500)`, raw dtype `uint16`; mask `(49, 500, 500)`, mask dtype `int64`.
- `3/3`: raw `(49, 500, 500)`, raw dtype `uint16`; mask `(49, 500, 500)`, mask dtype `int64`.
- `4_1`: raw `(40, 500, 500)`, raw dtype `uint16`; mask `(40, 500, 500)`, mask dtype `int64`.
- `4_2`: raw `(40, 500, 500)`, raw dtype `uint16`; mask `(40, 500, 500)`, mask dtype `int64`.
- `4_3`: raw `(40, 500, 500)`, raw dtype `uint16`; mask `(40, 500, 500)`, mask dtype `int64`.
- `5_1`: raw `(40, 500, 500)`, raw dtype `uint16`; mask `(40, 500, 500)`, mask dtype `int64`.
- `5_2`: raw `(40, 500, 500)`, raw dtype `uint16`; mask `(40, 500, 500)`, mask dtype `int64`.

All sampled pairs have raw/label shape equality and match manifest `shape_zyx` for each volume, including the leading dimension being `49` or `40`.

### Axis plausibility checks

For each pair, I computed simple slice-alignment metrics between raw and mask under permutations where axis `axis` is considered the Neuroglancer “front” axis:

- Axis 0 (as-is, z-first): produces low slice count (`49` or `40`) and mask bbox spans such as `(2,35)`, `(0,40)`, etc., matching the known physical depth.
- Axis 1/2 (swapped candidates): forces `500` slices and full-length span across all near-all slices.

Examples:

- `1`: axis0 correlation (raw mean/mask mean) `0.853`, axis1 `0.390`, axis2 `0.252`; nonzero-slice occupancy axis0 `34/49`, axis1 `490/500`, axis2 `482/500`.
- `4_1`: axis0 correlation `0.796`, axis1 `0.864`, axis2 `0.849`; however axis0 has expected 40 slices total while axis1/2 have 500.
- `4_2`: axis0 correlation `0.731`, axis1 `0.733`, axis2 `0.781`; again expected depth is preserved only when first axis remains 40.

Because the TIFF tensors already have one short depth-like axis (`40`/`49`) and one long axis pair (`500`/`500`), swapping to any 500-first interpretation would imply a physically implausible 500-slice z stack and would invert expected scale mapping.

## Neuroglancer construction review

In `server_api/main.py`:

- `/neuroglancer` and `/neuroglancer/proofread` both derive scales with `_coerce_neuroglancer_scales(scales)` which validates required `z, y, x` order.
- They build `CoordinateSpace(names=["z", "y", "x"], units=["nm","nm","nm"], scales=scales)`.
- They pass image/label arrays directly into `neuroglancer.LocalVolume(data, dimensions=res, ...)` through `_build_neuroglancer_layer`.
- No `np.moveaxis`/`np.transpose` is applied around loaded arrays in these paths.

`load_volume()` in `server_api/workflows/volume_io.py` also returns arrays as read (with optional channel slicing only); no axis permutation is introduced for TIFF paths.

## Diagnosis

I did not find evidence of an axis-order bug in the current Neuroglancer path for Yixiao ground-truth pairs.

Recommended action: **no code patch** for axis order at this time.

Optional next step: add a lightweight regression test (skipped when dataset is missing) that asserts manifest-matched pairs preserve `shape_zyx` and that the smallest axis remains first (`shape[0] in {40,49}` for this case study).

## Evidence artifacts

- Diagnostic outputs generated from ad-hoc Python checks:
  - `raw/mask shapes + dtype`
  - `mask bbox` and `nonzero counts`
  - `axis0/1/2 slice-alignment correlation` and `nonzero slice occupancy`
- Code paths verified directly from `server_api/main.py`, `server_api/workflows/volume_io.py`.
