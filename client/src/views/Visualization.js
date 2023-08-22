import React, { useContext } from "react";
import { AppContext } from "../contexts/GlobalContext";

function Visualization(props) {
  const context = useContext(AppContext);
  const { viewer } = props;

  return (
    <div>
      {"Neuroglancer Viewer"}
      {viewer && (
        <iframe
          width="100%"
          height="800"
          frameBorder="0"
          scrolling="no"
          src={viewer}
        />
      )}
    </div>
  );
}

export default Visualization;
