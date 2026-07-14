// global FileReader
import React, {
  Fragment,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  Button,
  Col,
  Divider,
  message,
  Row,
  Select,
  Slider,
  Space,
  Upload,
} from "antd";
import { UploadOutlined } from "@ant-design/icons";
import yaml from "js-yaml";
import { AppContext } from "../contexts/GlobalContext";
import { YamlContext } from "../contexts/YamlContext";
import {
  getConfigPresets,
  getConfigPresetContent,
  getModelArchitectures,
} from "../api";
import InlineHelpChat from "./InlineHelpChat";
import { findCommonPartOfString } from "../utils";
import {
  applyInputPaths,
  getArchitecturePath,
  getArchitectureValue,
  getSliderPath,
  getSliderValue,
  isArchitectureSupported,
  isSliderSupported,
  setArchitectureValue,
  setSliderValue,
} from "../configSchema";
import { logClientEvent } from "../logging/appEventLog";
import {
  detectConfigDiagnostics,
  summarizeConfigObject,
} from "../logging/configLogSummary";

const PROJECT_CONTEXT =
  "Biomedical image segmentation using PyTorch Connectomics.";

const BASE_CONFIG_TASK_CONTEXT = {
  training: "Model training configuration — Step 2: Base Configuration.",
  inference: "Model inference configuration — Step 2: Base Configuration.",
};

const YamlFileUploader = (props) => {
  const context = useContext(AppContext);
  const YAMLContext = useContext(YamlContext);
  const { type } = props;
  const workflow =
    type === "training" ? context.trainingState : context.inferenceState;
  const { trainingConfig, inferenceConfig, setTrainingConfig, setInferenceConfig } =
    context;
  const {
    setAugNum,
    setInferenceSamplesPerBatch,
    setLearningRate,
    setNumCPUs,
    setNumGPUs,
    setSolverSamplesPerBatch,
  } = YAMLContext;

  const [yamlContent, setYamlContent] = useState("");
  const [presetOptions, setPresetOptions] = useState([]);
  const [presetYamlText, setPresetYamlText] = useState(null);
  const [architectureOptions, setArchitectureOptions] = useState([]);
  const [isLoadingPresets, setIsLoadingPresets] = useState(false);
  const [isLoadingArchitectures, setIsLoadingArchitectures] = useState(false);
  const currentConfig = type === "training" ? trainingConfig : inferenceConfig;
  const setConfigOriginPath = workflow.setConfigOriginPath;
  const selectedYamlPreset = workflow.selectedYamlPreset;
  const configOriginPath = workflow.configOriginPath;
  const setSelectedYamlPreset = workflow.setSelectedYamlPreset;

  const sliderData = useMemo(() => {
    if (type === "training") {
      return [
        {
          key: "batch_size",
          label: "Batch size",
          min: 1,
          max: 32,
          marks: { 1: 1, 8: 8, 16: 16, 32: 32 },
          value: YAMLContext.solverSamplesPerBatch,
          step: 1,
        },
        {
          key: "gpus",
          label: "GPUs",
          min: 0,
          max: 8,
          marks: { 0: 0, 4: 4, 8: 8 },
          value: YAMLContext.numGPUs,
          step: 1,
        },
        {
          key: "cpus",
          label: "CPUs",
          min: 1,
          max: 16,
          marks: { 1: 1, 8: 8, 16: 16 },
          value: YAMLContext.numCPUs,
          step: 1,
        },
      ];
    }

    return [
      {
        key: "batch_size",
        label: "Batch size",
        min: 1,
        max: 32,
        marks: { 1: 1, 8: 8, 16: 16, 32: 32 },
        value: YAMLContext.inferenceSamplesPerBatch,
        step: 1,
      },
      {
        key: "augmentations",
        label: "Augmentations",
        min: 4,
        max: 16,
        marks: { 4: 4, 8: 8, 16: 16 },
        value: YAMLContext.augNum,
        step: null,
      },
    ];
  }, [
    type,
    YAMLContext.numGPUs,
    YAMLContext.numCPUs,
    YAMLContext.solverSamplesPerBatch,
    YAMLContext.augNum,
    YAMLContext.inferenceSamplesPerBatch,
  ]);

  const setCurrentOriginPath = useCallback((nextOriginPath) => {
    setConfigOriginPath(nextOriginPath || "");
  }, [setConfigOriginPath]);

  const setCurrentConfig = useCallback(
    (nextContent) => {
      if (type === "training") {
        setTrainingConfig(nextContent);
      } else {
        setInferenceConfig(nextContent);
      }
      setYamlContent(nextContent);
    },
    [setInferenceConfig, setTrainingConfig, type],
  );

  const getPathValue = useCallback((val) => {
    if (!val) return "";
    if (typeof val === "string") return val;
    return val.path || val.folderPath || "";
  }, []);

  const getFileName = (path) => {
    if (!path) return "";
    const parts = path.split(/[/\\]/);
    return parts[parts.length - 1];
  };

  const updateInputSelectorInformation = useCallback((yamlData) => {
    const inputImagePath = getPathValue(workflow.inputImage);
    const inputLabelPath = getPathValue(workflow.inputLabel);
    const inputPath = findCommonPartOfString(inputImagePath, inputLabelPath);
    const outputPath = getPathValue(workflow.outputPath);
    applyInputPaths(yamlData, {
      mode: type,
      inputImagePath,
      inputLabelPath,
      inputPath,
      outputPath,
    });
  }, [
    getPathValue,
    type,
    workflow.inputImage,
    workflow.inputLabel,
    workflow.outputPath,
  ]);

  const syncYamlContext = useCallback((yamlData) => {
    if (!yamlData) return;
    const gpus = getSliderValue(yamlData, "training", "gpus");
    if (typeof gpus === "number") {
      setNumGPUs(gpus);
    }
    const cpus = getSliderValue(yamlData, "training", "cpus");
    if (typeof cpus === "number") {
      setNumCPUs(cpus);
    }
    const trainBatch = getSliderValue(yamlData, "training", "batch_size");
    if (typeof trainBatch === "number") {
      setSolverSamplesPerBatch(trainBatch);
    }
    const inferenceBatch = getSliderValue(yamlData, "inference", "batch_size");
    if (typeof inferenceBatch === "number") {
      setInferenceSamplesPerBatch(inferenceBatch);
    }
    const augNum = getSliderValue(yamlData, "inference", "augmentations");
    if (typeof augNum === "number") {
      setAugNum(augNum);
    }
    const learningRate =
      yamlData.SOLVER?.BASE_LR ?? yamlData.optimization?.optimizer?.lr;
    if (typeof learningRate === "number") {
      setLearningRate(learningRate);
    }
  }, [
    setAugNum,
    setInferenceSamplesPerBatch,
    setLearningRate,
    setNumCPUs,
    setNumGPUs,
    setSolverSamplesPerBatch,
  ]);

  const applyYamlData = useCallback((yamlData, sourceLabel, originPath = "") => {
    if (!yamlData) {
      message.error("Failed to load YAML configuration.");
      return;
    }

    updateInputSelectorInformation(yamlData);
    const serialized = yaml
      .dump(yamlData, { indent: 2 })
      .replace(/^\s*\n/gm, "");
    setCurrentConfig(serialized);
    syncYamlContext(yamlData);

    const configSummary = summarizeConfigObject(yamlData, type);
    const diagnostics = detectConfigDiagnostics({ config: configSummary });
    logClientEvent("yaml_config_applied", {
      level: diagnostics.length ? "WARNING" : "INFO",
      message: sourceLabel || `${type} YAML updated`,
      source: "yaml-uploader",
      data: {
        type,
        sourceLabel: sourceLabel || null,
        originPath: originPath || workflow.configOriginPath || "",
        configSummary,
        diagnostics,
      },
    });

    if (sourceLabel) {
      message.success(`${sourceLabel} loaded.`);
    }
  }, [
    setCurrentConfig,
    syncYamlContext,
    type,
    updateInputSelectorInformation,
    workflow.configOriginPath,
  ]);

  const serializeYaml = useCallback((yamlData) => {
    return yaml.dump(yamlData, { indent: 2 }).replace(/^\s*\n/gm, "");
  }, []);

  const normalizeYamlText = (text) => {
    if (!text) return "";
    try {
      const parsed = yaml.load(text);
      return yaml.dump(parsed, { indent: 2 }).replace(/^\s*\n/gm, "");
    } catch (error) {
      return text;
    }
  };

  const parseYaml = useCallback((yamlText, showError = true) => {
    if (!yamlText) return null;
    try {
      return yaml.load(yamlText);
    } catch (error) {
      logClientEvent("yaml_parse_failed", {
        level: "ERROR",
        message: "Failed to parse YAML in uploader",
        source: "yaml-uploader",
        data: {
          type,
          showError,
          error: error.message || "unknown error",
          textLength: yamlText.length || 0,
        },
      });
      if (showError) {
        message.error("Error parsing YAML content.");
      }
      return null;
    }
  }, [type]);

  const handleFileUpload = (file) => {
    workflow.setUploadedYamlFile(file);
    workflow.setSelectedYamlPreset("");
    setPresetYamlText(null);
    setCurrentOriginPath(getPathValue(file));
    const reader = new FileReader();
    reader.onload = (e) => {
      const contents = e.target.result;
      const yamlData = parseYaml(contents);
      if (!yamlData) return;
      applyYamlData(yamlData, "YAML file", getPathValue(file));
    };
    reader.readAsText(file);
  };

  const handlePresetSelect = async (value) => {
    setIsLoadingPresets(true);
    try {
      const res = await getConfigPresetContent(value);
      setPresetYamlText(res.content || null);
      const yamlData = parseYaml(res.content);
      if (!yamlData) return;
      workflow.setSelectedYamlPreset(value);
      workflow.setUploadedYamlFile("");
      setCurrentOriginPath(value);
      applyYamlData(yamlData, "Preset config", value);
    } catch (error) {
      message.error(error?.message || "Failed to load preset config.");
    } finally {
      setIsLoadingPresets(false);
    }
  };

  const handleRevertPreset = () => {
    if (!presetYamlText) return;
    const yamlData = parseYaml(presetYamlText);
    if (!yamlData) return;
    applyYamlData(yamlData, "Preset restored", workflow.selectedYamlPreset);
  };

  const handleSliderChange = (sliderKey, newValue) => {
    if (!currentConfig) {
      message.warning("Load a preset or upload a YAML file first.");
      return;
    }
    const yamlData = parseYaml(currentConfig) || {};
    const updated = setSliderValue(yamlData, type, sliderKey, newValue);
    if (!updated) {
      message.info("This setting is not available for the loaded config.");
      return;
    }
    applyYamlData(yamlData);
  };

  const handleArchitectureChange = (value) => {
    if (!currentConfig) {
      message.warning("Load a preset or upload a YAML file first.");
      return;
    }
    const yamlData = parseYaml(currentConfig) || {};
    const updated = setArchitectureValue(yamlData, value);
    if (!updated) {
      message.info("Architecture field is not supported by this config.");
      return;
    }
    applyYamlData(yamlData, "Model architecture updated");
  };

  useEffect(() => {
    const loadPresets = async () => {
      setIsLoadingPresets(true);
      try {
        const res = await getConfigPresets();
        const options = (res.configs || []).map((configPath) => ({
          value: configPath,
          label: configPath,
        }));
        setPresetOptions(options);
      } catch (error) {
        setPresetOptions([]);
      } finally {
        setIsLoadingPresets(false);
      }
    };

    const loadArchitectures = async () => {
      setIsLoadingArchitectures(true);
      try {
        const res = await getModelArchitectures();
        const options = (res.architectures || []).map((arch) => ({
          value: arch,
          label: arch,
        }));
        setArchitectureOptions(options);
      } catch (error) {
        setArchitectureOptions([]);
      } finally {
        setIsLoadingArchitectures(false);
      }
    };

    loadPresets();
    loadArchitectures();
  }, []);

  useEffect(() => {
    if (!selectedYamlPreset || !presetOptions.length) return;
    const selectedPresetStillExists = presetOptions.some(
      (option) => option.value === selectedYamlPreset,
    );
    if (selectedPresetStillExists) return;

    logClientEvent("yaml_preset_missing", {
      level: "WARNING",
      message: "Persisted YAML preset was not found in the current preset list",
      source: "yaml-uploader",
      data: {
        type,
        missingPreset: selectedYamlPreset,
        currentOriginPath: configOriginPath || "",
      },
    });

    setSelectedYamlPreset("");
    setPresetYamlText(null);
    if (configOriginPath === selectedYamlPreset) {
      setCurrentOriginPath("");
    }
  }, [
    configOriginPath,
    presetOptions,
    selectedYamlPreset,
    setCurrentOriginPath,
    setSelectedYamlPreset,
    type,
  ]);

  useEffect(() => {
    if (currentConfig) {
      setYamlContent(currentConfig);
      const yamlData = parseYaml(currentConfig);
      if (yamlData) {
        syncYamlContext(yamlData);
      }
    }
  }, [currentConfig, parseYaml, syncYamlContext]);

  useEffect(() => {
    if (!currentConfig) return;

    const yamlData = parseYaml(currentConfig, false);
    if (!yamlData) return;

    updateInputSelectorInformation(yamlData);
    const nextSerialized = serializeYaml(yamlData);
    if (nextSerialized !== currentConfig) {
      setCurrentConfig(nextSerialized);
    }
  }, [currentConfig, parseYaml, serializeYaml, setCurrentConfig, updateInputSelectorInformation]);

  const currentYamlData = useMemo(() => {
    if (!currentConfig) return null;
    return parseYaml(currentConfig, false);
  }, [currentConfig, parseYaml]);

  const currentArchitecture = useMemo(() => {
    return getArchitectureValue(currentYamlData);
  }, [currentYamlData]);

  const currentArchitecturePath = useMemo(() => {
    return getArchitecturePath(currentYamlData);
  }, [currentYamlData]);

  const architectureSupported = useMemo(() => {
    return isArchitectureSupported(currentYamlData);
  }, [currentYamlData]);

  const baseConfigTaskContext = BASE_CONFIG_TASK_CONTEXT[type];

  return (
    <div style={{ margin: "10px" }}>
      <Space wrap size={12} style={{ marginBottom: 12 }}>
        <Upload beforeUpload={handleFileUpload} showUploadList={false}>
          <Button icon={<UploadOutlined />} size="small">
            Upload YAML File
          </Button>
        </Upload>
        <Select
          placeholder="Choose a preset config"
          style={{ minWidth: 280 }}
          loading={isLoadingPresets}
          options={presetOptions}
          onChange={handlePresetSelect}
          value={workflow.selectedYamlPreset || undefined}
          allowClear
          onClear={() => workflow.setSelectedYamlPreset("")}
        />
      </Space>

      {(workflow.uploadedYamlFile || workflow.selectedYamlPreset) && (
        <div
          style={{
            marginBottom: 12,
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <strong>Loaded:</strong>{" "}
          {workflow.uploadedYamlFile?.name || workflow.selectedYamlPreset}
          {workflow.selectedYamlPreset && presetYamlText && (
            <>
              <span style={{ color: "#fa8c16", fontSize: 12 }}>
                {normalizeYamlText(currentConfig) !==
                normalizeYamlText(presetYamlText)
                  ? "Modified"
                  : "Preset"}
              </span>
              {normalizeYamlText(currentConfig) !==
                normalizeYamlText(presetYamlText) && (
                <Button size="small" type="link" onClick={handleRevertPreset}>
                  Revert to preset
                </Button>
              )}
            </>
          )}
        </div>
      )}

      <Divider style={{ margin: "12px 0" }} />

      <div
        style={{
          marginBottom: 12,
          padding: "8px 12px",
          background: "#fafafa",
          border: "1px solid #f0f0f0",
          borderRadius: 8,
          fontSize: 12,
        }}
      >
        <strong>Effective dataset paths</strong>
        <div style={{ marginTop: 4 }}>
          <div>
            {/* Common folder mirrors DATASET.INPUT_PATH = shared parent dir */}
            Common folder:{" "}
            {getPathValue(workflow.inputImage) &&
            getPathValue(workflow.inputLabel)
              ? findCommonPartOfString(
                  getPathValue(workflow.inputImage),
                  getPathValue(workflow.inputLabel),
                )
              : "—"}
          </div>
          <div>
            Image name: {getFileName(getPathValue(workflow.inputImage)) || "—"}
          </div>
          <div>
            Label name: {getFileName(getPathValue(workflow.inputLabel)) || "—"}
          </div>
          <div>Output path: {getPathValue(workflow.outputPath) || "—"}</div>
        </div>
      </div>

      <Row gutter={[16, 16]}>
        <Col span={12}>
          <div>
            <Space align="center" size={4}>
              <h4 style={{ marginBottom: 0 }}>Model architecture</h4>
              <InlineHelpChat
                taskKey={`${type}:base-config`}
                label="Model architecture"
                yamlKey={
                  currentArchitecturePath
                    ? currentArchitecturePath.join(".")
                    : undefined
                }
                value={currentArchitecture}
                projectContext={PROJECT_CONTEXT}
                taskContext={baseConfigTaskContext}
              />
            </Space>
            <Space style={{ width: "100%" }} align="start">
              <Select
                placeholder="Select architecture"
                loading={isLoadingArchitectures}
                options={architectureOptions}
                style={{ width: "100%" }}
                value={currentArchitecture}
                onChange={handleArchitectureChange}
                disabled={!yamlContent || !architectureSupported}
              />
            </Space>
          </div>
        </Col>
      </Row>

      <Divider style={{ margin: "12px 0" }} />

      {yamlContent ? (
        <Row>
          {sliderData.map((param, index) => {
            const sliderValue = getSliderValue(currentYamlData, type, param.key);
            const sliderPath = getSliderPath(currentYamlData, type, param.key);
            const sliderSupported = isSliderSupported(
              currentYamlData,
              type,
              param.key,
            );
            return (
              <Fragment key={index}>
                <Col span={8} offset={2}>
                  <div>
                    <Space align="center">
                      <h4 style={{ marginBottom: 0 }}>{param.label}</h4>
                      <InlineHelpChat
                        taskKey={`${type}:base-config`}
                        label={param.label}
                        yamlKey={sliderPath ? sliderPath.join(".") : undefined}
                        value={
                          typeof sliderValue === "number"
                            ? sliderValue
                            : param.value
                        }
                        projectContext={PROJECT_CONTEXT}
                        taskContext={baseConfigTaskContext}
                      />
                    </Space>
                    <Slider
                      min={param.min}
                      max={param.max}
                      marks={param.marks}
                      value={typeof sliderValue === "number" ? sliderValue : param.value}
                      disabled={!sliderSupported}
                      onChange={(newValue) =>
                        handleSliderChange(param.key, newValue)
                      }
                      step={param.step}
                    />
                  </div>
                </Col>
              </Fragment>
            );
          })}
        </Row>
      ) : (
        <div style={{ color: "#8c8c8c" }}>
          Load a preset or upload a YAML file to unlock the configuration
          controls.
        </div>
      )}
    </div>
  );
};

export default YamlFileUploader;
