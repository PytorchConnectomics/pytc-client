import React, { useContext, useState } from "react";
import {
  Button,
  Cascader,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Radio,
  Select,
  Switch,
  TreeSelect,
} from "antd";
import axios from "axios";
import {
  getNeuroglancerViewer,
  startModelTraining,
  startTensorboard,
} from "../utils/api";
import Configurator from "../components/Configurator";
import { AppContext } from "../contexts/GlobalContext";

function ModelTraining() {
  const context = useContext(AppContext);
  const [isTraining, setIsTraining] = useState(false);
  const [tensorboardURL, setTensorboardURL] = useState(null);
  const handleStartButton = () => {
    try {
      // let fmData = new FormData();
      // fmData.append(
      //   "configBase",
      //   "--config-base configs/SNEMI/SNEMI-Base.yaml"
      // );
      const res = startModelTraining();
      console.log(res);
    } catch (e) {
      console.log(e);
    } finally {
      setIsTraining(true);
    }
  };

  const handleStopButton = () => {};

  const handleTensorboardButton = async () => {
    try {
      const res = await startTensorboard();
      console.log(res);
      setTensorboardURL(res);
    } catch (e) {
      console.log(e);
    }
  };
  const [componentSize, setComponentSize] = useState("default");
  const onFormLayoutChange = ({ size }) => {
    setComponentSize(size);
  };

  return (
    <>
      <div>
        {"ModelTraining"}
        <Configurator fileList={context.files} />
        <Button onClick={handleStartButton} disabled={!context.trainingConfig}>
          Start Training
        </Button>
        <Button onClick={handleStopButton} disabled={!isTraining}>
          Stop Training
        </Button>
        <Button onClick={handleTensorboardButton}>Tensorboard</Button>
      </div>
      {tensorboardURL && (
        <iframe
          width="100%"
          height="800"
          frameBorder="0"
          scrolling="no"
          src={tensorboardURL}
        />
      )}
    </>
  );
}

export default ModelTraining;
