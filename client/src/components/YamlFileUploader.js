import React, { useContext, useState, useEffect } from "react";
import { Upload, Button, message, InputNumber, Slider, Row, Col } from "antd";
import { UploadOutlined } from "@ant-design/icons";
import yaml from "js-yaml";
import { AppContext } from "../contexts/GlobalContext";

const YamlFileUploader = () => {
  const context = useContext(AppContext);

  const [numGPUs, setNumGPUs] = useState(4);
  const [numCPUs, setNumCPUs] = useState(0);
  const [samplesPerBatch, setSamplesPerBatch] = useState(0);
  const [learningRate, setLearningRate] = useState(0);

  const [yamlContent, setYamlContent] = useState("");


  // const [yamlContents, setYamlContents] = useState("");

  const handleFileUpload = (file) => {
    context.setUploadedYamlFile(file);
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const contents = e.target.result;
        const yamlData = yaml.safeLoad(contents);
        context.setTrainingConfig(
          yaml.safeDump(yamlData, { indent: 2 }).replace(/^\s*\n/gm, "")
        );
          setNumGPUs(yamlData.SYSTEM.NUM_GPUS);
          setNumCPUs(yamlData.SYSTEM.NUM_CPUS);
          setLearningRate(yamlData.SOLVER.BASE_LR);
          setSamplesPerBatch(yamlData.SOLVER.SAMPLES_PER_BATCH)

      } catch (error) {
        message.error("Error reading YAML file.");
      }
    };
    reader.readAsText(file);
  };

  const handleSliderChange = (location, property, newValue) => {
    // Update the respective property based on the parameter
    switch (property) {
      case 'NUM_GPUS':
        setNumGPUs(newValue);
        break;
      case 'SYSTEM.NUM_CPUS':
        setNumCPUs(newValue);
        break;
      case 'SOLVER_BASE_LR':
        setLearningRate(newValue);
        break;
      case 'SOLVER.SAMPLES_PER_BATCH':
        setSamplesPerBatch(newValue);
        break;
      default:
        break;
    }

    // Update the YAML file if it has been uploaded
    if (context.uploadedYamlFile) {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const contents = e.target.result;
          const yamlData = yaml.safeLoad(contents);

          // Update the property value in the YAML data
          yamlData[location][property] = newValue;

          context.setTrainingConfig(
            yaml.safeDump(yamlData, { indent: 2 }).replace(/^\s*\n/gm, "")
          );
        } catch (error) {
          message.error("Error reading YAML file.");
        }
      };
      reader.readAsText(context.uploadedYamlFile);

      updateYamlData(property, newValue);
      setYamlContent(context.trainingConfig);
    }
  };

  const updateYamlData = (property, value) => {
    const updatedYamlData = { ...context.yamlData, [property]: value };
    const updatedYamlContent = yaml.safeDump(updatedYamlData, { indent: 2 }).replace(/^\s*\n/gm, "");
    setYamlContent(updatedYamlContent);
    context.setTrainingConfig(updatedYamlContent);
  };

  const handleTextAreaChange = (event) => {
    const updatedYamlContent = event.target.value;
    setYamlContent(updatedYamlContent);

    try {
      const updatedYamlData = yaml.safeLoad(updatedYamlContent);
      // Update specific YAML values based on the updated YAML data
      updateYamlData('SYSTEM.NUM_GPUS', updatedYamlData.SYSTEM.NUM_GPUS);
      updateYamlData('SYSTEM.NUM_CPUS', updatedYamlData.SYSTEM.NUM_CPUS);
      // Update other YAML values as needed
    } catch (error) {
      message.error("Error parsing YAML content.");
    }
  };

  useEffect(() => {
    setYamlContent(context.trainingConfig);
  }, [context.uploadedYamlFile, context.trainingConfig]);

  return (
    <div>
      <Upload beforeUpload={handleFileUpload} showUploadList={false}>
        <Button icon={<UploadOutlined />} size="small">
          Upload YAML File
        </Button>
      </Upload>
      {context.trainingConfig && (
        <div>
          <h3>Uploaded File: {context.uploadedYamlFile.name}</h3>
        </div>
      )}
      {context.trainingConfig && (
      <div>
      <Row>
        <Col span={8}
          offset={2}>
            <div><h4>Number of GPUs</h4>
          <Slider
            min={1}
            max={8}
            marks={{1:1,4:4,8:8}}
            defaultValue={numGPUs}
            onChange={(newValue) => handleSliderChange('SYSTEM','NUM_GPUS', newValue)}
            step={1}
          /> 
          </div>
        </Col>      
        <Col span={8}
        offset={4}>
          <div><h4>Number of CPUs</h4>
          <Slider
            min={1}
            max={8}
            marks={{1:1,4:4,8:8}}
            defaultValue={numCPUs}
            onChange={(newValue) => handleSliderChange('SYSTEM','NUM_CPUS', newValue)}
            step={1}
          /> 
          </div>
        </Col>
        </Row>
      <Row>
        <Col 
          span={8}
          offset={2}>
            <div>
              <h4>Learning Rate:</h4>
          <Slider
            min={.01}
            max={.1}
            marks={{.01:.01,.1:.1}}
            defaultValue={learningRate}
            onChange={(newValue) => handleSliderChange('SOLVER','BASE_LR', newValue)}
            step={.01}
          /> 
          </div>
        </Col>
        <Col 
          span={8}
          offset={4}>
          <div>
            <h4>Samples Per Batch:</h4>
          <Slider
            min={2}
            max={16}
            marks={{2:2,8:8,16:16}}
            defaultValue={samplesPerBatch}
            onChange={(newValue) => handleSliderChange('SOLVER','SAMPLES_PER_BATCH', newValue)}
            step={1}
          />
          </div> 
        </Col>
      </Row>
      </div>
      )}
      <textarea
        value={yamlContent}
        onChange={handleTextAreaChange}
        rows={10}
        cols={50}
      />
    </div>
    
  );
};

export default YamlFileUploader;

// <div>
//   <Upload onChange={handleFileUpload}>
//     <Button>Select File</Button>
//   </Upload>
//
//   {file && (
//     <div>
//       <h2>Uploaded File:</h2>
//       <p>{file.name}</p>
//     </div>
//   )}
//
//   {file && (
//     <div>
//       <h2>Data:</h2>
//       {showFullData ? (
//         <>
//           <p>Show full data here...</p>
//           <Button onClick={handleShowMore}>Show Less</Button>
//         </>
//       ) : (
//         <Button onClick={handleShowMore}>Show More</Button>
//       )}
//     </div>
//   )}
// </div>;
