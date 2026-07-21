import React from "react";
import ReactDOM from "react-dom/client";
import { ConfigProvider } from "antd";
import { QueryClientProvider } from "@tanstack/react-query";
import "./index.css";
import App from "./App";
import AppErrorBoundary from "./components/AppErrorBoundary";
import { antdWorkflowTheme } from "./design/workflowDesignSystem";
import { installClientLogging } from "./logging/appEventLog";
import { appQueryClient } from "./queryClient";

installClientLogging();

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <QueryClientProvider client={appQueryClient}>
      <ConfigProvider theme={antdWorkflowTheme}>
        <AppErrorBoundary>
          <App />
        </AppErrorBoundary>
      </ConfigProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
