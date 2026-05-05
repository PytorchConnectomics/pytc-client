import React, { createContext, useState, useCallback } from "react";
import localforage from "localforage";

export const AppContext = createContext(null);

const FILE_STATE_DEFAULTS = {
  files: [],
  fileList: [],
  imageFileList: [],
  labelFileList: [],
  currentImage: null,
  currentLabel: null,
  trainingConfig: null,
  inferenceConfig: null,
  trainingConfigOriginPath: "",
  inferenceConfigOriginPath: "",
  trainingUploadedYamlFile: "",
  inferenceUploadedYamlFile: "",
  trainingSelectedYamlPreset: "",
  inferenceSelectedYamlPreset: "",
  trainingOutputPath: null,
  inferenceOutputPath: null,
  trainingLogPath: null,
  inferenceCheckpointPath: null,
  trainingInputImage: null,
  trainingInputLabel: null,
  inferenceInputImage: null,
  inferenceInputLabel: null,
  viewer: null,
  tensorBoardURL: null,
  visualizationScales: "",
};

const FILE_CACHE_KEYS = Object.keys(FILE_STATE_DEFAULTS);
function usePersistedState(_key, defaultValue) {
  const [state, setState] = useState(defaultValue);
  return [state, setState];
}

// function safeParseJSON(jsonString, defaultValue) {
//   try {
//     return JSON.parse(jsonString) || defaultValue;
//   } catch (e) {
//     console.error("Error parsing JSON:", e);
//     return defaultValue;
//   }
// }

export const ContextWrapper = (props) => {
  const [files, setFiles] = usePersistedState("files", []);
  const [fileList, setFileList] = usePersistedState("fileList", []);
  const [trainingConfig, setTrainingConfig] = usePersistedState(
    "trainingConfig",
    null,
  );
  const [inferenceConfig, setInferenceConfig] = usePersistedState(
    "inferenceConfig",
    null,
  );
  const [trainingConfigOriginPath, setTrainingConfigOriginPath] =
    usePersistedState("trainingConfigOriginPath", "");
  const [inferenceConfigOriginPath, setInferenceConfigOriginPath] =
    usePersistedState("inferenceConfigOriginPath", "");
  const [trainingUploadedYamlFile, setTrainingUploadedYamlFile] =
    usePersistedState(
      "trainingUploadedYamlFile",
      "",
    );
  const [inferenceUploadedYamlFile, setInferenceUploadedYamlFile] =
    usePersistedState(
      "inferenceUploadedYamlFile",
      "",
    );
  const [trainingSelectedYamlPreset, setTrainingSelectedYamlPreset] =
    usePersistedState(
      "trainingSelectedYamlPreset",
      "",
    );
  const [inferenceSelectedYamlPreset, setInferenceSelectedYamlPreset] =
    usePersistedState(
      "inferenceSelectedYamlPreset",
      "",
    );
  const [imageFileList, setImageFileList] = usePersistedState(
    "imageFileList",
    [],
  );
  const [labelFileList, setLabelFileList] = usePersistedState(
    "labelFileList",
    [],
  );
  const [trainingOutputPath, setTrainingOutputPath] = usePersistedState(
    "trainingOutputPath",
    null,
  );
  const [inferenceOutputPath, setInferenceOutputPath] = usePersistedState(
    "inferenceOutputPath",
    null,
  );
  const [trainingLogPath, setTrainingLogPath] = usePersistedState(
    "trainingLogPath",
    null,
  );
  const [inferenceCheckpointPath, setInferenceCheckpointPath] =
    usePersistedState(
      "inferenceCheckpointPath",
      null,
    );
  const [currentImage, setCurrentImage] = usePersistedState(
    "currentImage",
    null,
  );
  const [currentLabel, setCurrentLabel] = usePersistedState(
    "currentLabel",
    null,
  );
  const [visualizationScales, setVisualizationScales] = usePersistedState(
    "visualizationScales",
    FILE_STATE_DEFAULTS.visualizationScales,
  );
  const [trainingInputImage, setTrainingInputImage] = usePersistedState(
    "trainingInputImage",
    null,
  );
  const [trainingInputLabel, setTrainingInputLabel] = usePersistedState(
    "trainingInputLabel",
    null,
  );
  const [inferenceInputImage, setInferenceInputImage] = usePersistedState(
    "inferenceInputImage",
    null,
  );
  const [inferenceInputLabel, setInferenceInputLabel] = usePersistedState(
    "inferenceInputLabel",
    null,
  );
  const [viewer, setViewer] = usePersistedState("viewer", null);
  const [tensorBoardURL, setTensorBoardURL] = usePersistedState(
    "tensorBoardURL",
    null,
  );

  const resetFileState = useCallback(async () => {
    try {
      await Promise.all(
        FILE_CACHE_KEYS.map((key) => localforage.removeItem(key)),
      );
    } catch (error) {
      console.error("Error clearing file cache from storage:", error);
    } finally {
      setFiles(FILE_STATE_DEFAULTS.files);
      setFileList(FILE_STATE_DEFAULTS.fileList);
      setImageFileList(FILE_STATE_DEFAULTS.imageFileList);
      setLabelFileList(FILE_STATE_DEFAULTS.labelFileList);
      setTrainingConfig(FILE_STATE_DEFAULTS.trainingConfig);
      setInferenceConfig(FILE_STATE_DEFAULTS.inferenceConfig);
      setTrainingConfigOriginPath(FILE_STATE_DEFAULTS.trainingConfigOriginPath);
      setInferenceConfigOriginPath(FILE_STATE_DEFAULTS.inferenceConfigOriginPath);
      setTrainingUploadedYamlFile(FILE_STATE_DEFAULTS.trainingUploadedYamlFile);
      setInferenceUploadedYamlFile(FILE_STATE_DEFAULTS.inferenceUploadedYamlFile);
      setTrainingSelectedYamlPreset(FILE_STATE_DEFAULTS.trainingSelectedYamlPreset);
      setInferenceSelectedYamlPreset(FILE_STATE_DEFAULTS.inferenceSelectedYamlPreset);
      setTrainingOutputPath(FILE_STATE_DEFAULTS.trainingOutputPath);
      setInferenceOutputPath(FILE_STATE_DEFAULTS.inferenceOutputPath);
      setTrainingLogPath(FILE_STATE_DEFAULTS.trainingLogPath);
      setInferenceCheckpointPath(FILE_STATE_DEFAULTS.inferenceCheckpointPath);
      setCurrentImage(FILE_STATE_DEFAULTS.currentImage);
      setCurrentLabel(FILE_STATE_DEFAULTS.currentLabel);
      setVisualizationScales(FILE_STATE_DEFAULTS.visualizationScales);
      setTrainingInputImage(FILE_STATE_DEFAULTS.trainingInputImage);
      setTrainingInputLabel(FILE_STATE_DEFAULTS.trainingInputLabel);
      setInferenceInputImage(FILE_STATE_DEFAULTS.inferenceInputImage);
      setInferenceInputLabel(FILE_STATE_DEFAULTS.inferenceInputLabel);
      setViewer(FILE_STATE_DEFAULTS.viewer);
      setTensorBoardURL(FILE_STATE_DEFAULTS.tensorBoardURL);
    }
  }, [
    setFiles,
    setFileList,
    setImageFileList,
    setLabelFileList,
    setTrainingConfig,
    setInferenceConfig,
    setTrainingConfigOriginPath,
    setInferenceConfigOriginPath,
    setTrainingUploadedYamlFile,
    setInferenceUploadedYamlFile,
    setTrainingSelectedYamlPreset,
    setInferenceSelectedYamlPreset,
    setTrainingOutputPath,
    setInferenceOutputPath,
    setTrainingLogPath,
    setInferenceCheckpointPath,
    setCurrentImage,
    setCurrentLabel,
    setVisualizationScales,
    setTrainingInputImage,
    setTrainingInputLabel,
    setInferenceInputImage,
    setInferenceInputLabel,
    setViewer,
    setTensorBoardURL,
  ]);

  const trainingState = {
    configOriginPath: trainingConfigOriginPath,
    setConfigOriginPath: setTrainingConfigOriginPath,
    uploadedYamlFile: trainingUploadedYamlFile,
    setUploadedYamlFile: setTrainingUploadedYamlFile,
    selectedYamlPreset: trainingSelectedYamlPreset,
    setSelectedYamlPreset: setTrainingSelectedYamlPreset,
    inputImage: trainingInputImage,
    setInputImage: setTrainingInputImage,
    inputLabel: trainingInputLabel,
    setInputLabel: setTrainingInputLabel,
    outputPath: trainingOutputPath,
    setOutputPath: setTrainingOutputPath,
    logPath: trainingLogPath,
    setLogPath: setTrainingLogPath,
  };

  const inferenceState = {
    configOriginPath: inferenceConfigOriginPath,
    setConfigOriginPath: setInferenceConfigOriginPath,
    uploadedYamlFile: inferenceUploadedYamlFile,
    setUploadedYamlFile: setInferenceUploadedYamlFile,
    selectedYamlPreset: inferenceSelectedYamlPreset,
    setSelectedYamlPreset: setInferenceSelectedYamlPreset,
    inputImage: inferenceInputImage,
    setInputImage: setInferenceInputImage,
    inputLabel: inferenceInputLabel,
    setInputLabel: setInferenceInputLabel,
    outputPath: inferenceOutputPath,
    setOutputPath: setInferenceOutputPath,
    checkpointPath: inferenceCheckpointPath,
    setCheckpointPath: setInferenceCheckpointPath,
  };

  return (
    <AppContext.Provider
      value={{
        files,
        setFiles,
        fileList,
        setFileList,
        currentImage,
        setCurrentImage,
        currentLabel,
        setCurrentLabel,
        visualizationScales,
        setVisualizationScales,
        viewer,
        setViewer,
        trainingConfig,
        setTrainingConfig,
        imageFileList,
        setImageFileList,
        labelFileList,
        setLabelFileList,
        inferenceConfig,
        setInferenceConfig,
        trainingState,
        inferenceState,
        tensorBoardURL,
        setTensorBoardURL,
        resetFileState,
      }}
    >
      {props.children}
    </AppContext.Provider>
  );
};
