import React from "react";
import { ArrowLeftOutlined, ReloadOutlined } from "@ant-design/icons";
import { Button, Result, Space, Typography } from "antd";
import { logClientEvent } from "../logging/appEventLog";

const { Text } = Typography;

class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null, errorId: null };
  }

  static getDerivedStateFromError(error) {
    return {
      error,
      errorId: `ui-${Date.now().toString(36)}`,
    };
  }

  componentDidCatch(error, info) {
    logClientEvent("ui_render_failed", {
      level: "ERROR",
      message: error?.message || "The application failed to render",
      source: "AppErrorBoundary",
      data: {
        errorId: this.state.errorId,
        errorName: error?.name,
        componentStack: info?.componentStack,
      },
    });
  }

  retry = () => {
    this.setState({ error: null, errorId: null });
  };

  reload = () => {
    window.location.reload();
  };

  goBack = () => {
    window.history.back();
  };

  render() {
    const { error, errorId } = this.state;
    if (!error) return this.props.children;

    return (
      <main className="app-error-boundary" role="alert">
        <Result
          status="error"
          title="This screen could not be displayed"
          subTitle="Your saved project data is unchanged. Try the screen again or reload the application."
          extra={
            <Space wrap>
              <Button
                type="primary"
                icon={<ReloadOutlined />}
                onClick={this.retry}
              >
                Try again
              </Button>
              <Button icon={<ReloadOutlined />} onClick={this.reload}>
                Reload application
              </Button>
              <Button icon={<ArrowLeftOutlined />} onClick={this.goBack}>
                Go back
              </Button>
            </Space>
          }
        >
          <Text type="secondary">Error reference: {errorId}</Text>
        </Result>
      </main>
    );
  }
}

export default AppErrorBoundary;
