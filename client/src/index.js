import React from "react";
import ReactDOM from "react-dom/client";
import { ConfigProvider } from "antd";
import "./index.css";
import App from "./App";
import { antdWorkflowTheme } from "./design/workflowDesignSystem";
import { installClientLogging } from "./logging/appEventLog";

installClientLogging();

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <ConfigProvider theme={antdWorkflowTheme}>
      <App />
    </ConfigProvider>
  </React.StrictMode>,
);
