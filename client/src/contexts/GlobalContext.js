import React, { useState } from "react";

export const AppContext = React.createContext(null);

export const ContextWrapper = (props) => {
  const [images, setImages] = useState([]);
  const [currentImage, setCurrentImage] = useState(null);
  return (
    <AppContext.Provider
      value={{ images, setImages, currentImage, setCurrentImage }}
    >
      {props.children}
    </AppContext.Provider>
  );
};
