class SliceRequestManager {
  constructor() {
    this.pendingByKey = new Map();
    this.pendingByLane = new Map();
    this.laneVersion = new Map();
  }

  _laneKey(lane) {
    return lane || "__default__";
  }

  _nextLaneVersion(lane) {
    const laneKey = this._laneKey(lane);
    const next = (this.laneVersion.get(laneKey) || 0) + 1;
    this.laneVersion.set(laneKey, next);
    return next;
  }

  cancelLane(lane, keepKey = null) {
    const laneKey = this._laneKey(lane);
    const laneEntries = this.pendingByLane.get(laneKey);
    if (!laneEntries) return;
    laneEntries.forEach((entry, key) => {
      if (keepKey && key === keepKey) return;
      entry.controller.abort();
      this.pendingByKey.delete(key);
      laneEntries.delete(key);
    });
    if (laneEntries.size === 0) {
      this.pendingByLane.delete(laneKey);
    }
  }

  async run({ key, lane, exec, reuse = true }) {
    if (!key || typeof exec !== "function") {
      throw new Error("SliceRequestManager.run requires key and exec");
    }

    const existing = this.pendingByKey.get(key);
    if (reuse && existing) {
      return existing.promise;
    }

    const laneKey = this._laneKey(lane);
    const laneVersion = this._nextLaneVersion(lane);
    this.cancelLane(laneKey, key);

    const controller = new AbortController();
    const laneEntries = this.pendingByLane.get(laneKey) || new Map();
    this.pendingByLane.set(laneKey, laneEntries);

    const promise = Promise.resolve()
      .then(() => exec(controller.signal))
      .then((result) => {
        if (this.laneVersion.get(laneKey) !== laneVersion) {
          const stale = new Error("stale-request");
          stale.name = "AbortError";
          throw stale;
        }
        return result;
      })
      .finally(() => {
        const active = this.pendingByKey.get(key);
        if (active && active.promise === promise) {
          this.pendingByKey.delete(key);
        }
        const laneMap = this.pendingByLane.get(laneKey);
        if (laneMap) {
          const activeInLane = laneMap.get(key);
          if (activeInLane && activeInLane.promise === promise) {
            laneMap.delete(key);
          }
          if (laneMap.size === 0) {
            this.pendingByLane.delete(laneKey);
          }
        }
      });

    const entry = { controller, promise, lane: laneKey, laneVersion };
    this.pendingByKey.set(key, entry);
    laneEntries.set(key, entry);

    return promise;
  }

  clear() {
    this.pendingByKey.forEach((entry) => entry.controller.abort());
    this.pendingByKey.clear();
    this.pendingByLane.clear();
    this.laneVersion.clear();
  }
}

export default SliceRequestManager;
