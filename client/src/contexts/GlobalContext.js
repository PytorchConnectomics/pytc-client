import React, { createContext, useState, useEffect } from "react";
import localforage from 'localforage';

export const AppContext = createContext(null);

// Solve delete button error issue
function usePersistedState(key, defaultValue) {
  const [state, setState] = useState(defaultValue);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    // Fetch the stored value asynchronously when the component mounts
    localforage.getItem(key).then((storedValue) => {
      if (storedValue !== null) {
        setState(storedValue);
      }
      setIsLoaded(true);
    }).catch((err) => {
      console.error("Error retrieving value from localforage:", err);
      setIsLoaded(true);
    });
  }, [key]);

  useEffect(() => {
    if (isLoaded) {
      // Save the state to localforage asynchronously whenever it changes
      localforage.setItem(key, state).catch((err) => {
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
  const [tensorBoardURL, setTensorBoardURL] = usePersistedState('tensorBoardURL', null);

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
        tensorBoardURL,
        setTensorBoardURL,
      }}
    >
      {props.children}
    </AppContext.Provider>
  );
};
