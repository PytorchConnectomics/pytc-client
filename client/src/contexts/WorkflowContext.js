import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { message } from "antd";
import {
  appendWorkflowEvent,
  approveAgentAction as approveAgentActionApi,
  createAgentAction,
  getCurrentWorkflow,
  getWorkflowHotspots,
  getWorkflowImpactPreview,
  listWorkflowEvents,
  queryWorkflowAgent,
  rejectAgentAction as rejectAgentActionApi,
  updateWorkflow as updateWorkflowApi,
} from "../api";
import { AppContext } from "./GlobalContext";

export const WorkflowContext = createContext(null);

export function useWorkflow() {
  return useContext(WorkflowContext);
}

export function WorkflowProvider({ children }) {
  const appContext = useContext(AppContext);
  const [workflow, setWorkflow] = useState(null);
  const [events, setEvents] = useState([]);
  const [hotspots, setHotspots] = useState([]);
  const [impactPreview, setImpactPreview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastClientEffects, setLastClientEffects] = useState(null);

  const refreshWorkflow = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getCurrentWorkflow();
      setWorkflow(data?.workflow || null);
      setEvents(data?.events || []);
      return data;
    } catch (error) {
      message.error("Failed to load workflow state.");
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshEvents = useCallback(async () => {
    if (!workflow?.id) return [];
    const nextEvents = await listWorkflowEvents(workflow.id);
    setEvents(nextEvents || []);
    return nextEvents || [];
  }, [workflow?.id]);

  const refreshInsights = useCallback(async () => {
    if (!workflow?.id) {
      setHotspots([]);
      setImpactPreview(null);
      return null;
    }
    try {
      const [hotspotData, impactData] = await Promise.all([
        getWorkflowHotspots(workflow.id),
        getWorkflowImpactPreview(workflow.id),
      ]);
      setHotspots(hotspotData?.hotspots || []);
      setImpactPreview(impactData || null);
      return {
        hotspots: hotspotData?.hotspots || [],
        impactPreview: impactData || null,
      };
    } catch (_error) {
      return null;
    }
  }, [workflow?.id]);

  useEffect(() => {
    refreshWorkflow();
  }, [refreshWorkflow]);

  useEffect(() => {
    if (!workflow?.id) {
      setHotspots([]);
      setImpactPreview(null);
      return;
    }
    refreshInsights();
  }, [
    workflow?.id,
    workflow?.stage,
    workflow?.corrected_mask_path,
    events.length,
    refreshInsights,
  ]);

  const updateWorkflow = useCallback(
    async (patch) => {
      if (!workflow?.id) return null;
      const nextWorkflow = await updateWorkflowApi(workflow.id, patch);
      setWorkflow(nextWorkflow);
      return nextWorkflow;
    },
    [workflow?.id],
  );

  const appendEvent = useCallback(
    async (event) => {
      if (!workflow?.id) return null;
      const nextEvent = await appendWorkflowEvent(workflow.id, event);
      setEvents((prev) => [...prev, nextEvent]);
      return nextEvent;
    },
    [workflow?.id],
  );

  const proposeAgentAction = useCallback(
    async (action) => {
      if (!workflow?.id) return null;
      const proposal = await createAgentAction(workflow.id, action);
      await refreshEvents();
      return proposal;
    },
    [workflow?.id, refreshEvents],
  );

  const applyClientEffects = useCallback(
    (effects) => {
      if (!effects) return;
      if (effects.set_training_label_path && appContext?.trainingState) {
        appContext.trainingState.setInputLabel(effects.set_training_label_path);
      }
      setLastClientEffects(effects);
    },
    [appContext],
  );

  const approveAgentAction = useCallback(
    async (eventId) => {
      if (!workflow?.id) return null;
      const result = await approveAgentActionApi(workflow.id, eventId);
      if (result?.workflow) {
        setWorkflow(result.workflow);
      }
      applyClientEffects(result?.client_effects);
      await refreshEvents();
      message.success("Agent proposal approved.");
      return result;
    },
    [workflow?.id, refreshEvents, applyClientEffects],
  );

  const rejectAgentAction = useCallback(
    async (eventId) => {
      if (!workflow?.id) return null;
      const result = await rejectAgentActionApi(workflow.id, eventId);
      await refreshEvents();
      message.info("Agent proposal rejected.");
      return result;
    },
    [workflow?.id, refreshEvents],
  );

  const queryAgent = useCallback(
    async (query) => {
      if (!workflow?.id) return null;
      const result = await queryWorkflowAgent(workflow.id, query);
      if (result?.proposals?.length) {
        await refreshEvents();
      }
      return result;
    },
    [workflow?.id, refreshEvents],
  );

  const consumeClientEffects = useCallback(() => {
    const effects = lastClientEffects;
    setLastClientEffects(null);
    return effects;
  }, [lastClientEffects]);

  return (
    <WorkflowContext.Provider
      value={{
        workflow,
        events,
        hotspots,
        impactPreview,
        loading,
        lastClientEffects,
        refreshWorkflow,
        refreshEvents,
        refreshInsights,
        updateWorkflow,
        appendEvent,
        proposeAgentAction,
        approveAgentAction,
        rejectAgentAction,
        queryAgent,
        consumeClientEffects,
      }}
    >
      {children}
    </WorkflowContext.Provider>
  );
}
