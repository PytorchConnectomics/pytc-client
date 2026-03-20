function getElectronAPI() {
  if (typeof window === "undefined") {
    return null;
  }

  return window.electronAPI || null;
}

export function isElectronAvailable() {
  return Boolean(getElectronAPI()?.isElectron);
}

export function openLocalFile(options = {}) {
  const api = getElectronAPI();
  if (!api) {
    return Promise.resolve(null);
  }
  return api.openLocalFile(options);
}

export function revealInFinder(targetPath) {
  const api = getElectronAPI();
  if (!api) {
    return Promise.resolve(null);
  }
  return api.revealInFinder(targetPath);
}

export function onToggleTab(listener) {
  const api = getElectronAPI();
  if (!api) {
    return () => {};
  }
  return api.onToggleTab(listener);
}

export function onChangeViews(listener) {
  const api = getElectronAPI();
  if (!api) {
    return () => {};
  }
  return api.onChangeViews(listener);
}
