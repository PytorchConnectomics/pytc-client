const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  isElectron: true,
  openLocalFile: (options = {}) =>
    ipcRenderer.invoke("open-local-file", options),
  revealInFinder: (targetPath) =>
    ipcRenderer.invoke("reveal-in-finder", targetPath),
});
