/**
 * @typedef {Object} FrameRequest
 * @property {number} sessionId
 * @property {number} instanceId
 * @property {"xy"|"zx"|"zy"} axis
 * @property {number} zIndex
 * @property {"preview"|"full"} quality
 * @property {boolean} includeAll
 * @property {boolean} includeActive
 * @property {"interactive"|"nearby"|"background"} priority
 */

/**
 * @typedef {Object} FramePayload
 * @property {"xy"|"zx"|"zy"} axis
 * @property {number} zIndex
 * @property {number} totalLayers
 * @property {"preview"|"full"} quality
 * @property {string|null} imageUrl
 * @property {string|null} maskAllUrl
 * @property {string|null} maskActiveUrl
 */

export const ProofreadingLanes = Object.freeze({
  INTERACTIVE: "interactive",
  NEARBY: "nearby",
  BACKGROUND: "background",
});
