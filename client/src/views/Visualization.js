import React, { useContext } from "react";
import { AppContext } from "../contexts/GlobalContext";
import { Tabs } from "antd";

const { TabPane } = Tabs;

function Visualization(props) {
  const context = useContext(AppContext);
  const { viewers } = props;
  console.log(viewers);

  return (
    <div>
      {"Neuroglancer Viewer"}
      <Tabs>
        {viewers.map((viewer) => (
          <TabPane key={viewer.key} tab={viewer.title}>
            {viewer.viewer && (
              <iframe
                width="100%"
                height="800"
                frameBorder="0"
                scrolling="no"
                src={viewer.viewer}
              />
            )}
          </TabPane>
        ))}
      </Tabs>
    </div>
  );
}

export default Visualization;
