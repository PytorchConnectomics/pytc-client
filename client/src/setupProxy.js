const { createProxyMiddleware } = require("http-proxy-middleware");

module.exports = function (app) {
  if (!process.env.PYTC_DEV_API_TARGET) return;
  // Keep browser requests on one origin; the API and worker remain on loopback.
  app.use("/backend", createProxyMiddleware({
    target: process.env.PYTC_DEV_API_TARGET,
    changeOrigin: true,
    pathRewrite: { "^/backend": "" },
    proxyTimeout: 120000,
    onError(_error, _request, response) {
      response.writeHead(503, { "Content-Type": "application/json" });
      response.end(JSON.stringify({ detail: "The API is offline. Restart the demo services and retry." }));
    },
  }));
};
