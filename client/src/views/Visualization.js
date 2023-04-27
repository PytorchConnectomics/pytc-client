import React, { useState, useEffect, useContext } from "react";
import { getNeuroglancerViewer } from "../utils/api";
import { AppContext } from "../contexts/GlobalContext";

function Visualization() {
  const context = useContext(AppContext);
  const [viewer, setViewer] = useState(null);

  console.log(viewer);

  useEffect(() => {
    const fetchNeuroglancerViewer = async () => {
      try {
        const res = await getNeuroglancerViewer(
          context.currentImage,
          context.currentLabel
        );
        console.log(res);
        setViewer(res);
      } catch (e) {
        console.log(e);
      }
    };

    if (context.currentImage && !viewer) {
      fetchNeuroglancerViewer();
    }
  }, [context.currentImage]);

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
