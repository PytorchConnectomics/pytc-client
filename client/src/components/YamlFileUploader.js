import React, { useContext, useState } from "react";
import { Upload, Button, message, Input } from "antd";
import { UploadOutlined } from "@ant-design/icons";
import yaml from "js-yaml";
import { AppContext } from "../contexts/GlobalContext";

const YamlFileUploader = () => {
  const context = useContext(AppContext);
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
      } catch (error) {
        message.error("Error reading YAML file.");
      }
    };
    reader.readAsText(file);
  };

  return (
    <div>
      <Upload beforeUpload={handleFileUpload} showUploadList={false}>
        <Button icon={<UploadOutlined />} size="small">
          Upload YAML File
        </Button>
      </Upload>
      {context.trainingConfig && (
        <div>
          <h2>Uploaded File: {context.uploadedYamlFile.name}</h2>
        </div>
      )}
      {/*
      {context.trainingConfig && (
        <Input.TextArea
          value={context.trainingConfig}
          // onChange={this.handleTextChange}
          autoSize={{ minRows: 4, maxRows: 8 }}
        />
      )}*/}
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
