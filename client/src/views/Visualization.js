import React, { useState } from "react";
import { Tabs } from "antd";

function Visualization(props) {
  const { viewers, setViewers } = props;
  const [activeKey, setActiveKey] = useState(
    viewers.length > 0 ? viewers[0].key : null
  ); // Store the active tab key

  const handleEdit = (targetKey, action) => {
    if (action === "remove") {
      remove(targetKey);
    }
  };

  const remove = (targetKey) => {
    let newActiveKey = activeKey;
    let lastIndex = -1;
    viewers.forEach((item, i) => {
      if (item.key === targetKey) {
        lastIndex = i - 1;
      }
    });
    const newPanes = viewers.filter((item) => item.key !== targetKey);
    if (newPanes.length && newActiveKey === targetKey) {
      if (lastIndex >= 0) {
        newActiveKey = newPanes[lastIndex].key;
      } else {
        newActiveKey = newPanes[0].key;
      }
    }
    setViewers(newPanes);
    setActiveKey(newActiveKey);
  };
  const handleChange = (newActiveKey) => {
    setActiveKey(newActiveKey);
  };

  return (
    <div>
      <Tabs
        closeIcon={true}
        type="editable-card"
        hideAdd={true}
        onEdit={handleEdit}
        activeKey={activeKey}
        onChange={handleChange}
        items={viewers.map((viewer) => ({
          label: viewer.title,
          key: viewer.key,
          children: (
            <iframe
              width="100%"
              height="800"
              frameBorder="0"
              scrolling="no"
              src={viewer.viewer}
            />
          ),
        }))}
      />
    </div>
  );
}

export default Visualization;
