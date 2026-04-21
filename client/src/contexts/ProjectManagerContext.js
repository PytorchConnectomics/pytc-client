import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
} from "react";
import { message, Spin } from "antd";
import {
  getPMConfig,
  getPMData,
  savePMData,
  resetPMData,
  updatePMConfig,
} from "../api";
import { apiClient } from "../api";
import { dataReader } from "../services/data_reader";

// ── Context ───────────────────────────────────────────────────────────────────

const ProjectManagerContext = createContext(null);

export function useProjectManager() {
  const ctx = useContext(ProjectManagerContext);
  if (!ctx)
    throw new Error(
      "useProjectManager must be used inside <ProjectManagerProvider>",
    );
  return ctx;
}

// ── Provider ──────────────────────────────────────────────────────────────────

const DEBOUNCE_MS = 800;

/**
 * ProjectManagerProvider
 *
 * Props:
 *   role         "admin" | "worker"          — current RBAC role
 *   activeWorker  worker key string            — e.g. "alex" (relevant when role=worker)
 */
export function ProjectManagerProvider({ children }) {
  const [pmState, setPmState] = useState(null); // null = not yet loaded
  const [pmConfig, setPmConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [configLoading, setConfigLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [user, setUser] = useState(null); // Authenticated user object
  const debounceRef = useRef(null);

  // ── Session Restoration ──────────────────────────────────────────────────
  useEffect(() => {
    const saved = localStorage.getItem("pm_user");
    if (saved) {
      try {
        setUser(JSON.parse(saved));
      } catch (e) {
        localStorage.removeItem("pm_user");
      }
    }
  }, []);

  const loadPmData = useCallback(async () => {
    const data = await getPMData();
    setPmState(data);
    return data;
  }, []);

  const loadPmConfig = useCallback(async () => {
    const config = await getPMConfig();
    setPmConfig(config);
    return config;
  }, []);

  const refreshPmState = useCallback(async () => {
    setLoading(true);
    try {
      const [data, config] = await Promise.all([loadPmData(), loadPmConfig()]);
      return { data, config };
    } catch (err) {
      console.error("[PM] Failed to load data:", err);
      message.error("Failed to load Project Manager data from server.");
      throw err;
    } finally {
      setLoading(false);
    }
  }, [loadPmConfig, loadPmData]);

  // ── Fetch on mount (always load PM config/seeds) ──────────────────────────
  useEffect(() => {
    let cancelled = false;

    const bootstrap = async () => {
      setLoading(true);
      try {
        const [data, config] = await Promise.all([getPMData(), getPMConfig()]);
        if (!cancelled) {
          setPmState(data);
          setPmConfig(config);
        }
      } catch (err) {
        if (!cancelled) {
          console.error("[PM] Failed to load data:", err);
          message.error("Failed to load Project Manager data from server.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  // ── Auth Actions ──────────────────────────────────────────────────────────
  const login = useCallback(async (username, password) => {
    try {
      const res = await apiClient.post("/api/pm/login", { username, password });
      if (res.data.ok) {
        const userData = res.data.user;
        setUser(userData);
        localStorage.setItem("pm_user", JSON.stringify(userData));
        message.success(`Logged in as ${userData.name}`);
        return true;
      }
    } catch (err) {
      message.error(err.response?.data?.detail || "Login failed");
      return false;
    }
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    localStorage.removeItem("pm_user");
    message.info("Logged out.");
  }, []);

  // ── Debounced server save ─────────────────────────────────────────────────
  const _scheduleSave = useCallback((nextState) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setSaving(true);
      try {
        await savePMData(nextState);
        message.success({
          content: "Changes saved.",
          key: "pm-save",
          duration: 1.5,
        });
      } catch (err) {
        console.error("[PM] Save failed:", err);
        message.error({
          content: "Failed to save changes to server.",
          key: "pm-save",
        });
      } finally {
        setSaving(false);
      }
    }, DEBOUNCE_MS);
  }, []);

  // ── Public state-mutators ─────────────────────────────────────────────────
  const updateState = useCallback(
    (patch) => {
      setPmState((prev) => {
        const next = { ...prev, ...patch };
        _scheduleSave(next);
        return next;
      });
    },
    [_scheduleSave],
  );

  const resetData = useCallback(async () => {
    setLoading(true);
    try {
      const seed = await resetPMData();
      setPmState(seed);
      await loadPmConfig();
      message.success("Started a fresh project.");
    } catch (err) {
      console.error("[PM] Reset failed:", err);
      message.error("Failed to reset data on server.");
    } finally {
      setLoading(false);
    }
  }, [loadPmConfig]);

  const ingestData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.post("/api/pm/data/ingest");
      if (res.data.ok) {
        setPmState(res.data.data);
        message.success(
          `Ingested ${res.data.data.volumes?.length || 0} volumes.`,
        );
      }
    } catch (err) {
      console.error("[PM] Ingestion failed:", err);
      message.error(
        err.response?.data?.detail || "Failed to ingest data from storage.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  const updateProjectConfig = useCallback(
    async (patch) => {
      setConfigLoading(true);
      try {
        const config = await updatePMConfig(patch);
        setPmConfig(config);
        const data = await getPMData();
        setPmState(data);
        message.success("Project source updated.");
        return { config, data };
      } catch (err) {
        console.error("[PM] Config update failed:", err);
        message.error(
          err.response?.data?.detail || "Failed to update project source.",
        );
        throw err;
      } finally {
        setConfigLoading(false);
      }
    },
    [],
  );

  // ── Volume helpers ───────────────────────────────────────────────────────
  const getVolumes = useCallback(async (params = {}) => {
    try {
      return await dataReader.getPooledVolumes(params);
    } catch (err) {
      message.error("Failed to load volumes from server.");
      throw err;
    }
  }, []);

  const updateVolumeStatus = useCallback(async (volumeId, status) => {
    try {
      const res = await dataReader.updateStatus(volumeId, status);
      if (res?.global_progress) {
        setPmState((prev) =>
          prev ? { ...prev, global_progress: res.global_progress } : prev,
        );
      }
      return res;
    } catch (err) {
      message.error("Failed to update volume status.");
      throw err;
    }
  }, []);

  const updateVolumeAssignee = useCallback(async (volumeId, assignee) => {
    try {
      const res = await dataReader.assignVolume(volumeId, assignee);
      if (res?.global_progress) {
        setPmState((prev) =>
          prev ? { ...prev, global_progress: res.global_progress } : prev,
        );
      }
      return res;
    } catch (err) {
      message.error("Failed to update volume assignee.");
      throw err;
    }
  }, []);

  // ── Convenience setters ───────────────────────────────────────────────────
  const setQuotaData = useCallback(
    (v) => updateState({ quota_data: v }),
    [updateState],
  );
  const setProofreaderData = useCallback(
    (v) => updateState({ proofreader_data: v }),
    [updateState],
  );
  const setThroughputData = useCallback(
    (v) => updateState({ throughput_data: v }),
    [updateState],
  );
  const setMsgPreview = useCallback(
    (v) => updateState({ msg_preview: v }),
    [updateState],
  );

  // ── Computed RBAC Values ──────────────────────────────────────────────────
  const isAuthenticated = !!user;
  const role = user?.role || "guest";
  const isAdmin = role === "admin";
  const isWorker = role === "worker";
  const activeWorker = isWorker ? user?.key : null;

  // ── Role-filtered convenience getters ─────────────────────────────────────
  const allQuotaData = pmState?.quota_data ?? [];
  const allProofreaderData = pmState?.proofreader_data ?? [];

  const quotaData = isWorker
    ? allQuotaData.filter((r) => r.worker_key === activeWorker)
    : allQuotaData;
  const proofreaderData = isWorker
    ? allProofreaderData.filter((r) => r.worker_key === activeWorker)
    : allProofreaderData;

  // ── Loading gate ──────────────────────────────────────────────────────────
  if (loading && pmState === null) {
    return (
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          height: "100%",
          padding: 48,
        }}
      >
        <Spin size="large" tip="Loading Project Manager data…" />
      </div>
    );
  }

  return (
    <ProjectManagerContext.Provider
      value={{
        // Auth & RBAC
        user,
        isAuthenticated,
        role,
        activeWorker,
        isAdmin,
        isWorker,
        login,
        logout,

        // State slices
        quotaData,
        proofreaderData,
        allQuotaData,
        allProofreaderData,
        throughputData: pmState?.throughput_data ?? [],
        datasets: pmState?.datasets ?? [],
        milestones: pmState?.milestones ?? [],
        cumulativeData: pmState?.cumulative_data ?? [],
        cumulativeTarget: pmState?.cumulative_target ?? [],
        atRisk: pmState?.at_risk ?? [],
        upcomingMilestones: pmState?.upcoming_milestones ?? [],
        msgPreview: pmState?.msg_preview ?? "",
        globalProgress: pmState?.global_progress ?? {
          total: 0,
          done: 0,
          in_progress: 0,
          todo: 0,
          pct: 0,
          by_worker: {},
        },
        workers: pmState?.workers ?? [],
        pmConfig,
        projectInfo: pmState?.project_info ?? pmConfig?.project_info ?? null,

        // Status
        loading,
        configLoading,
        saving,

        // Setters
        setQuotaData,
        setProofreaderData,
        setThroughputData,
        setMsgPreview,

        // Actions
        resetData,
        ingestData,
        refreshPmState,
        loadPmConfig,
        updateProjectConfig,
        getVolumes,
        updateVolumeStatus,
        updateVolumeAssignee,
      }}
    >
      {children}
    </ProjectManagerContext.Provider>
  );
}
