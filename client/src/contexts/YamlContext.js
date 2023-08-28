import React, { useState } from "react";

export const YamlContext = React.createContext(null);

export const YamlContextWrapper = (props) => {
  // for training
  const [numGPUs, setNumGPUs] = useState(0);
  const [numCPUs, setNumCPUs] = useState(0);
  const [solverSamplesPerBatch, setSolverSamplesPerBatch] = useState(0);
  const [learningRate, setLearningRate] = useState(0);

  // for inference
  const [inferenceSamplesPerBatch, setInferenceSamplesPerBatch] = useState(0);
  const [augNum, setAugNum] = useState(0);

  return (
    <YamlContext.Provider
      value={{
        numGPUs,
        setNumGPUs,
        numCPUs,
        setNumCPUs,
        solverSamplesPerBatch,
        setSolverSamplesPerBatch,
        learningRate,
        setLearningRate,
        inferenceSamplesPerBatch,
        setInferenceSamplesPerBatch,
        augNum,
        setAugNum,
      }}
    >
      {props.children}
    </YamlContext.Provider>
  );
};
