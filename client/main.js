const path = require("path");
const url = require("url");
const fs = require("fs");
const {
  app,
  BrowserWindow,
  ipcMain,
  dialog,
  Menu,
  nativeImage,
  screen,
  shell,
} = require("electron");

let mainWindow;
const APP_NAME = "PyTC Client";

app.setName(APP_NAME);
app.setAppUserModelId("bio.seg.pytc-client");

function getAppIconPath() {
  const candidates = [
    path.join(__dirname, "public", "pytc-app-icon.png"),
    path.join(__dirname, "build", "pytc-app-icon.png"),
    path.join(__dirname, "public", "favicon.ico"),
    path.join(__dirname, "build", "favicon.ico"),
  ];
  return candidates.find((candidate) => fs.existsSync(candidate));
}

function loadAppIcon() {
  const iconPath = getAppIconPath();
  if (!iconPath) return undefined;

  const icon = nativeImage.createFromPath(iconPath);
  if (icon.isEmpty()) return undefined;

  if (process.platform === "darwin" && app.dock) {
    app.dock.setIcon(icon);
  }

  return icon;
}

function createWindow() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;
  const appIcon = loadAppIcon();
  mainWindow = new BrowserWindow({
    width,
    height,
    icon: appIcon,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      webSecurity: true,
      allowRunningInsecureContent: false,
    },
  });

  // React UI
  let startUrl;
  if (process.env.ENVIRONMENT === "development") {
    // Dev server
    startUrl = "http://localhost:3000";
  } else {
    // Production build
    startUrl = url.format({
      pathname: path.join(__dirname, "build", "index.html"),
      protocol: "file:",
      slashes: true,
    });
  }
  mainWindow.loadURL(startUrl);

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  createMenu();
}

function createMenu() {
  const template = [
    {
      label: APP_NAME,
      submenu: [{ role: "toggleDevTools" }, { role: "quit" }],
    },
    { role: "editMenu" },
    {
      label: "Edit",
      submenu: [
        { role: "undo" },
        { role: "redo" },
        { type: "separator" },
        { role: "cut" },
        { role: "copy" },
        { role: "paste" },
        { role: "selectAll" },
      ],
    },
    {
      label: "Window",
      submenu: [{ role: "minimize" }, { role: "close" }],
    },
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

ipcMain.handle("open-local-file", async (_event, options = {}) => {
  const properties = options.properties;
  const { canceled, filePaths } = await dialog.showOpenDialog(mainWindow, {
    properties,
  });
  if (canceled) {
    return null;
  } else {
    return filePaths[0];
  }
});

ipcMain.handle("reveal-in-finder", async (_event, targetPath) => {
  if (!targetPath) return null;
  try {
    await shell.showItemInFolder(targetPath);
  } catch (err) {
    return null;
  }
  return true;
});

app.on("ready", createWindow);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (!mainWindow) {
    createWindow();
  }
});
