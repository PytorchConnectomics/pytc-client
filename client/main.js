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
      nodeIntegration: true,
      contextIsolation: false,
      webSecurity: false,
      allowRunningInsecureContent: true,
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
      label: "Views",
      submenu: [
        {
          label: "Change Views",
          click: () => {
            if (mainWindow) {
              mainWindow.webContents.send("change-views");
            }
          },
        },
        { type: "separator" },
        {
          label: "File Management",
          type: "checkbox",
          checked: true,
          enabled: false, // Always on
        },
        {
          label: "Visualization",
          type: "checkbox",
          checked: false,
          click: (menuItem) =>
            mainWindow.webContents.send(
              "toggle-tab",
              "visualization",
              menuItem.checked,
            ),
        },
        {
          label: "Model Training",
          type: "checkbox",
          checked: false,
          click: (menuItem) =>
            mainWindow.webContents.send(
              "toggle-tab",
              "training",
              menuItem.checked,
            ),
        },
        {
          label: "Model Inference",
          type: "checkbox",
          checked: false,
          click: (menuItem) =>
            mainWindow.webContents.send(
              "toggle-tab",
              "inference",
              menuItem.checked,
            ),
        },
        {
          label: "Tensorboard",
          type: "checkbox",
          checked: false,
          click: (menuItem) =>
            mainWindow.webContents.send(
              "toggle-tab",
              "monitoring",
              menuItem.checked,
            ),
        },
        {
          label: "SynAnno",
          type: "checkbox",
          checked: false,
          click: (menuItem) =>
            mainWindow.webContents.send(
              "toggle-tab",
              "synanno",
              menuItem.checked,
            ),
        },
        {
          label: "Mask Proofreading",
          type: "checkbox",
          checked: false,
          click: (menuItem) =>
            mainWindow.webContents.send(
              "toggle-tab",
              "mask-proofreading",
              menuItem.checked,
            ),
        },
      ],
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
