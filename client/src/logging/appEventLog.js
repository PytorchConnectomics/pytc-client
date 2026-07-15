const isLocalHost = (hostname) =>
  /^(localhost|127\.0\.0\.1)$/.test(hostname || "");

const removeTrailingSlash = (value) => value.replace(/\/+$/, "");

const getDefaultBaseUrl = () => {
  if (
    typeof window !== "undefined" &&
    window.location?.origin &&
    !isLocalHost(window.location.hostname)
  ) {
    return `${window.location.origin}/api`;
  }

  return `${process.env.REACT_APP_SERVER_PROTOCOL || "http"}://${process.env.REACT_APP_SERVER_URL || "localhost:4242"}`;
};

const BASE_URL = removeTrailingSlash(
  process.env.REACT_APP_API_BASE_URL || getDefaultBaseUrl(),
);
const LOG_ENDPOINT = `${BASE_URL}/app/log-event`;
const CLIENT_SESSION_ID = `client-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
const envFlagEnabled = (name, defaultValue = true) => {
  const rawValue = process.env[name];
  if (rawValue === undefined || rawValue === "") return defaultValue;
  return !["0", "false", "off", "no"].includes(String(rawValue).toLowerCase());
};

const CAPTURE_CONSOLE_LOGS = envFlagEnabled(
  "REACT_APP_CAPTURE_CONSOLE_LOGS",
  true,
);
const CAPTURE_BROWSER_NETWORK = envFlagEnabled(
  "REACT_APP_CAPTURE_BROWSER_NETWORK",
  true,
);
const CAPTURE_DOM_EVENTS = envFlagEnabled("REACT_APP_CAPTURE_DOM_EVENTS", true);
const CAPTURE_RESOURCE_TIMING = envFlagEnabled(
  "REACT_APP_CAPTURE_RESOURCE_TIMING",
  true,
);
const MAX_SEND_FAILURES = 3;
const DOM_EVENT_TYPES = [
  "click",
  "dblclick",
  "submit",
  "change",
  "input",
  "keydown",
  "keyup",
  "focusin",
  "focusout",
  "dragstart",
  "drop",
  "paste",
];
const LOG_ENDPOINT_PATH = (() => {
  try {
    return new URL(LOG_ENDPOINT).pathname;
  } catch {
    return "/app/log-event";
  }
})();

let installed = false;
const originalConsole = {};
let originalFetch = null;
let originalXHROpen = null;
let originalXHRSend = null;
let originalPushState = null;
let originalReplaceState = null;
let sendFailures = 0;
let loggingDisabledUntil = 0;
let lastDomEventAtByKey = {};

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

const normalizeUrl = (url) => {
  if (!url) return "";
  if (typeof url === "string") return url;
  if (typeof URL !== "undefined" && url instanceof URL) return url.toString();
  if (typeof Request !== "undefined" && url instanceof Request) return url.url;
  return String(url);
};

const shouldSkipLogUrl = (url) => {
  const normalized = normalizeUrl(url);
  if (!normalized) return false;
  try {
    const parsed = new URL(
      normalized,
      typeof window !== "undefined" ? window.location.href : undefined,
    );
    return parsed.pathname === LOG_ENDPOINT_PATH;
  } catch {
    return normalized.includes("/app/log-event");
  }
};

const nowMs = () =>
  typeof performance !== "undefined" ? performance.now() : Date.now();

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
  if (
    sendFailures >= MAX_SEND_FAILURES &&
    typeof Date !== "undefined" &&
    Date.now() < loggingDisabledUntil
  ) {
    return;
  }

  const body = JSON.stringify(payload);

  try {
    const fetchImpl =
      originalFetch ||
      (typeof window !== "undefined" && window.fetch
        ? window.fetch.bind(window)
        : null);
    if (!fetchImpl) return;

    fetchImpl(LOG_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      keepalive: true,
    })
      .then((response) => {
        if (response.ok) {
          sendFailures = 0;
          return;
        }
        sendFailures += 1;
        if (sendFailures >= MAX_SEND_FAILURES) {
          loggingDisabledUntil = Date.now() + 60000;
        }
      })
      .catch(() => {
        sendFailures += 1;
        if (sendFailures >= MAX_SEND_FAILURES) {
          loggingDisabledUntil = Date.now() + 60000;
        }
      });
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
      url || (typeof window !== "undefined" ? window.location.href : undefined),
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

const summarizeElement = (target) => {
  if (!target || !target.tagName) return {};
  const text = String(target.innerText || target.textContent || "")
    .replace(/\s+/g, " ")
    .trim();
  const value =
    "value" in target && typeof target.value === "string" ? target.value : "";
  return {
    tagName: target.tagName,
    id: target.id || "",
    className: String(target.className || "").slice(0, 160),
    name: target.name || "",
    role: target.getAttribute?.("role") || "",
    ariaLabel: target.getAttribute?.("aria-label") || "",
    title: target.getAttribute?.("title") || "",
    textPreview: text.slice(0, 120),
    valueLength: value.length,
    checked: typeof target.checked === "boolean" ? target.checked : undefined,
    href: target.href || undefined,
    src: target.src || undefined,
  };
};

const shouldLogDomEvent = (event) => {
  if (event.type !== "input") return true;
  const key = [
    event.type,
    event.target?.tagName || "",
    event.target?.id || "",
    event.target?.name || "",
    event.target?.className || "",
  ].join("|");
  const current = Date.now();
  if (current - (lastDomEventAtByKey[key] || 0) < 750) {
    return false;
  }
  lastDomEventAtByKey[key] = current;
  return true;
};

const installDomEventLogging = () => {
  DOM_EVENT_TYPES.forEach((eventType) => {
    document.addEventListener(
      eventType,
      (event) => {
        if (!shouldLogDomEvent(event)) return;
        logClientEvent(`dom_${eventType}`, {
          level: "INFO",
          message: `${eventType} ${event.target?.tagName || "target"}`,
          source: "dom",
          data: {
            eventType,
            key: event.key,
            code: event.code,
            altKey: event.altKey,
            ctrlKey: event.ctrlKey,
            metaKey: event.metaKey,
            shiftKey: event.shiftKey,
            button: event.button,
            target: summarizeElement(event.target),
          },
        });
      },
      true,
    );
  });

  document.addEventListener(
    "error",
    (event) => {
      const target = event.target;
      if (!target || target === window) return;
      logClientEvent("resource_error", {
        level: "ERROR",
        message: `Resource failed to load: ${target.tagName || "target"}`,
        source: "resource",
        data: { target: summarizeElement(target) },
      });
    },
    true,
  );
};

const installFetchLogging = () => {
  if (typeof window.fetch !== "function") return;
  originalFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const [input, init = {}] = args;
    const url = normalizeUrl(input);
    const startedAt = nowMs();
    const skip = shouldSkipLogUrl(url);
    if (!skip) {
      logClientEvent("browser_fetch_request", {
        level: "INFO",
        message: `${init?.method || input?.method || "GET"} ${url}`,
        source: "fetch",
        data: {
          method: init?.method || input?.method || "GET",
          url,
          keepalive: Boolean(init?.keepalive),
        },
      });
    }
    try {
      const response = await originalFetch(...args);
      if (!skip) {
        logClientEvent("browser_fetch_response", {
          level: response.ok ? "INFO" : "ERROR",
          message: `${init?.method || input?.method || "GET"} ${url} -> ${response.status}`,
          source: "fetch",
          data: {
            method: init?.method || input?.method || "GET",
            url,
            status: response.status,
            ok: response.ok,
            latencyMs: Number((nowMs() - startedAt).toFixed(2)),
          },
        });
      }
      return response;
    } catch (error) {
      if (!skip) {
        logClientEvent("browser_fetch_failed", {
          level: "ERROR",
          message: `${init?.method || input?.method || "GET"} ${url} failed`,
          source: "fetch",
          data: {
            method: init?.method || input?.method || "GET",
            url,
            latencyMs: Number((nowMs() - startedAt).toFixed(2)),
            error: normalizeValue(error),
          },
        });
      }
      throw error;
    }
  };
};

const installXhrLogging = () => {
  if (typeof XMLHttpRequest === "undefined") return;
  originalXHROpen = XMLHttpRequest.prototype.open;
  originalXHRSend = XMLHttpRequest.prototype.send;

  XMLHttpRequest.prototype.open = function open(method, url, ...rest) {
    this.__pytcLog = {
      method: method || "GET",
      url: normalizeUrl(url),
      startedAt: null,
      skip: shouldSkipLogUrl(url),
    };
    return originalXHROpen.call(this, method, url, ...rest);
  };

  XMLHttpRequest.prototype.send = function send(body) {
    const meta = this.__pytcLog || {};
    meta.startedAt = nowMs();
    if (!meta.skip) {
      logClientEvent("browser_xhr_request", {
        level: "INFO",
        message: `${meta.method || "GET"} ${meta.url}`,
        source: "xhr",
        data: {
          method: meta.method || "GET",
          url: meta.url,
          bodyType: body ? Object.prototype.toString.call(body) : null,
        },
      });
    }

    this.addEventListener("loadend", () => {
      if (meta.skip) return;
      logClientEvent("browser_xhr_response", {
        level: this.status >= 400 ? "ERROR" : "INFO",
        message: `${meta.method || "GET"} ${meta.url} -> ${this.status}`,
        source: "xhr",
        data: {
          method: meta.method || "GET",
          url: meta.url,
          status: this.status,
          latencyMs:
            meta.startedAt !== null
              ? Number((nowMs() - meta.startedAt).toFixed(2))
              : null,
        },
      });
    });

    this.addEventListener("error", () => {
      if (meta.skip) return;
      logClientEvent("browser_xhr_failed", {
        level: "ERROR",
        message: `${meta.method || "GET"} ${meta.url} failed`,
        source: "xhr",
        data: {
          method: meta.method || "GET",
          url: meta.url,
          latencyMs:
            meta.startedAt !== null
              ? Number((nowMs() - meta.startedAt).toFixed(2))
              : null,
        },
      });
    });

    return originalXHRSend.call(this, body);
  };
};

const logNavigation = (event, extra = {}) => {
  logClientEvent(event, {
    level: "INFO",
    message: `${event}: ${window.location.href}`,
    source: "navigation",
    data: {
      href: window.location.href,
      pathname: window.location.pathname,
      search: window.location.search,
      hash: window.location.hash,
      ...extra,
    },
  });
};

const installNavigationLogging = () => {
  originalPushState = window.history.pushState;
  originalReplaceState = window.history.replaceState;
  window.history.pushState = function pushState(state, title, url) {
    const result = originalPushState.apply(this, arguments);
    logNavigation("history_push_state", {
      targetUrl: normalizeUrl(url),
      state,
    });
    return result;
  };
  window.history.replaceState = function replaceState(state, title, url) {
    const result = originalReplaceState.apply(this, arguments);
    logNavigation("history_replace_state", {
      targetUrl: normalizeUrl(url),
      state,
    });
    return result;
  };
  window.addEventListener("popstate", (event) =>
    logNavigation("history_pop_state", { state: event.state }),
  );
  window.addEventListener("hashchange", () => logNavigation("hash_change"));
  window.addEventListener("online", () => logNavigation("browser_online"));
  window.addEventListener("offline", () => logNavigation("browser_offline"));
  document.addEventListener("visibilitychange", () =>
    logClientEvent("visibility_change", {
      level: "INFO",
      message: `document visibility: ${document.visibilityState}`,
      source: "browser",
      data: { visibilityState: document.visibilityState },
    }),
  );
  window.addEventListener("focus", () => logNavigation("window_focus"));
  window.addEventListener("blur", () => logNavigation("window_blur"));
  window.addEventListener("message", (event) => {
    logClientEvent("window_message", {
      level: "INFO",
      message: `message from ${event.origin || "unknown origin"}`,
      source: "window",
      data: {
        origin: event.origin,
        data: normalizeValue(event.data),
      },
    });
  });
};

const installResourceTimingLogging = () => {
  if (
    typeof PerformanceObserver === "undefined" ||
    !PerformanceObserver.supportedEntryTypes?.includes("resource")
  ) {
    return;
  }
  const observer = new PerformanceObserver((list) => {
    list.getEntries().forEach((entry) => {
      if (shouldSkipLogUrl(entry.name)) return;
      logClientEvent("resource_timing", {
        level: "INFO",
        message: `${entry.initiatorType || "resource"} ${entry.name}`,
        source: "performance",
        data: {
          name: entry.name,
          initiatorType: entry.initiatorType,
          durationMs: Number(entry.duration?.toFixed?.(2) || 0),
          transferSize: entry.transferSize,
          encodedBodySize: entry.encodedBodySize,
          decodedBodySize: entry.decodedBodySize,
          nextHopProtocol: entry.nextHopProtocol,
        },
      });
    });
  });
  observer.observe({ type: "resource", buffered: true });
};

export const installClientLogging = () => {
  if (installed || typeof window === "undefined") {
    return;
  }
  installed = true;
  originalFetch =
    typeof window.fetch === "function"
      ? window.fetch.bind(window)
      : originalFetch;

  if (CAPTURE_CONSOLE_LOGS) {
    installConsoleLogging();
  }
  if (CAPTURE_BROWSER_NETWORK) {
    installFetchLogging();
    installXhrLogging();
  }
  installNavigationLogging();
  if (CAPTURE_DOM_EVENTS) {
    installDomEventLogging();
  }
  if (CAPTURE_RESOURCE_TIMING) {
    installResourceTimingLogging();
  }

  window.addEventListener("error", (event) => {
    if (
      typeof event.message === "string" &&
      event.message.includes("ResizeObserver loop completed")
    ) {
      return;
    }
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
