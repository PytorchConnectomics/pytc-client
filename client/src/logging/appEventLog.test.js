const loadAppEventLogModule = (baseUrl) => {
  const originalFetch = window.fetch;
  const fetchMock = jest.fn().mockResolvedValue({ ok: true });
  window.fetch = fetchMock;
  process.env.REACT_APP_API_BASE_URL = baseUrl;

  jest.resetModules();
  const appEventLog = require("./appEventLog");

  return { appEventLog, fetchMock, originalFetch };
};

describe("appEventLog canonicalization", () => {
  let originalFetch;

  beforeEach(() => {
    originalFetch = window.fetch;
  });

  afterEach(() => {
    delete process.env.REACT_APP_API_BASE_URL;
    if (originalFetch) {
      window.fetch = originalFetch;
    }
    jest.clearAllMocks();
  });

  it("posts logging events to /app/log-event when base URL already has /api", async () => {
    const { appEventLog, fetchMock } = loadAppEventLogModule(
      "https://demo.example/api",
    );

    appEventLog.logClientEvent("api_test_event", {
      message: "from test",
      level: "INFO",
    });

    await Promise.resolve();

    expect(fetchMock).toHaveBeenCalledWith(
      "https://demo.example/api/app/log-event",
      expect.objectContaining({
        method: "POST",
      }),
    );
  });

  it("posts logging events to the app log endpoint on the configured base", async () => {
    const { appEventLog, fetchMock } = loadAppEventLogModule(
      "https://demo.example",
    );

    appEventLog.logClientEvent("api_test_event", {
      message: "from test",
      level: "INFO",
    });

    await Promise.resolve();

    expect(fetchMock).toHaveBeenCalledWith(
      "https://demo.example/app/log-event",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
