const DEFAULT_ERROR = {
  code: "request_failed",
  category: "request",
  title: "Request failed",
  message: "The request could not be completed.",
  retryable: false,
  recoveryActions: [],
  validationErrors: [],
};

const messageFromDetail = (detail) => {
  if (!detail) return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map(messageFromDetail).filter(Boolean).join("; ");
  }
  if (typeof detail === "object") {
    if (detail.user_message) return messageFromDetail(detail.user_message);
    return [
      detail.message,
      detail.detail,
      detail.reason,
      detail.upstream_body,
      detail.error,
    ]
      .map(messageFromDetail)
      .filter(Boolean)
      .join(" | ");
  }
  return String(detail);
};

const statusDefaults = (status) => {
  if (status === 401) {
    return {
      code: "authentication_required",
      category: "authentication",
      title: "Authentication required",
      recoveryActions: ["sign_in"],
    };
  }
  if (status === 403) {
    return {
      code: "permission_denied",
      category: "authorization",
      title: "Permission denied",
      recoveryActions: ["contact_admin"],
    };
  }
  if (status === 404) {
    return {
      code: "not_found",
      category: "resource",
      title: "Resource not found",
      recoveryActions: ["go_back"],
    };
  }
  if (status === 409) {
    return {
      code: "conflict",
      category: "state",
      title: "State conflict",
      recoveryActions: ["refresh"],
    };
  }
  if (status === 422) {
    return {
      code: "validation_failed",
      category: "validation",
      title: "Some request values are invalid",
      recoveryActions: ["review_input"],
    };
  }
  if (status === 429 || status >= 500) {
    return {
      code: status === 429 ? "rate_limited" : "service_unavailable",
      category: "availability",
      title:
        status === 429
          ? "Too many requests"
          : "Service temporarily unavailable",
      retryable: true,
      recoveryActions: ["retry"],
    };
  }
  return {};
};

export const normalizeApiError = (error) => {
  if (error?.apiError) return error.apiError;

  const response = error?.response;
  const status = response?.status || null;
  const payload = response?.data || {};
  const contract = payload?.error || {};
  const isCanceled =
    error?.code === "ERR_CANCELED" || error?.name === "CanceledError";
  const isTimeout = error?.code === "ECONNABORTED";
  const isNetworkError = !response && !isCanceled && !isTimeout;

  let transportDefaults = {};
  if (isCanceled) {
    transportDefaults = {
      code: "request_canceled",
      category: "cancellation",
      title: "Request canceled",
      message: "The operation was canceled.",
    };
  } else if (isTimeout) {
    transportDefaults = {
      code: "request_timeout",
      category: "availability",
      title: "Request timed out",
      message: "The server did not respond in time.",
      retryable: true,
      recoveryActions: ["retry"],
    };
  } else if (isNetworkError) {
    transportDefaults = {
      code: "network_unavailable",
      category: "availability",
      title: "Cannot reach the server",
      message: "Check the server connection and try again.",
      retryable: true,
      recoveryActions: ["retry"],
    };
  }

  const defaults = {
    ...DEFAULT_ERROR,
    ...statusDefaults(status),
    ...transportDefaults,
  };
  const responseRequestId =
    response?.headers?.["x-request-id"] ||
    response?.headers?.get?.("x-request-id") ||
    null;

  return {
    schemaVersion: contract.schema_version || null,
    code: contract.code || defaults.code,
    category: contract.category || defaults.category,
    title: contract.title || defaults.title,
    message:
      contract.message ||
      messageFromDetail(payload?.detail) ||
      transportDefaults.message ||
      error?.message ||
      defaults.message,
    status,
    retryable:
      typeof contract.retryable === "boolean"
        ? contract.retryable
        : Boolean(defaults.retryable),
    requestId: contract.request_id || responseRequestId,
    recoveryActions:
      contract.recovery_actions || defaults.recoveryActions || [],
    validationErrors: contract.validation_errors || [],
  };
};

export const attachApiError = (error) => {
  if (error && typeof error === "object") {
    error.apiError = normalizeApiError(error);
  }
  return error;
};

export const getApiErrorMessage = (error, fallback = DEFAULT_ERROR.message) =>
  normalizeApiError(error)?.message || fallback;
