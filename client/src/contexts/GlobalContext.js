import React, { createContext, useState, useEffect } from "react";

export const AppContext = createContext(null);

function usePersistedState(key, defaultValue) {
  const [state, setState] = useState(() => {
    const storedValue = localStorage.getItem(key);
    return safeParseJSON(storedValue, defaultValue);
  });

  useEffect(() => {
    localStorage.setItem(key, JSON.stringify(state));
  }, [key, state]);

  return [state, setState];
}

function safeParseJSON(jsonString, defaultValue) {
  try {
    return JSON.parse(jsonString) || defaultValue;
  } catch (e) {
    console.error("Error parsing JSON:", e);
    return defaultValue;
  }
}

export const ContextWrapper = (props) => {
  const [files, setFiles] = usePersistedState("files", []);
  const [fileList, setFileList] = usePersistedState('fileList', []);
  const [trainingConfig, setTrainingConfig] = usePersistedState('trainingConfig', null);
  const [inferenceConfig, setInferenceConfig] = usePersistedState('inferenceConfig', null);
  const [uploadedYamlFile, setUploadedYamlFile] = usePersistedState('uploadedYamlFile', "");
  const [imageFileList, setImageFileList] = usePersistedState('imageFileList', []);
  const [labelFileList, setLabelFileList] = usePersistedState('labelFileList', []);
  const [outputPath, setOutputPath] = usePersistedState('outputPath', null);
  const [logPath, setLogPath] = usePersistedState('logPath', null);
  const [checkpointPath, setCheckpointPath] = usePersistedState('checkpointPath', null);
  const [currentImage, setCurrentImage] = usePersistedState('currentImage', null);
  const [currentLabel, setCurrentLabel] = usePersistedState('currentLabel', null);
  const [inputImage, setInputImage] = usePersistedState('inputImage', null);
  const [inputLabel, setInputLabel] = usePersistedState('inputLabel', null);
  const [viewer, setViewer] = usePersistedState('viewer', null);

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
        inputImage,
        setInputImage,
        inputLabel,
        setInputLabel,
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
        uploadedYamlFile,
        setUploadedYamlFile,
        outputPath,
        setOutputPath,
        logPath,
        setLogPath,
        checkpointPath,
        setCheckpointPath,
      }}
    >
      {props.children}
    </AppContext.Provider>
  );
};
