import React, { useState } from "react";

export const AppContext = React.createContext(null);

export const ContextWrapper = (props) => {
  const [files, setFiles] = useState([]);
  const [fileList, setFileList] = useState([]);
  const [currentImage, setCurrentImage] = useState(null);
  const [currentLabel, setCurrentLabel] = useState(null);
  const [trainingConfig, setTrainingConfig] = useState(null);
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
        trainingConfig,
        setTrainingConfig,
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
