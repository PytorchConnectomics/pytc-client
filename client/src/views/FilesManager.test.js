import React from "react";
import { render, waitFor } from "@testing-library/react";

import FilesManager from "./FilesManager";
import { AppContext } from "../contexts/GlobalContext";
import { apiClient } from "../api";

jest.mock("../api", () => ({
  apiClient: {
    defaults: { baseURL: "http://localhost:4242" },
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
  },
}));

jest.mock("../electronApi", () => ({
  openLocalFile: jest.fn(),
  revealInFinder: jest.fn(),
}));

jest.mock("../components/FileTreeSidebar", () => () => null);

jest.mock("@ant-design/icons", () => {
  const Icon = () => <span />;
  return {
    FolderFilled: Icon,
    FolderOpenOutlined: Icon,
    FileOutlined: Icon,
    FileTextOutlined: Icon,
    ArrowLeftOutlined: Icon,
    AppstoreOutlined: Icon,
    BarsOutlined: Icon,
    UploadOutlined: Icon,
    EyeOutlined: Icon,
    LayoutOutlined: Icon,
    MoreOutlined: Icon,
    DeleteOutlined: Icon,
  };
});

jest.mock("antd", () => {
  const React = require("react");

  const Button = ({ children, ...props }) => (
    <button {...props}>{children}</button>
  );
  const Dropdown = ({ children }) => <div>{children}</div>;
  const Input = React.forwardRef((props, ref) => (
    <input ref={ref} {...props} />
  ));
  const Menu = ({ items = [], onClick }) => (
    <div>
      {items.map((item) =>
        item.type === "divider" ? null : (
          <button
            key={item.key}
            onClick={() => onClick?.({ key: item.key })}
            type="button"
          >
            {item.label}
          </button>
        ),
      )}
    </div>
  );
  const Breadcrumb = ({ children }) => <div>{children}</div>;
  Breadcrumb.Item = ({ children, onClick }) => (
    <button onClick={onClick} type="button">
      {children}
    </button>
  );
  const Modal = ({ children, open }) => (open ? <div>{children}</div> : null);
  Modal.confirm = jest.fn();

  return {
    Button,
    Dropdown,
    Input,
    Modal,
    Menu,
    Breadcrumb,
    Empty: ({ description }) => <div>{description}</div>,
    Image: ({ alt }) => <img alt={alt} />,
    Spin: () => <div>Loading</div>,
    message: {
      error: jest.fn(),
      success: jest.fn(),
      warning: jest.fn(),
      info: jest.fn(),
    },
  };
});

describe("FilesManager", () => {
  it("loads root-level files with a parent-scoped request on initial render", async () => {
    apiClient.get.mockResolvedValue({ data: [] });

    render(
      <AppContext.Provider value={{ resetFileState: jest.fn() }}>
        <FilesManager />
      </AppContext.Provider>,
    );

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith("/files", {
        params: { parent: "root" },
      });
    });

    expect(apiClient.get).not.toHaveBeenCalledWith("/files");
  });
});
