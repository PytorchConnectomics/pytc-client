const { contextBridge, ipcRenderer } = require("electron");

function subscribe(channel) {
  return (listener) => {
    if (typeof listener !== "function") {
      return () => {};
    }

    const wrappedListener = (_event, ...args) => listener(...args);
    ipcRenderer.on(channel, wrappedListener);

    return () => {
      ipcRenderer.removeListener(channel, wrappedListener);
    };
  };
}

contextBridge.exposeInMainWorld("electronAPI", {
  isElectron: true,
  openLocalFile: (options = {}) => ipcRenderer.invoke("open-local-file", options),
  revealInFinder: (targetPath) =>
    ipcRenderer.invoke("reveal-in-finder", targetPath),
  onToggleTab: subscribe("toggle-tab"),
  onChangeViews: subscribe("change-views"),
});
