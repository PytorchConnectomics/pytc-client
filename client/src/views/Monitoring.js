import React, { useState, useEffect } from "react";
import { getTensorboardURL } from "../utils/api";

function Monitoring() {
  const [tensorboardURL, setTensorboardURL] = useState(null);

  const callGetTensorboardURL = async () => {
    try {
      const res = await getTensorboardURL();
      console.log(res);
      setTensorboardURL(res);
    } catch (e) {
      console.log(e);
    }
  };

  useEffect(() => {
    if (!tensorboardURL) {
      callGetTensorboardURL();
    }
  }, [tensorboardURL]);

  return (
    <>
      {tensorboardURL && (
        <iframe
          title="Tensorboard Display"
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
export default Monitoring;
