import React, { useContext } from "react";
import { AppContext } from "../contexts/GlobalContext";

function Visualization() {
  const context = useContext(AppContext);

  return (
    <div>
      {"Neuroglancer Viewer"}
      {context.viewer && (
        <iframe
          width="100%"
          height="800"
          frameBorder="0"
          scrolling="no"
          src={context.viewer}
        />
      )}
    </div>
  );
}

export default Visualization;
