const path = require("path");
const url = require("url");
const {
  app,
  BrowserWindow,
  ipcMain,
  dialog,
  Menu,
  screen,
  shell,
} = require("electron");

let mainWindow;

function createWindow() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;
  mainWindow = new BrowserWindow({
    width,
    height,
    icon: path.join(__dirname, "public", "favicon.ico"),
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
      label: "Electron",
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
