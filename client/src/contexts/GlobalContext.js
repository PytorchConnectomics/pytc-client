import React, { useState } from "react";

export const AppContext = React.createContext(null);

export const ContextWrapper = (props) => {
  const [files, setFiles] = useState([]);
  const [currentImage, setCurrentImage] = useState(null);
  const [currentLabel, setCurrentLabel] = useState(null);
  const [currentImagePath, setCurrentImagePath] = useState(null);
  const [currentLabelPath, setCurrentLabelPath] = useState(null)
  return (
    <AppContext.Provider
      value={{
        files,
        setFiles,
        currentImage,
        setCurrentImage,
        currentLabel,
        setCurrentLabel,
          currentImagePath,
          setCurrentImagePath,
          currentLabelPath,
          setCurrentLabelPath,
      }}
    >
      {props.children}
    </AppContext.Provider>
  );
};
