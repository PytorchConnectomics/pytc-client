jest.mock("antd", () => ({
  message: {
    error: jest.fn(),
  },
}));

jest.mock("axios", () => ({
  create: jest.fn((config) => ({ defaults: config })),
}));

describe("apiClient", () => {
  it("does not send guest-mode requests as credentialed CORS requests", () => {
    let apiClient;

    jest.isolateModules(() => {
      ({ apiClient } = require("./api"));
    });

    expect(apiClient.defaults.withCredentials).toBe(false);
  });
});
