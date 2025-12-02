import React, { useState, useEffect } from 'react';
import { Button, Spin, Alert, Typography } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import axios from 'axios';

const { Text, Title } = Typography;
const API_BASE = `${process.env.REACT_APP_SERVER_PROTOCOL || 'http'}://${process.env.REACT_APP_SERVER_URL || 'localhost:4243'}`;

/**
 * NeuroglancerViewer Component
 * 
 * Loads and displays Neuroglancer viewer in an iframe using the project's image files.
 * Uses the same approach as the Visualization tab.
 * 
 * @param {number} projectId - Project ID to load viewer for
 * @param {object} currentSynapse - Current synapse for position reference
 */
function NeuroglancerViewer({ projectId = 1, currentSynapse }) {
  const [viewerUrl, setViewerUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load Neuroglancer viewer on mount
  useEffect(() => {
    loadViewer();
  }, [projectId]);

  const loadViewer = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.get(
        `${API_BASE}/api/synanno/ng-url/${projectId}`,
        { withCredentials: true }
      );

      if (response.data.url) {
        setViewerUrl(response.data.url);
      } else {
        // If backend returns a message instead of URL (transition state)
        if (response.data.message) {
          // We can handle the message here, but for now let's just show the "Setup in Progress" state
          // by not setting the URL.
          console.log("Neuroglancer message:", response.data.message);
        }
        setError(null); // Clear error if it's just a transition message
      }
    } catch (err) {
      console.error('Failed to load Neuroglancer viewer', err);
      setError(err.response?.data?.detail || 'Failed to load Neuroglancer viewer');
    } finally {
      setLoading(false);
    }
  };

  const refreshViewer = () => {
    loadViewer();
  };

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100%',
        minHeight: '400px'
      }}>
        <Spin size="large" tip="Loading Neuroglancer viewer..." />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100%',
        padding: '40px',
        gap: '16px'
      }}>
        <Alert
          message="Failed to Load Viewer"
          description={error}
          type="error"
          showIcon
          style={{ maxWidth: '600px' }}
        />
        <Button onClick={loadViewer}>Try Again</Button>
      </div>
    );
  }

  // Display viewer in iframe
  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <div style={{
        position: 'absolute',
        top: 10,
        right: 10,
        zIndex: 1000,
        background: 'rgba(255, 255, 255, 0.9)',
        borderRadius: '4px',
        padding: '4px'
      }}>
        <Button
          type="link"
          icon={<ReloadOutlined />}
          onClick={refreshViewer}
          title="Refresh viewer"
        />
        {currentSynapse && (
          <Text type="secondary" style={{ marginLeft: '8px', fontSize: '12px' }}>
            Synapse #{currentSynapse.id}
          </Text>
        )}
      </div>
      {viewerUrl ? (
        <iframe
          title="Neuroglancer Viewer"
          width="100%"
          height="800"
          frameBorder="0"
          scrolling="no"
          src={viewerUrl}
          style={{ background: '#000' }}
        />
      ) : (
        <div style={{ padding: 40, textAlign: 'center' }}>
          <Title level={4}>Setup in Progress</Title>
          <Text>Data server is running. Preparing viewer...</Text>
          <div style={{ marginTop: 20 }}>
            <Alert
              message="Transitioning to Web Client"
              description="Converting data to NIfTI format for web compatibility..."
              type="info"
              showIcon
            />
          </div>
        </div>
      )}
    </div>
  );
}

export default NeuroglancerViewer;
