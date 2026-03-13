import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";
import { message, Spin } from "antd";
import { getPMData, savePMData, resetPMData } from "../api";

// ── Context ───────────────────────────────────────────────────────────────────

const ProjectManagerContext = createContext(null);

export function useProjectManager() {
    const ctx = useContext(ProjectManagerContext);
    if (!ctx) throw new Error("useProjectManager must be used inside <ProjectManagerProvider>");
    return ctx;
}

// ── Provider ──────────────────────────────────────────────────────────────────

const DEBOUNCE_MS = 800;

export function ProjectManagerProvider({ children }) {
    const [pmState, setPmState] = useState(null);  // null = not yet loaded
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const debounceRef = useRef(null);

    // ── Fetch on mount ────────────────────────────────────────────────────────
    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        getPMData()
            .then((data) => {
                if (!cancelled) setPmState(data);
            })
            .catch((err) => {
                if (!cancelled) {
                    console.error("[PM] Failed to load data:", err);
                    message.error("Failed to load Project Manager data from server.");
                }
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => { cancelled = true; };
    }, []);

    // ── Debounced server save (called internally after every state mutation) ──
    const _scheduleSave = useCallback((nextState) => {
        if (debounceRef.current) clearTimeout(debounceRef.current);
        debounceRef.current = setTimeout(async () => {
            setSaving(true);
            try {
                await savePMData(nextState);
                message.success({ content: "Changes saved.", key: "pm-save", duration: 1.5 });
            } catch (err) {
                console.error("[PM] Save failed:", err);
                message.error({ content: "Failed to save changes to server.", key: "pm-save" });
            } finally {
                setSaving(false);
            }
        }, DEBOUNCE_MS);
    }, []);

    // ── Public state-mutators ─────────────────────────────────────────────────
    const updateState = useCallback((patch) => {
        setPmState((prev) => {
            const next = { ...prev, ...patch };
            _scheduleSave(next);
            return next;
        });
    }, [_scheduleSave]);

    const resetData = useCallback(async () => {
        setLoading(true);
        try {
            const seed = await resetPMData();
            setPmState(seed);
            message.success("Reset to default data.");
        } catch (err) {
            console.error("[PM] Reset failed:", err);
            message.error("Failed to reset data on server.");
        } finally {
            setLoading(false);
        }
    }, []);

    // ── Derived convenience setters (keep the API ergonomic for sub-views) ────
    const setQuotaData = useCallback((v) => updateState({ quota_data: v }), [updateState]);
    const setProofreaderData = useCallback((v) => updateState({ proofreader_data: v }), [updateState]);
    const setThroughputData = useCallback((v) => updateState({ throughput_data: v }), [updateState]);
    const setMsgPreview = useCallback((v) => updateState({ msg_preview: v }), [updateState]);

    // ── Loading gate ──────────────────────────────────────────────────────────
    if (loading && pmState === null) {
        return (
            <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100%", padding: 48 }}>
                <Spin size="large" tip="Loading Project Manager data…" />
            </div>
        );
    }

    return (
        <ProjectManagerContext.Provider
            value={{
                // Raw state slices
                quotaData: pmState?.quota_data ?? [],
                proofreaderData: pmState?.proofreader_data ?? [],
                throughputData: pmState?.throughput_data ?? [],
                datasets: pmState?.datasets ?? [],
                milestones: pmState?.milestones ?? [],
                cumulativeData: pmState?.cumulative_data ?? [],
                cumulativeTarget: pmState?.cumulative_target ?? [],
                atRisk: pmState?.at_risk ?? [],
                upcomingMilestones: pmState?.upcoming_milestones ?? [],
                msgPreview: pmState?.msg_preview ?? "",
                // Status flags
                loading,
                saving,
                // Setters
                setQuotaData,
                setProofreaderData,
                setThroughputData,
                setMsgPreview,
                // Actions
                resetData,
            }}
        >
            {children}
        </ProjectManagerContext.Provider>
    );
}
