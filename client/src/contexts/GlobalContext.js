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
  const [uploadedYamlFile, setUploadedYamlFile] = useState("");
  //<<<<<<< HEAD

  const [imageFileList, setImageFileList] = useState([]);
  const [labelFileList, setLabelFileList] = useState([]);

  //=======
  const [outputPath, setOutputPath] = useState(null);
  const [logPath, setLogPath] = useState(null);
  //>>>>>>> 438a71423abd5c2a128ecec668525c7c8ebe01d3
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
        //<<<<<<< HEAD
        /*uploadedYamlFile,
        setUploadedYamlFile,*/
        imageFileList,
        setImageFileList,
        labelFileList,
        setLabelFileList,
        //=======
        uploadedYamlFile,
        setUploadedYamlFile,
        outputPath,
        setOutputPath,
        logPath,
        setLogPath,
        //>>>>>>> 438a71423abd5c2a128ecec668525c7c8ebe01d3
      }}
    >
      {props.children}
    </AppContext.Provider>
  );
};
