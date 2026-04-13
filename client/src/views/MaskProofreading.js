import React, { useState } from "react";
import EHTool from "./EHTool";
import { useWorkflow } from "../contexts/WorkflowContext";

function MaskProofreading() {
  const [ehToolSession, setEhToolSession] = useState(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const workflowContext = useWorkflow();
  const workflowId = workflowContext?.workflow?.id ?? null;

  return (
    <div style={{ height: "100%", overflow: "hidden" }}>
      <EHTool
        refreshTrigger={refreshTrigger}
        savedSessionId={ehToolSession}
        workflowId={workflowId}
        onSessionChange={setEhToolSession}
        onStartProofreading={() => {
          // This prop is now nominally used to trigger internal modal
          setRefreshTrigger((prev) => prev + 1);
        }}
      />
    </div>
  );
}

export default MaskProofreading;
