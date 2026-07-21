import {
  attachApiError,
  getApiErrorMessage,
  normalizeApiError,
} from "./apiError";

describe("API error normalization", () => {
  it("normalizes the structured server contract", () => {
    const result = normalizeApiError({
      response: {
        status: 503,
        data: {
          detail: "Worker is offline",
          error: {
            schema_version: 1,
            code: "service_unavailable",
            category: "availability",
            title: "Service temporarily unavailable",
            message: "Worker is offline",
            retryable: true,
            request_id: "req-7",
            recovery_actions: ["retry", "view_logs"],
          },
        },
      },
    });

    expect(result).toEqual(
      expect.objectContaining({
        code: "service_unavailable",
        message: "Worker is offline",
        requestId: "req-7",
        retryable: true,
        recoveryActions: ["retry", "view_logs"],
      }),
    );
  });

  it("supports legacy detail responses", () => {
    const result = normalizeApiError({
      response: {
        status: 404,
        headers: { "x-request-id": "legacy-4" },
        data: { detail: "Volume not found" },
      },
    });

    expect(result.code).toBe("not_found");
    expect(result.message).toBe("Volume not found");
    expect(result.requestId).toBe("legacy-4");
  });

  it("distinguishes network and cancellation failures", () => {
    expect(normalizeApiError(new Error("Network Error"))).toEqual(
      expect.objectContaining({
        code: "network_unavailable",
        retryable: true,
      }),
    );
    expect(normalizeApiError({ code: "ERR_CANCELED" })).toEqual(
      expect.objectContaining({
        code: "request_canceled",
        retryable: false,
      }),
    );
  });

  it("attaches the normalized value without replacing the original error", () => {
    const error = new Error("Network Error");

    expect(attachApiError(error)).toBe(error);
    expect(getApiErrorMessage(error)).toBe(
      "Check the server connection and try again.",
    );
  });
});
