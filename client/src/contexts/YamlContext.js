import React, { useState } from "react";

export const YamlContext = React.createContext(null);

export const YamlContextWrapper = (props) => {
    const [numGPUs, setNumGPUs] = useState(0);
    const [numCPUs, setNumCPUs] = useState(0);
    const [samplesPerBatch, setSamplesPerBatch] = useState(0);
    const [learningRate, setLearningRate] = useState(0);
  return (
    <YamlContext.Provider
      value={{
        numGPUs,
        setNumGPUs,
        numCPUs,
        setNumCPUs,
        samplesPerBatch,
        setSamplesPerBatch,
        learningRate,
        setLearningRate
      }}
    >
      {props.children}
    </YamlContext.Provider>
  );
};