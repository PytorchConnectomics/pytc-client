import React, { useState } from "react";

export const AppContext = React.createContext(null);

export const ContextWrapper = (props) => {
  const [files, setFiles] = useState([]);
  const [fileList, setFileList] = useState([]);
  const [currentImage, setCurrentImage] = useState(null);
  const [currentLabel, setCurrentLabel] = useState(null);
  const [trainingConfig, setTrainingConfig] = useState(null);
  const [uploadedYamlFile, setUploadedYamlFile] = useState("");

  const [imageFileList, setImageFileList] = useState([]);
  const [labelFileList, setLabelFileList] = useState([]);

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
          imageFileList,
          setImageFileList,
          labelFileList,
          setLabelFileList
      }}
    >
      {props.children}
    </AppContext.Provider>
  );
};
