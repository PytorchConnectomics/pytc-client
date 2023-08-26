import React, { useState } from "react";

export const AppContext = React.createContext(null);

export const ContextWrapper = (props) => {
  const [files, setFiles] = useState([]);
  const [fileList, setFileList] = useState([]);
  const [currentImage, setCurrentImage] = useState(null);
  const [currentLabel, setCurrentLabel] = useState(null);
  const [currentImagePath, setCurrentImagePath] = useState(null);
  const [currentLabelPath, setCurrentLabelPath] = useState(null);
  const [viewer, setViewer] = useState(null);

  const [trainingConfig, setTrainingConfig] = useState(null);
  const [inferenceConfig, setInferenceConfig] = useState(null);
  const [uploadedYamlFile, setUploadedYamlFile] = useState("");
  const [outputPath, setOutputPath] = useState(null);
  const [logPath, setLogPath] = useState(null);
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
        currentImagePath,
        setCurrentImagePath,
        currentLabelPath,
        setCurrentLabelPath,
        viewer,
        setViewer,
        trainingConfig,
        setTrainingConfig,
        inferenceConfig,
        setInferenceConfig,
        uploadedYamlFile,
        setUploadedYamlFile,
        outputPath,
        setOutputPath,
        logPath,
        setLogPath,
      }}
    >
      {props.children}
    </AppContext.Provider>
  );
};
