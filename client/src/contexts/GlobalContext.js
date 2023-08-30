import React, { useState } from "react";

export const AppContext = React.createContext(null);

export const ContextWrapper = (props) => {
  const [files, setFiles] = useState([]);
  const [fileList, setFileList] = useState([]);
  const [currentImage, setCurrentImage] = useState(null);
  const [currentLabel, setCurrentLabel] = useState(null);
  const [inputImage, setInputImage] = useState(null);
  const [inputLabel, setInputLabel] = useState(null);
  const [viewer, setViewer] = useState(null);
  const [trainingConfig, setTrainingConfig] = useState(null);
  const [inferenceConfig, setInferenceConfig] = useState(null);
  const [uploadedYamlFile, setUploadedYamlFile] = useState("");
  const [imageFileList, setImageFileList] = useState([]);
  const [labelFileList, setLabelFileList] = useState([]);

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
      }}
    >
      {props.children}
    </AppContext.Provider>
  );
};
