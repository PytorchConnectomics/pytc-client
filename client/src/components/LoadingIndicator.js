import React from 'react';
import { Spin } from 'antd';
import './LoadingIndicator.css';

const LoadingIndicator = () => {
  return (
    <div className="loading-indicator">
      <Spin size="large" tip="Loading..." />
    </div>
  );
};

export default LoadingIndicator;