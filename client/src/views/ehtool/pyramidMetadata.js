const parsePyramidVectorHeader = (value) => {
  if (!value) return null;
  try {
    const parsed = JSON.parse(value);
    if (!Array.isArray(parsed)) return null;
    const vector = parsed.map(Number);
    return vector.every(Number.isFinite) ? vector : null;
  } catch (_error) {
    return null;
  }
};

const decodePyramidHeader = (value) => {
  if (!value) return null;
  try {
    return decodeURIComponent(value);
  } catch (_error) {
    return value;
  }
};

export const parsePyramidHeaders = (headers = {}) => {
  const rawLevel = headers["x-pyramid-level"];
  if (rawLevel === undefined || rawLevel === null || rawLevel === "") {
    return null;
  }
  const level = Number(rawLevel);
  if (!Number.isFinite(level)) return null;
  const authoritativeLevel = Number(
    headers["x-pyramid-authoritative-level"] ?? 0,
  );
  const datasetKey = decodePyramidHeader(headers["x-pyramid-dataset-key"]);
  const source = decodePyramidHeader(headers["x-pyramid-source"]);
  const explicitRevision = decodePyramidHeader(headers["x-pyramid-revision"]);
  const revision =
    explicitRevision || [source, datasetKey].filter(Boolean).join("#") || null;
  return {
    level,
    authoritativeLevel: Number.isFinite(authoritativeLevel)
      ? authoritativeLevel
      : 0,
    scale: parsePyramidVectorHeader(headers["x-pyramid-scale"]),
    translation: parsePyramidVectorHeader(headers["x-pyramid-translation"]),
    baseShape: parsePyramidVectorHeader(headers["x-pyramid-base-shape"]),
    datasetKey,
    source,
    revision,
  };
};

export const resolvePyramidLevelForQuality = (levels, quality) =>
  levels.get(quality) ??
  (quality !== "full" ? levels.get("preview") : undefined) ??
  "auto";

export const isAuthoritativeMaskForPlane = ({
  planeState,
  axis,
  targetIndex,
  instanceId,
}) =>
  planeState?.axis === axis &&
  planeState?.zIndex === targetIndex &&
  planeState?.instanceId === instanceId &&
  Boolean(planeState?.maskRawBase64) &&
  planeState?.maskRawAuthoritative === true;
