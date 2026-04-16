// global FileReader
import React, {
  Fragment,
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
import { findCommonPartOfString } from "../utils";
import { adaptToPytcSchema } from "../utils/yamlSchemaAdapter";
import {
  applyInputPaths,
  getArchitectureValue,
  getSliderValue,
  isArchitectureSupported,
  isSliderSupported,
  setArchitectureValue,
  setSliderValue,
} from "../configSchema";

const YamlFileUploader = (props) => {
  const context = useContext(AppContext);
  const YAMLContext = useContext(YamlContext);
  const { type } = props;
  const workflow =
    type === "training" ? context.trainingState : context.inferenceState;

  const [yamlContent, setYamlContent] = useState("");
  const [presetOptions, setPresetOptions] = useState([]);
  const [presetYamlText, setPresetYamlText] = useState(null);
  const [architectureOptions, setArchitectureOptions] = useState([]);
  const [isLoadingPresets, setIsLoadingPresets] = useState(false);
  const [isLoadingArchitectures, setIsLoadingArchitectures] = useState(false);

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
        min: 1,
        max: 16,
        marks: { 1: 1, 8: 8, 16: 16 },
        value: YAMLContext.augNum,
        step: 1,
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

  const getCurrentConfig = () =>
    type === "training" ? context.trainingConfig : context.inferenceConfig;

  const setCurrentOriginPath = (nextOriginPath) => {
    workflow.setConfigOriginPath(nextOriginPath || "");
  };

  const setCurrentConfig = (nextContent) => {
    if (type === "training") {
      context.setTrainingConfig(nextContent);
    } else {
      context.setInferenceConfig(nextContent);
    }
    setYamlContent(nextContent);
  };

  const getPathValue = (val) => {
    if (!val) return "";
    if (typeof val === "string") return val;
    return val.path || val.folderPath || "";
  };

  const getFileName = (path) => {
    if (!path) return "";
    const parts = path.split(/[/\\]/);
    return parts[parts.length - 1];
  };

  const updateInputSelectorInformation = (yamlData) => {
    // Phase 1: Auto-populate Step 0 path slots from YAML if UI fields are empty.
    const ds = yamlData.DATASET || {};
    if (!getPathValue(workflow.inputImage) && ds.INPUT_PATH && ds.IMAGE_NAME) {
      context.setInputImage(ds.INPUT_PATH + ds.IMAGE_NAME);
    }
    if (!getPathValue(workflow.inputLabel) && ds.INPUT_PATH && ds.LABEL_NAME) {
      context.setInputLabel(ds.INPUT_PATH + ds.LABEL_NAME);
    }
    if (!getPathValue(workflow.outputPath) && ds.OUTPUT_PATH) {
      context.setOutputPath(ds.OUTPUT_PATH);
    }

    // Phase 2: Write current UI values back into the YAML (using configSchema).
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
  };

  const syncYamlContext = (yamlData) => {
    if (!yamlData) return;
    const gpus = getSliderValue(yamlData, "training", "gpus");
    if (typeof gpus === "number") {
      YAMLContext.setNumGPUs(gpus);
    }
    const cpus = getSliderValue(yamlData, "training", "cpus");
    if (typeof cpus === "number") {
      YAMLContext.setNumCPUs(cpus);
    }
    const trainBatch = getSliderValue(yamlData, "training", "batch_size");
    if (typeof trainBatch === "number") {
      YAMLContext.setSolverSamplesPerBatch(trainBatch);
    }
    const inferenceBatch = getSliderValue(yamlData, "inference", "batch_size");
    if (typeof inferenceBatch === "number") {
      YAMLContext.setInferenceSamplesPerBatch(inferenceBatch);
    }
    const augNum = getSliderValue(yamlData, "inference", "augmentations");
    if (typeof augNum === "number") {
      YAMLContext.setAugNum(augNum);
    }
    const learningRate =
      yamlData.SOLVER?.BASE_LR ?? yamlData.optimization?.optimizer?.lr;
    if (typeof learningRate === "number") {
      YAMLContext.setLearningRate(learningRate);
    }
  };

  const applyYamlData = (rawYamlData, sourceLabel) => {
    if (!rawYamlData) {
      message.error("Failed to load YAML configuration.");
      return;
    }

    // Detect schema and adapt to pytorch_connectomics format if needed.
    const {
      adapted: yamlData,
      originalSchema,
      wasAdapted,
    } = adaptToPytcSchema(rawYamlData);
    if (wasAdapted) {
      message.info(
        `Detected '${originalSchema}' schema — automatically converted to pytorch_connectomics format.`,
        5,
      );
    }

    updateInputSelectorInformation(yamlData);
    const serialized = yaml
      .dump(yamlData, { indent: 2 })
      .replace(/^\s*\n/gm, "");
    setCurrentConfig(serialized);
    syncYamlContext(yamlData);

    if (sourceLabel) {
      message.success(`${sourceLabel} loaded.`);
    }
  };

  const serializeYaml = (yamlData) => {
    return yaml.dump(yamlData, { indent: 2 }).replace(/^\s*\n/gm, "");
  };

  const normalizeYamlText = (text) => {
    if (!text) return "";
    try {
      const parsed = yaml.load(text);
      return yaml.dump(parsed, { indent: 2 }).replace(/^\s*\n/gm, "");
    } catch (error) {
      return text;
    }
  };

  const parseYaml = (yamlText, showError = true) => {
    if (!yamlText) return null;
    try {
      return yaml.load(yamlText);
    } catch (error) {
      if (showError) {
        message.error("Error parsing YAML content.");
      }
      return null;
    }
  };

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
      applyYamlData(yamlData, "YAML file");
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
      applyYamlData(yamlData, "Preset config");
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
    applyYamlData(yamlData, "Preset restored");
  };

  const handleSliderChange = (sliderKey, newValue) => {
    const currentConfig = getCurrentConfig();
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
    const currentConfig = getCurrentConfig();
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
    const currentConfig = getCurrentConfig();
    if (currentConfig) {
      setYamlContent(currentConfig);
      const yamlData = parseYaml(currentConfig);
      if (yamlData) {
        syncYamlContext(yamlData);
      }
    }
  }, [context.trainingConfig, context.inferenceConfig, type]);

  useEffect(() => {
    const currentConfig = getCurrentConfig();
    if (!currentConfig) return;

    const yamlData = parseYaml(currentConfig, false);
    if (!yamlData) return;

    updateInputSelectorInformation(yamlData);
    const nextSerialized = serializeYaml(yamlData);
    if (nextSerialized !== currentConfig) {
      setCurrentConfig(nextSerialized);
    }
  }, [
    workflow.inputImage,
    workflow.inputLabel,
    workflow.outputPath,
    context.trainingConfig,
    context.inferenceConfig,
    type,
  ]);

  const currentYamlData = useMemo(() => {
    const currentConfig = getCurrentConfig();
    if (!currentConfig) return null;
    return parseYaml(currentConfig, false);
  }, [context.trainingConfig, context.inferenceConfig, type]);

  const currentArchitecture = useMemo(() => {
    return getArchitectureValue(currentYamlData);
  }, [currentYamlData]);

  const architectureSupported = useMemo(() => {
    return isArchitectureSupported(currentYamlData);
  }, [currentYamlData]);

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
                {normalizeYamlText(getCurrentConfig()) !==
                normalizeYamlText(presetYamlText)
                  ? "Modified"
                  : "Preset"}
              </span>
              {normalizeYamlText(getCurrentConfig()) !==
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
            <h4>Model architecture</h4>
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
            const sliderValue = getSliderValue(
              currentYamlData,
              type,
              param.key,
            );
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
                    </Space>
                    <Slider
                      min={param.min}
                      max={param.max}
                      marks={param.marks}
                      value={
                        typeof sliderValue === "number"
                          ? sliderValue
                          : param.value
                      }
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
