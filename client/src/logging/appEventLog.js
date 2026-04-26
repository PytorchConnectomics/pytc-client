const BASE_URL = `${process.env.REACT_APP_SERVER_PROTOCOL || "http"}://${process.env.REACT_APP_SERVER_URL || "localhost:4242"}`;
const LOG_ENDPOINT = `${BASE_URL}/app/log-event`;
const CLIENT_SESSION_ID = `client-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;

let installed = false;
const originalConsole = {};

const normalizeValue = (value, depth = 0, seen = new WeakSet()) => {
  if (depth > 3) {
    return "[max-depth]";
  }
  if (
    value === null ||
    value === undefined ||
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return value;
  }
  if (value instanceof Error) {
    return {
      name: value.name,
      message: value.message,
      stack: value.stack,
    };
  }
  if (Array.isArray(value)) {
    return value
      .slice(0, 20)
      .map((item) => normalizeValue(item, depth + 1, seen));
  }
  if (typeof value === "object") {
    if (seen.has(value)) {
      return "[circular]";
    }
    seen.add(value);
    const output = {};
    Object.entries(value)
      .slice(0, 20)
      .forEach(([key, item]) => {
        output[key] = normalizeValue(item, depth + 1, seen);
      });
    return output;
  }
  return String(value);
};

const formatConsoleArgs = (args) =>
  args
    .map((arg) => {
      if (typeof arg === "string") return arg;
      try {
        return JSON.stringify(normalizeValue(arg));
      } catch {
        return String(arg);
      }
    })
    .join(" ");

const sendPayload = (payload) => {
  const body = JSON.stringify(payload);
  try {
    if (typeof navigator !== "undefined" && navigator.sendBeacon) {
      const blob = new Blob([body], { type: "application/json" });
      if (navigator.sendBeacon(LOG_ENDPOINT, blob)) {
        return;
      }
    }
  } catch {
    // Fall through to fetch.
  }

  try {
    fetch(LOG_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      keepalive: true,
    }).catch(() => {});
  } catch {
    // Swallow client logging failures.
  }
};

export const logClientEvent = (
  event,
  { level = "INFO", message = "", data = null, source = "client", url } = {},
) => {
  sendPayload({
    event,
    level,
    message,
    data: data ? normalizeValue(data) : undefined,
    source,
    sessionId: CLIENT_SESSION_ID,
    url:
      url ||
      (typeof window !== "undefined" ? window.location.href : undefined),
  });
};

const installConsoleLogging = () => {
  ["log", "info", "warn", "error", "debug"].forEach((method) => {
    const original = console[method].bind(console);
    originalConsole[method] = original;
    console[method] = (...args) => {
      original(...args);
      logClientEvent("console_output", {
        level: method === "debug" ? "INFO" : method.toUpperCase(),
        message: formatConsoleArgs(args),
        data: { method, args: args.map((arg) => normalizeValue(arg)) },
        source: "console",
      });
    };
  });
};

export const installClientLogging = () => {
  if (installed || typeof window === "undefined") {
    return;
  }
  installed = true;

  installConsoleLogging();

  window.addEventListener("error", (event) => {
    logClientEvent("window_error", {
      level: "ERROR",
      message: event.message || "Unhandled window error",
      data: {
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
        error: normalizeValue(event.error),
      },
      source: "window",
    });
  });

  window.addEventListener("unhandledrejection", (event) => {
    logClientEvent("unhandled_rejection", {
      level: "ERROR",
      message: "Unhandled promise rejection",
      data: {
        reason: normalizeValue(event.reason),
      },
      source: "window",
    });
  });

  logClientEvent("app_boot", {
    level: "INFO",
    message: "React client booted",
    data: {
      userAgent: navigator.userAgent,
    },
    source: "client",
  });
};
