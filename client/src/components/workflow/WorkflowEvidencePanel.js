import React, { useMemo, useState } from "react";
import { Button, Card, Empty, Input, Space, Tag, Typography } from "antd";
import {
  computeWorkflowEvaluationResult,
  exportWorkflowBundle,
} from "../../api";
import { useWorkflow } from "../../contexts/WorkflowContext";

const { Text } = Typography;

const METRIC_ROWS = [
  { key: "dice", label: "Dice", direction: "higher" },
  { key: "iou", label: "IoU", direction: "higher" },
  { key: "voxel_accuracy", label: "Voxel accuracy", direction: "higher" },
  { key: "adapted_rand_error", label: "Adapted Rand error", direction: "lower" },
  { key: "vi_total", label: "VI total", direction: "lower" },
];

const EMPTY_ARRAY = [];

function latestByCreatedAt(items = []) {
  return [...items].sort((left, right) => {
    const leftTime = new Date(left.created_at || 0).getTime();
    const rightTime = new Date(right.created_at || 0).getTime();
    if (leftTime !== rightTime) return rightTime - leftTime;
    return (right.id || 0) - (left.id || 0);
  })[0] || null;
}

function normalizeText(value) {
  return String(value || "").toLowerCase();
}

function findArtifactByPath(artifacts, path) {
  if (!path) return null;
  return artifacts.find((artifact) => artifact.path === path) || null;
}

function findArtifactByHints(artifacts, hints) {
  return (
    artifacts.find((artifact) => {
      const haystack = [
        artifact.artifact_type,
        artifact.role,
        artifact.name,
        artifact.path,
        artifact.metadata?.source_payload_key,
      ]
        .map(normalizeText)
        .join(" ");
      return hints.some((hint) => haystack.includes(hint));
    }) || null
  );
}

function formatMetric(value, { signed = false } = {}) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value !== "number") return String(value);
  const rounded = Math.abs(value) >= 10 ? value.toFixed(2) : value.toFixed(4);
  const trimmed = rounded.replace(/\.?0+$/, "");
  return signed && value > 0 ? `+${trimmed}` : trimmed;
}

function formatPath(path) {
  if (!path) return "Not recorded";
  return path;
}

function formatShortPath(path) {
  if (!path) return "Not selected";
  const parts = String(path).split(/[\\/]+/).filter(Boolean);
  if (parts.length <= 2) return parts.join("/");
  return parts.slice(-2).join("/");
}

function statusForPath(artifacts, path) {
  if (!path) return { label: "Needed", color: "red" };
  const artifact = findArtifactByPath(artifacts, path);
  if (!artifact) return { label: "Selected", color: "default" };
  return artifact.exists
    ? { label: "Ready", color: "green" }
    : { label: "Can't find file", color: "orange" };
}

function compactObject(value) {
  return Object.fromEntries(
    Object.entries(value).filter(([, entry]) => entry !== undefined && entry !== null && entry !== ""),
  );
}

function summarizeEvidence({
  workflow,
  artifacts,
  modelRuns,
  correctionSets,
  evaluationResults,
}) {
  const latestEvaluation = latestByCreatedAt(evaluationResults);
  const latestCorrection = latestByCreatedAt(correctionSets);
  const completedInferenceRuns = modelRuns.filter(
    (run) =>
      run.run_type === "inference" &&
      run.status === "completed" &&
      run.output_path,
  );
  const baselineRun = completedInferenceRuns[0] || null;
  const candidateRun =
    completedInferenceRuns.length > 1
      ? completedInferenceRuns[completedInferenceRuns.length - 1]
      : null;
  const inferenceArtifacts = artifacts.filter(
    (artifact) => artifact.artifact_type === "inference_output",
  );
  const correctionArtifacts = artifacts.filter(
    (artifact) => artifact.artifact_type === "correction_set",
  );
  const labelArtifacts = artifacts.filter((artifact) =>
    ["label_volume", "mask_volume", "dataset"].includes(artifact.artifact_type),
  );
  const baselineArtifact = findArtifactByHints(inferenceArtifacts, [
    "baseline",
    "initial",
  ]);
  const candidateArtifact = findArtifactByHints(inferenceArtifacts, [
    "candidate",
    "after",
    "result_xy",
  ]);
  const correctedArtifact = findArtifactByHints(correctionArtifacts, [
    "corrected",
    "correction",
  ]);
  const groundTruthArtifact = findArtifactByHints(labelArtifacts, [
    "ground",
    "truth",
    "label",
  ]);

  const baselinePath =
    latestEvaluation?.metadata?.baseline_prediction_path ||
    baselineRun?.output_path ||
    baselineArtifact?.path ||
    null;
  const candidatePath =
    latestEvaluation?.metadata?.candidate_prediction_path ||
    candidateRun?.output_path ||
    workflow?.inference_output_path ||
    candidateArtifact?.path ||
    null;
  const correctedPath =
    latestCorrection?.corrected_mask_path ||
    workflow?.corrected_mask_path ||
    correctedArtifact?.path ||
    null;
  const groundTruthPath =
    latestEvaluation?.metadata?.ground_truth_path ||
    workflow?.label_path ||
    workflow?.mask_path ||
    groundTruthArtifact?.path ||
    null;

  return {
    latestEvaluation,
    latestCorrection,
    baselineRun,
    candidateRun,
    baselinePath,
    candidatePath,
    correctedPath,
    groundTruthPath,
  };
}

function parseOptionalInteger(value) {
  if (value === null || value === undefined || value === "") return undefined;
  const parsed = Number.parseInt(String(value), 10);
  return Number.isNaN(parsed) ? undefined : parsed;
}

function getEvaluationOptions(workflow, latestEvaluation, evaluationInputs) {
  const metadata = {
    ...(workflow?.metadata || {}),
    ...(latestEvaluation?.metadata || {}),
  };
  return compactObject({
    baseline_dataset: evaluationInputs.baselineDataset || metadata.baseline_dataset,
    candidate_dataset:
      evaluationInputs.candidateDataset || metadata.candidate_dataset,
    ground_truth_dataset:
      evaluationInputs.groundTruthDataset ||
      metadata.ground_truth_dataset ||
      metadata.label_dataset ||
      metadata.mask_dataset,
    crop: evaluationInputs.crop || metadata.crop || metadata.evaluation_crop,
    baseline_channel: parseOptionalInteger(
      evaluationInputs.baselineChannel || metadata.baseline_channel,
    ),
    candidate_channel: parseOptionalInteger(
      evaluationInputs.candidateChannel || metadata.candidate_channel,
    ),
    ground_truth_channel: parseOptionalInteger(
      evaluationInputs.groundTruthChannel || metadata.ground_truth_channel,
    ),
  });
}

function getMissingEvaluationInputs(evidence) {
  return [
    ["previous result", evidence.baselinePath],
    ["new result", evidence.candidatePath],
    ["reference mask", evidence.groundTruthPath],
  ]
    .filter(([, value]) => !value)
    .map(([label]) => label);
}

function getPipelineSteps({
  workflow,
  artifacts,
  modelRuns,
  modelVersions,
  correctionSets,
  evaluationResults,
  events,
  evidence,
}) {
  const hasSourceVolume = Boolean(
    workflow?.dataset_path ||
      workflow?.image_path ||
      artifacts.some((artifact) =>
        ["dataset", "image_volume"].includes(artifact.artifact_type),
      ),
  );
  const completedTrainingRuns = modelRuns.filter(
    (run) => run.run_type === "training" && run.status === "completed",
  );
  const hasCandidatePrediction = Boolean(
    evidence.candidateRun ||
      (evidence.candidatePath && evidence.candidatePath !== evidence.baselinePath),
  );

  const hasBundleExport = events.some(
    (event) => event.event_type === "workflow.bundle_exported",
  );

  return [
    {
      key: "data",
      label: "Data loaded",
      complete: hasSourceVolume && Boolean(evidence.groundTruthPath),
      detail: hasSourceVolume
        ? "image and reference detected"
        : "choose image and mask",
    },
    {
      key: "baseline",
      label: "First result",
      complete: Boolean(evidence.baselinePath),
      detail: evidence.baselineRun ? `run #${evidence.baselineRun.id}` : "run model",
    },
    {
      key: "proofreading",
      label: "Edits saved",
      complete: Boolean(evidence.correctedPath || correctionSets.length),
      detail: correctionSets.length
        ? `${correctionSets.length} saved edit set(s)`
        : "save or export edits",
    },
    {
      key: "training",
      label: "Training run",
      complete: Boolean(completedTrainingRuns.length || modelVersions.length),
      detail: modelVersions.length
        ? `${modelVersions.length} model version(s)`
        : "train on edits",
    },
    {
      key: "candidate",
      label: "New result",
      complete: hasCandidatePrediction,
      detail: evidence.candidateRun ? `run #${evidence.candidateRun.id}` : "run model again",
    },
    {
      key: "evaluation",
      label: "Improvement check",
      complete: Boolean(evaluationResults.length),
      detail: evaluationResults.length
        ? `${evaluationResults.length} comparison(s)`
        : "compare results",
    },
    {
      key: "bundle",
      label: "Research report",
      complete: hasBundleExport,
      detail: evaluationResults.length ? "ready to export" : "compare first",
    },
  ];
}

function PipelineMap({ steps }) {
  const nextBlocked = steps.find((step) => !step.complete);

  return (
    <div
      style={{
        border: "1px solid var(--seg-border-subtle, #e5e7eb)",
        borderRadius: 10,
        padding: 12,
        background: "#fffdf7",
      }}
    >
      <Space size={8} wrap style={{ marginBottom: 10 }}>
        <Text strong>Loop progress</Text>
        <Tag color={nextBlocked ? "orange" : "green"} style={{ margin: 0 }}>
          {nextBlocked ? `next: ${nextBlocked.label}` : "ready"}
        </Tag>
      </Space>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
          gap: 8,
        }}
      >
        {steps.map((step, index) => (
          <div
            key={step.key}
            style={{
              borderRadius: 10,
              padding: 10,
              border: step.complete ? "1px solid #b7eb8f" : "1px solid #ffe58f",
              background: step.complete ? "#f6ffed" : "#fffbe6",
            }}
          >
            <Text style={{ display: "block", fontSize: 11, fontWeight: 700 }}>
              {index + 1}. {step.label}
            </Text>
            <Text type="secondary" style={{ display: "block", fontSize: 11 }}>
              {step.complete ? "complete" : step.detail}
            </Text>
          </div>
        ))}
      </div>
    </div>
  );
}

function EvidencePathCard({ title, path, status, detail }) {
  return (
    <div
      style={{
        border: "1px solid var(--seg-border-subtle, #e5e7eb)",
        borderRadius: 10,
        padding: 12,
        background: "#fff",
        minWidth: 0,
      }}
    >
      <Space size={6} wrap>
        <Text strong style={{ fontSize: 12 }}>
          {title}
        </Text>
        <Tag color={status.color} style={{ margin: 0 }}>
          {status.label}
        </Tag>
      </Space>
      <div
        style={{
          marginTop: 8,
          fontFamily:
            '"IBM Plex Mono", "SFMono-Regular", Menlo, Monaco, Consolas, monospace',
          fontSize: 11,
          color: path ? "#374151" : "#9ca3af",
          wordBreak: "break-word",
        }}
      >
        {formatPath(path)}
      </div>
      {detail && (
        <Text type="secondary" style={{ display: "block", marginTop: 6, fontSize: 11 }}>
          {detail}
        </Text>
      )}
    </div>
  );
}

function CompactEvidenceRow({ label, path, status }) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "96px auto",
        gap: 8,
        alignItems: "baseline",
        padding: "4px 0",
        borderBottom: "1px solid #f0ece3",
      }}
    >
      <Space size={4}>
        <Tag color={status.color} style={{ margin: 0 }}>
          {status.label}
        </Tag>
      </Space>
      <div style={{ minWidth: 0 }}>
        <Text strong style={{ display: "block", fontSize: 12 }}>
          {label}
        </Text>
        <Text
          type="secondary"
          style={{
            display: "block",
            overflow: "hidden",
            fontSize: 11,
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
          title={path || "Not recorded"}
        >
          {formatShortPath(path)}
        </Text>
      </div>
    </div>
  );
}

function MetricGrid({ evaluation }) {
  const metrics = evaluation?.metrics || {};
  const baseline = metrics.baseline || {};
  const candidate = metrics.candidate || {};
  const delta = metrics.delta || {};
  const rows = METRIC_ROWS.filter(
    (row) =>
      baseline[row.key] !== undefined ||
      candidate[row.key] !== undefined ||
      delta[row.key] !== undefined,
  );

  if (!evaluation || rows.length === 0) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description="No comparison yet"
        style={{ margin: "8px 0" }}
      />
    );
  }

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "minmax(120px, 1.2fr) repeat(3, minmax(72px, 0.8fr)) minmax(86px, 0.8fr)",
        gap: 8,
        alignItems: "center",
        overflowX: "auto",
      }}
    >
      {["Metric", "Previous", "New", "Change", "Goal"].map((label) => (
        <Text key={label} type="secondary" style={{ fontSize: 11, fontWeight: 700 }}>
          {label}
        </Text>
      ))}
      {rows.map((row) => {
        const deltaValue = delta[row.key];
        const improved =
          typeof deltaValue === "number"
            ? row.direction === "higher"
              ? deltaValue >= 0
              : deltaValue <= 0
            : null;
        return (
          <React.Fragment key={row.key}>
            <Text style={{ fontSize: 12 }}>{row.label}</Text>
            <Text style={{ fontSize: 12 }}>{formatMetric(baseline[row.key])}</Text>
            <Text style={{ fontSize: 12 }}>{formatMetric(candidate[row.key])}</Text>
            <Text style={{ fontSize: 12 }}>{formatMetric(deltaValue, { signed: true })}</Text>
            <Tag
              color={improved === null ? "default" : improved ? "green" : "orange"}
              style={{ width: "fit-content", margin: 0 }}
            >
              {row.direction === "higher" ? "higher better" : "lower better"}
            </Tag>
          </React.Fragment>
        );
      })}
    </div>
  );
}

function WorkflowEvidencePanel({ compact = false }) {
  const workflowContext = useWorkflow();
  const workflow = workflowContext?.workflow;
  const events = workflowContext?.events || EMPTY_ARRAY;
  const artifacts = workflowContext?.artifacts || EMPTY_ARRAY;
  const modelRuns = workflowContext?.modelRuns || EMPTY_ARRAY;
  const modelVersions = workflowContext?.modelVersions || EMPTY_ARRAY;
  const correctionSets = workflowContext?.correctionSets || EMPTY_ARRAY;
  const evaluationResults = workflowContext?.evaluationResults || EMPTY_ARRAY;
  const refreshEvidence = workflowContext?.refreshEvidence;
  const refreshEvents = workflowContext?.refreshEvents;
  const [computingEvaluation, setComputingEvaluation] = useState(false);
  const [exportingBundle, setExportingBundle] = useState(false);
  const [showMetricOptions, setShowMetricOptions] = useState(false);
  const [computeError, setComputeError] = useState("");
  const [computeNotice, setComputeNotice] = useState("");
  const [bundleNotice, setBundleNotice] = useState("");
  const [evaluationInputs, setEvaluationInputs] = useState({
    baselineDataset: "",
    candidateDataset: "",
    groundTruthDataset: "",
    crop: "",
    baselineChannel: "",
    candidateChannel: "",
    groundTruthChannel: "",
  });

  const evidence = useMemo(
    () =>
      summarizeEvidence({
        workflow,
        artifacts,
        modelRuns,
        correctionSets,
        evaluationResults,
      }),
    [workflow, artifacts, modelRuns, correctionSets, evaluationResults],
  );

  if (!workflowContext || !workflow?.id) {
    return (
      <Card size={compact ? "small" : "default"} title="Review status">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="No active workflow yet"
        />
      </Card>
    );
  }

  const summary = evidence.latestEvaluation?.metrics?.summary || {};
  const missingEvaluationInputs = getMissingEvaluationInputs(evidence);
  const pipelineSteps = getPipelineSteps({
    workflow,
    artifacts,
    modelRuns,
    modelVersions,
    correctionSets,
    evaluationResults,
    events,
    evidence,
  });
  const canComputeEvaluation = missingEvaluationInputs.length === 0;
  const improved = summary.candidate_improved_dice;
  const statusTag =
    improved === true
      ? { label: "new result improved", color: "green" }
      : improved === false
        ? { label: "no Dice gain", color: "orange" }
        : { label: "not compared yet", color: "default" };

  const handleComputeEvaluation = async () => {
    if (!canComputeEvaluation || computingEvaluation) return;
    setComputingEvaluation(true);
    setComputeError("");
    setComputeNotice("");
    try {
      const result = await computeWorkflowEvaluationResult(
        workflow.id,
        compactObject({
          name: "workflow-before-after-evaluation",
          baseline_prediction_path: evidence.baselinePath,
          candidate_prediction_path: evidence.candidatePath,
          ground_truth_path: evidence.groundTruthPath,
          baseline_run_id: evidence.baselineRun?.id,
          candidate_run_id: evidence.candidateRun?.id,
          metadata: {
            source: "workflow_evidence_panel",
            corrected_mask_path: evidence.correctedPath,
          },
          ...getEvaluationOptions(
            workflow,
            evidence.latestEvaluation,
            evaluationInputs,
          ),
        }),
      );
      setComputeNotice(result?.summary || "Comparison computed.");
      await refreshEvidence?.();
    } catch (error) {
      setComputeError(error.message || "Failed to compute evaluation metrics.");
    } finally {
      setComputingEvaluation(false);
    }
  };

  const handleExportBundle = async () => {
    if (exportingBundle) return;
    setExportingBundle(true);
    setComputeError("");
    setBundleNotice("");
    try {
      const bundle = await exportWorkflowBundle(workflow.id);
      const artifactPaths = bundle?.artifact_paths || [];
      const missingCount = artifactPaths.filter((entry) => !entry.exists).length;
      setBundleNotice(
        `Report exported: ${bundle?.artifacts?.length || 0} files, ${bundle?.model_runs?.length || 0} runs, ${bundle?.evaluation_results?.length || 0} comparisons, ${missingCount} missing paths.`,
      );
      await refreshEvents?.();
    } catch (error) {
      setComputeError(error.message || "Failed to export report bundle.");
    } finally {
      setExportingBundle(false);
    }
  };

  if (compact) {
    const completeEvidenceCount = [
      evidence.baselinePath,
      evidence.candidatePath,
      evidence.correctedPath,
      evidence.groundTruthPath,
    ].filter(Boolean).length;

    return (
      <Card
        size="small"
        title={
          <Space size={6} wrap>
            <span>Review status</span>
            <Tag color={statusTag.color} style={{ margin: 0 }}>
              {statusTag.label}
            </Tag>
            <Tag color={completeEvidenceCount === 4 ? "green" : "gold"} style={{ margin: 0 }}>
              {completeEvidenceCount}/4 ready
            </Tag>
          </Space>
        }
        extra={
          <Button size="small" type="text" onClick={() => refreshEvidence?.()}>
            Refresh
          </Button>
        }
      >
        <Space direction="vertical" size={8} style={{ width: "100%" }}>
          <div>
            <CompactEvidenceRow
              label="Previous result"
              path={evidence.baselinePath}
              status={statusForPath(artifacts, evidence.baselinePath)}
            />
            <CompactEvidenceRow
              label="New result"
              path={evidence.candidatePath}
              status={statusForPath(artifacts, evidence.candidatePath)}
            />
            <CompactEvidenceRow
              label="Your edits"
              path={evidence.correctedPath}
              status={statusForPath(artifacts, evidence.correctedPath)}
            />
            <CompactEvidenceRow
              label="Reference mask"
              path={evidence.groundTruthPath}
              status={statusForPath(artifacts, evidence.groundTruthPath)}
            />
          </div>
          <Space size={6} wrap>
            <Text strong style={{ fontSize: 12 }}>
              Metrics
            </Text>
            {summary.dice_delta !== undefined ? (
              <Tag color={summary.dice_delta >= 0 ? "green" : "orange"}>
                Dice {formatMetric(summary.dice_delta, { signed: true })}
              </Tag>
            ) : (
              <Text type="secondary" style={{ fontSize: 12 }}>
                Not computed
              </Text>
            )}
          </Space>
          {!canComputeEvaluation && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              Needed: {missingEvaluationInputs.join(", ")}
            </Text>
          )}
        </Space>
      </Card>
    );
  }

  return (
    <Card
      size="default"
      title={
        <Space size={8} wrap>
          <span>Review status</span>
          <Tag color={statusTag.color} style={{ margin: 0 }}>
            {statusTag.label}
          </Tag>
        </Space>
      }
      extra={
        <Space size={8} wrap>
          <Button
            size="small"
            onClick={handleComputeEvaluation}
            disabled={!canComputeEvaluation || computingEvaluation}
            loading={computingEvaluation}
          >
            Compare results
          </Button>
          <Button size="small" onClick={() => refreshEvidence?.()}>
            Refresh
          </Button>
          <Button
            size="small"
            onClick={handleExportBundle}
            loading={exportingBundle}
          >
            Export report
          </Button>
        </Space>
      }
    >
      <Space direction="vertical" size={12} style={{ width: "100%" }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: compact
              ? "1fr"
              : "repeat(auto-fit, minmax(220px, 1fr))",
            gap: 10,
          }}
        >
          <EvidencePathCard
            title="Previous result"
            path={evidence.baselinePath}
            status={statusForPath(artifacts, evidence.baselinePath)}
            detail={
              evidence.baselineRun
                ? `run #${evidence.baselineRun.id}`
                : "first model output"
            }
          />
          <EvidencePathCard
            title="New result"
            path={evidence.candidatePath}
            status={statusForPath(artifacts, evidence.candidatePath)}
            detail={
              evidence.candidateRun
                ? `run #${evidence.candidateRun.id}`
                : "latest model output"
            }
          />
          <EvidencePathCard
            title="Your saved edits"
            path={evidence.correctedPath}
            status={statusForPath(artifacts, evidence.correctedPath)}
            detail={
              evidence.latestCorrection
                ? `${evidence.latestCorrection.edit_count || 0} edits, ${evidence.latestCorrection.region_count || 0} regions`
                : "save or export edits from proofreading"
            }
          />
          <EvidencePathCard
            title="Reference mask"
            path={evidence.groundTruthPath}
            status={statusForPath(artifacts, evidence.groundTruthPath)}
            detail="mask used to check improvement"
          />
        </div>

        {!compact && <PipelineMap steps={pipelineSteps} />}

        <div
          style={{
            border: "1px solid var(--seg-border-subtle, #e5e7eb)",
            borderRadius: 10,
            padding: 12,
            background: "#fbfbfa",
          }}
        >
          {!compact && (
            <div style={{ marginBottom: showMetricOptions ? 12 : 8 }}>
              <Button
                size="small"
                type="text"
                onClick={() => setShowMetricOptions((current) => !current)}
              >
                {showMetricOptions ? "Hide metric options" : "Metric options"}
              </Button>
            </div>
          )}
          {!compact && showMetricOptions && (
            <div
              style={{
                marginBottom: 12,
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
                gap: 8,
              }}
            >
              <Input
                size="small"
                aria-label="Baseline dataset key"
                placeholder="previous result dataset key"
                value={evaluationInputs.baselineDataset}
                onChange={(event) =>
                  setEvaluationInputs((current) => ({
                    ...current,
                    baselineDataset: event.target.value,
                  }))
                }
              />
              <Input
                size="small"
                aria-label="Candidate dataset key"
                placeholder="new result dataset key"
                value={evaluationInputs.candidateDataset}
                onChange={(event) =>
                  setEvaluationInputs((current) => ({
                    ...current,
                    candidateDataset: event.target.value,
                  }))
                }
              />
              <Input
                size="small"
                aria-label="Ground truth dataset key"
                placeholder="reference mask dataset key"
                value={evaluationInputs.groundTruthDataset}
                onChange={(event) =>
                  setEvaluationInputs((current) => ({
                    ...current,
                    groundTruthDataset: event.target.value,
                  }))
                }
              />
              <Input
                size="small"
                aria-label="Evaluation crop"
                placeholder="crop e.g. 0:32,0:256,0:256"
                value={evaluationInputs.crop}
                onChange={(event) =>
                  setEvaluationInputs((current) => ({
                    ...current,
                    crop: event.target.value,
                  }))
                }
              />
              <Input
                size="small"
                aria-label="Baseline channel"
                placeholder="previous result channel"
                value={evaluationInputs.baselineChannel}
                onChange={(event) =>
                  setEvaluationInputs((current) => ({
                    ...current,
                    baselineChannel: event.target.value,
                  }))
                }
              />
              <Input
                size="small"
                aria-label="Candidate channel"
                placeholder="new result channel"
                value={evaluationInputs.candidateChannel}
                onChange={(event) =>
                  setEvaluationInputs((current) => ({
                    ...current,
                    candidateChannel: event.target.value,
                  }))
                }
              />
              <Input
                size="small"
                aria-label="Ground truth channel"
                placeholder="reference mask channel"
                value={evaluationInputs.groundTruthChannel}
                onChange={(event) =>
                  setEvaluationInputs((current) => ({
                    ...current,
                    groundTruthChannel: event.target.value,
                  }))
                }
              />
            </div>
          )}
          <Space size={8} wrap style={{ marginBottom: 8 }}>
            <Text strong>Improvement</Text>
            {summary.dice_delta !== undefined && (
              <Tag color={summary.dice_delta >= 0 ? "green" : "orange"}>
                Dice {formatMetric(summary.dice_delta, { signed: true })}
              </Tag>
            )}
            {summary.iou_delta !== undefined && (
              <Tag color={summary.iou_delta >= 0 ? "green" : "orange"}>
                IoU {formatMetric(summary.iou_delta, { signed: true })}
              </Tag>
            )}
            {summary.voxel_accuracy_delta !== undefined && (
              <Tag color={summary.voxel_accuracy_delta >= 0 ? "green" : "orange"}>
                Accuracy {formatMetric(summary.voxel_accuracy_delta, { signed: true })}
              </Tag>
            )}
          </Space>
          <MetricGrid evaluation={evidence.latestEvaluation} />
          {!canComputeEvaluation && (
            <Text type="secondary" style={{ display: "block", marginTop: 8, fontSize: 12 }}>
              Need {missingEvaluationInputs.join(", ")} before metrics can be
              computed.
            </Text>
          )}
          {computeNotice && (
            <Text style={{ display: "block", marginTop: 8, fontSize: 12, color: "#2f7d32" }}>
              {computeNotice}
            </Text>
          )}
          {bundleNotice && (
            <Text style={{ display: "block", marginTop: 8, fontSize: 12, color: "#256f68" }}>
              {bundleNotice}
            </Text>
          )}
          {computeError && (
            <Text style={{ display: "block", marginTop: 8, fontSize: 12, color: "#b13a2f" }}>
              {computeError}
            </Text>
          )}
        </div>

        {evidence.latestEvaluation ? (
          <div>
            <Text strong style={{ fontSize: 12 }}>
              Latest comparison
            </Text>
            <Text style={{ display: "block", fontSize: 12 }}>
              {evidence.latestEvaluation.summary ||
                evidence.latestEvaluation.name ||
                "Comparison recorded."}
            </Text>
            {evidence.latestEvaluation.report_path && (
              <Text
                type="secondary"
                style={{
                  display: "block",
                  fontSize: 11,
                  wordBreak: "break-word",
                  fontFamily:
                    '"IBM Plex Mono", "SFMono-Regular", Menlo, Monaco, Consolas, monospace',
                }}
              >
                Report: {evidence.latestEvaluation.report_path}
              </Text>
            )}
          </div>
        ) : (
          <Text type="secondary" style={{ fontSize: 12 }}>
            No comparison yet. Register previous and new results, then compare
            them.
          </Text>
        )}
      </Space>
    </Card>
  );
}

export default WorkflowEvidencePanel;
