import React, { createContext, useState, useEffect, useCallback } from "react";
import localforage from "localforage";

export const AppContext = createContext(null);

const FILE_STATE_DEFAULTS = {
  files: [],
  fileList: [],
  imageFileList: [],
  labelFileList: [],
  currentImage: null,
  currentLabel: null,
  trainingInputImage: null,
  trainingInputLabel: null,
  inferenceInputImage: null,
  inferenceInputLabel: null,
};

const FILE_CACHE_KEYS = Object.keys(FILE_STATE_DEFAULTS);
const FILE_OBJECT_STATE_KEYS = [
  ...FILE_CACHE_KEYS.filter((key) => key !== "fileList"),
  "trainingUploadedYamlFile",
  "inferenceUploadedYamlFile",
];

const sanitizeFileEntry = (file) => {
  if (!file || typeof file !== "object") return file;
  const {
    uid,
    name,
    originalName,
    path,
    folderPath,
    thumbUrl,
    type,
    status,
    percent,
    size,
    response,
    error,
    lastModified,
    lastModifiedDate,
    url,
  } = file;
  return {
    uid,
    name,
    originalName: originalName || name,
    path,
    folderPath,
    thumbUrl,
    type,
    status,
    percent,
    size,
    response,
    error,
    lastModified,
    lastModifiedDate,
    url,
  };
};

const sanitizePersistedState = (key, state) => {
  if (!FILE_OBJECT_STATE_KEYS.includes(key)) {
    return state;
  }
  if (Array.isArray(state)) {
    return state.map((entry) => sanitizeFileEntry(entry));
  }
  return sanitizeFileEntry(state);
};

// Solve delete button error issue
function usePersistedState(key, defaultValue) {
  const [state, setState] = useState(defaultValue);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    // Fetch the stored value asynchronously when the component mounts
    localforage
      .getItem(key)
      .then((storedValue) => {
        if (storedValue !== null) {
          setState(storedValue);
        }
        setIsLoaded(true);
      })
      .catch((err) => {
        console.error("Error retrieving value from localforage:", err);
        setIsLoaded(true);
      });
  }, [key]);

  useEffect(() => {
    if (isLoaded) {
      // Save the state to localforage asynchronously whenever it changes
      const valueToPersist = sanitizePersistedState(key, state);
      localforage.setItem(key, valueToPersist).catch((err) => {
        console.error("Error setting value to localforage:", err);
      });
    }
  }, [key, state, isLoaded]);

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
    usePersistedState("trainingUploadedYamlFile", "");
  const [inferenceUploadedYamlFile, setInferenceUploadedYamlFile] =
    usePersistedState("inferenceUploadedYamlFile", "");
  const [trainingSelectedYamlPreset, setTrainingSelectedYamlPreset] =
    usePersistedState("trainingSelectedYamlPreset", "");
  const [inferenceSelectedYamlPreset, setInferenceSelectedYamlPreset] =
    usePersistedState("inferenceSelectedYamlPreset", "");
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
    usePersistedState("inferenceCheckpointPath", null);
  const [currentImage, setCurrentImage] = usePersistedState(
    "currentImage",
    null,
  );
  const [currentLabel, setCurrentLabel] = usePersistedState(
    "currentLabel",
    null,
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
      setCurrentImage(FILE_STATE_DEFAULTS.currentImage);
      setCurrentLabel(FILE_STATE_DEFAULTS.currentLabel);
      setTrainingInputImage(FILE_STATE_DEFAULTS.trainingInputImage);
      setTrainingInputLabel(FILE_STATE_DEFAULTS.trainingInputLabel);
      setInferenceInputImage(FILE_STATE_DEFAULTS.inferenceInputImage);
      setInferenceInputLabel(FILE_STATE_DEFAULTS.inferenceInputLabel);
    }
  }, [
    setFiles,
    setFileList,
    setImageFileList,
    setLabelFileList,
    setCurrentImage,
    setCurrentLabel,
    setTrainingInputImage,
    setTrainingInputLabel,
    setInferenceInputImage,
    setInferenceInputLabel,
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
