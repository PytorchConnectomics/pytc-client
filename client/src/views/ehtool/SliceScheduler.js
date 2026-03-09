class SliceScheduler {
  constructor(options = {}) {
    this.queues = {
      interactive: [],
      nearby: [],
      background: [],
    };
    this.pendingByKey = new Map();
    this.latestScopeVersion = new Map();
    this.runningByLane = {
      interactive: 0,
      nearby: 0,
      background: 0,
    };
    this.concurrency = {
      interactive: options.interactiveConcurrency ?? 1,
      nearby: options.nearbyConcurrency ?? 1,
      background: options.backgroundConcurrency ?? 1,
    };
    this.laneOrder = ["interactive", "nearby", "background"];
    this.flushScheduled = false;
  }

  _nextScopeVersion(scope) {
    if (!scope) return null;
    const next = (this.latestScopeVersion.get(scope) || 0) + 1;
    this.latestScopeVersion.set(scope, next);
    return next;
  }

  _dropQueuedForScope(scope, keepKey = null) {
    if (!scope) return;
    this.pendingByKey.forEach((task, taskKey) => {
      if (task.scope !== scope) return;
      if (keepKey && taskKey === keepKey) return;
      task.controller.abort();
      this.pendingByKey.delete(taskKey);
      task.reject(this._abortError("dropped-by-scope"));
    });
    this.laneOrder.forEach((lane) => {
      const queue = this.queues[lane];
      this.queues[lane] = queue.filter((task) => {
        if (task.scope !== scope) return true;
        if (keepKey && task.key === keepKey) return true;
        return false;
      });
    });
  }

  _abortError(message = "aborted") {
    const error = new Error(message);
    error.name = "AbortError";
    return error;
  }

  _scheduleFlush() {
    if (this.flushScheduled) return;
    this.flushScheduled = true;
    Promise.resolve().then(() => {
      this.flushScheduled = false;
      this._flush();
    });
  }

  _flush() {
    this.laneOrder.forEach((lane) => {
      while (this.runningByLane[lane] < this.concurrency[lane]) {
        const task = this.queues[lane].shift();
        if (!task) break;
        if (task.controller.signal.aborted) {
          this.pendingByKey.delete(task.key);
          task.reject(this._abortError("aborted-before-run"));
          continue;
        }
        this.runningByLane[lane] += 1;
        this._runTask(task, lane);
      }
    });
  }

  _runTask(task, lane) {
    Promise.resolve()
      .then(() => task.exec(task.controller.signal))
      .then((result) => {
        if (task.scope) {
          const latest = this.latestScopeVersion.get(task.scope);
          if (latest !== task.scopeVersion) {
            task.reject(this._abortError("stale-request"));
            return;
          }
        }
        task.resolve(result);
      })
      .catch((error) => {
        task.reject(error);
      })
      .finally(() => {
        this.runningByLane[lane] = Math.max(0, this.runningByLane[lane] - 1);
        const active = this.pendingByKey.get(task.key);
        if (active && active.promise === task.promise) {
          this.pendingByKey.delete(task.key);
        }
        this._flush();
      });
  }

  run({
    key,
    lane = "interactive",
    scope = null,
    priority = 0,
    reuse = true,
    exec,
  }) {
    if (!key || typeof exec !== "function") {
      throw new Error("SliceScheduler.run requires key and exec");
    }
    if (!this.queues[lane]) {
      throw new Error(`Unknown scheduler lane: ${lane}`);
    }

    const existing = this.pendingByKey.get(key);
    if (reuse && existing) {
      return existing.promise;
    }

    const scopeVersion = this._nextScopeVersion(scope);
    if (scope) {
      this._dropQueuedForScope(scope, key);
    }

    const controller = new AbortController();
    let resolveTask = () => {};
    let rejectTask = () => {};
    const promise = new Promise((resolve, reject) => {
      resolveTask = resolve;
      rejectTask = reject;
    });

    const task = {
      key,
      lane,
      scope,
      scopeVersion,
      priority,
      controller,
      exec,
      resolve: resolveTask,
      reject: rejectTask,
      promise,
    };

    this.pendingByKey.set(key, task);
    const queue = this.queues[lane];
    const insertAt = queue.findIndex((item) => (item.priority || 0) < priority);
    if (insertAt === -1) queue.push(task);
    else queue.splice(insertAt, 0, task);

    this._scheduleFlush();
    return promise;
  }

  cancelLane(lane) {
    if (!this.queues[lane]) return;
    this.queues[lane].forEach((task) => {
      task.controller.abort();
      this.pendingByKey.delete(task.key);
      task.reject(this._abortError("lane-cancelled"));
    });
    this.queues[lane] = [];
  }

  clear() {
    this.laneOrder.forEach((lane) => {
      this.cancelLane(lane);
    });
    this.pendingByKey.forEach((task) => {
      task.controller.abort();
      task.reject(this._abortError("scheduler-cleared"));
    });
    this.pendingByKey.clear();
    this.latestScopeVersion.clear();
  }
}

export default SliceScheduler;
