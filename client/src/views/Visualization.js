import React, { useState, useEffect, useContext } from "react";
import { getNeuroglancerViewer } from "../utils/api";
import { AppContext } from "../contexts/GlobalContext";

function Visualization() {
  const context = useContext(AppContext);
  const [viewer, setViewer] = useState(null);

  useEffect(() => {
    const fetchNeuroglancerViewer = async (image, label) => {
      try {
        const res = await getNeuroglancerViewer(image, label);
        console.log(res);
        setViewer(res);
      } catch (e) {
        console.log(e);
      }
    };

    if (context.currentImage && !viewer) {
      fetchNeuroglancerViewer(context.currentImage, context.currentLabel);
    }
  }, [context.currentImage, context.currentLabel]);

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
