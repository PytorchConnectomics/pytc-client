function getElectronAPI() {
  if (typeof window === "undefined") {
    return null;
  }

  return window.electronAPI || null;
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
