const BASE_WITH_API_PREFIX = "https://demo.example/api";
const BASE_WITHOUT_API_PREFIX = "https://demo.example";

const loadApiModule = (baseUrl) => {
  process.env.REACT_APP_API_BASE_URL = baseUrl;
  process.env.REACT_APP_SERVER_PROTOCOL = "https";
  process.env.REACT_APP_SERVER_URL = "demo.example";

  const apiClientMock = {
    get: jest.fn(),
    post: jest.fn(),
    patch: jest.fn(),
    delete: jest.fn(),
    put: jest.fn(),
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
  };

  const axiosMock = {
    create: jest.fn(() => apiClientMock),
    get: jest.fn(),
    post: jest.fn(),
    patch: jest.fn(),
    delete: jest.fn(),
    put: jest.fn(),
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
  };

  jest.resetModules();
  jest.doMock("axios", () => axiosMock);
  jest.doMock("./logging/appEventLog", () => ({
    logClientEvent: jest.fn(),
  }));

  const api = require("./api");
  return { api, apiClientMock, axiosMock };
};

describe("api canonicalization", () => {
  afterEach(() => {
    delete process.env.REACT_APP_API_BASE_URL;
    jest.clearAllMocks();
  });

  it("strips legacy workflow prefix when base URL already ends with /api", async () => {
    const { api, apiClientMock } = loadApiModule(BASE_WITH_API_PREFIX);
    apiClientMock.get.mockResolvedValue({ data: { id: 42 } });

    await api.getCurrentWorkflow();

    expect(apiClientMock.get).toHaveBeenCalledWith("/workflows/current");
  });

  it("keeps /api/workflows path when base URL does not end with /api", async () => {
    const { api, apiClientMock } = loadApiModule(BASE_WITHOUT_API_PREFIX);
    apiClientMock.get.mockResolvedValue({ data: { id: 42 } });

    await api.getCurrentWorkflow();

    expect(apiClientMock.get).toHaveBeenCalledWith("/api/workflows/current");
  });

  it("canonicalizes files-style prefixed paths with query strings", () => {
    const { api } = loadApiModule(BASE_WITH_API_PREFIX);

    const url = api.buildApiUrl("/api/files?parent=root");

    expect(url).toBe("https://demo.example/api/files?parent=root");
  });

  it("requests structured Problem Details responses", () => {
    const { axiosMock } = loadApiModule(BASE_WITH_API_PREFIX);

    expect(axiosMock.create).toHaveBeenCalledWith(
      expect.objectContaining({
        headers: {
          Accept: "application/json, application/problem+json",
        },
      }),
    );
  });

  it("canonicalizes training approval/action paths for base URLs with /api/workflows", () => {
    const { api, apiClientMock } = loadApiModule(
      "https://demo.example/api/workflows",
    );
    apiClientMock.post.mockResolvedValue({ data: {} });

    api.approveAgentAction(99, 123);
    expect(apiClientMock.post).toHaveBeenNthCalledWith(
      1,
      "/99/agent-actions/123/approve",
      undefined,
    );

    api.runWorkflowCommand(99, 321);
    expect(apiClientMock.post).toHaveBeenNthCalledWith(
      2,
      "/99/commands/321/run",
    );
  });

  it("uses canonical durable operation list and cancellation paths", async () => {
    const { api, apiClientMock } = loadApiModule(BASE_WITH_API_PREFIX);
    apiClientMock.get.mockResolvedValue({ data: [] });
    apiClientMock.post.mockResolvedValue({
      data: { id: 8, status: "cancelled" },
    });

    await api.listWorkflowOperations(42, { limit: 6 });
    expect(apiClientMock.get).toHaveBeenCalledWith("/workflows/42/operations", {
      params: { limit: 6 },
    });

    await api.cancelWorkflowOperation(42, 8, "No longer needed");
    expect(apiClientMock.post).toHaveBeenCalledWith(
      "/workflows/42/operations/8/cancel",
      { reason: "No longer needed" },
    );
  });
});
