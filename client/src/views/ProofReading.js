import React, { useState, useEffect } from 'react';
import { Layout, message, Spin, Empty } from 'antd';
import axios from 'axios';
import NeuroglancerViewer from '../components/NeuroglancerViewer';
import SynapseList from '../components/SynapseList';
import ProofreadingControls from '../components/ProofreadingControls';

const { Sider, Content } = Layout;
const API_BASE = `${process.env.REACT_APP_SERVER_PROTOCOL || 'http'}://${process.env.REACT_APP_SERVER_URL || 'localhost:4243'}`;

/**
 * ProofReading Component
 * 
 * Main view for synapse proofreading. Integrates Neuroglancer viewer,
 * synapse list, and proofreading controls. Supports keyboard shortcuts
 * for efficient workflow.
 */
function ProofReading() {
  const [synapses, setSynapses] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [neuroglancerUrl, setNeuroglancerUrl] = useState('');
  const [loading, setLoading] = useState(true);
  const [projectId, setProjectId] = useState(1); // Default to first project
  const [reviewedCount, setReviewedCount] = useState(0);

  // Fetch synapses on mount
  useEffect(() => {
    fetchSynapses();
    fetchNeuroglancerUrl();
  }, [projectId]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyPress = (e) => {
      // Don't trigger shortcuts when typing in input fields
      if (e.target.tagName === 'INPUT') return;

      switch (e.key.toLowerCase()) {
        case 'c':
          updateStatus('correct');
          break;
        case 'x':
          updateStatus('incorrect');
          break;
        case 'u':
          updateStatus('unsure');
          break;
        case 'arrowright':
          goToNext();
          break;
        case 'arrowleft':
          goToPrevious();
          break;
        case 's':
          saveCurrent();
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [currentIndex, synapses]);

  /**
   * Fetch synapses from backend
   */
  const fetchSynapses = async () => {
    try {
      setLoading(true);
      const res = await axios.get(`${API_BASE}/api/projects/${projectId}/synapses`, {
        withCredentials: true
      });
      setSynapses(res.data);

      // Count reviewed synapses (not in error state)
      const reviewed = res.data.filter(s => s.status !== 'error').length;
      setReviewedCount(reviewed);

      setLoading(false);
    } catch (err) {
      console.error('Failed to fetch synapses', err);
      message.error('Failed to load synapses');
      setLoading(false);
    }
  };

  /**
   * Fetch Neuroglancer URL for the project
   */
  const fetchNeuroglancerUrl = async () => {
    try {
      const res = await axios.get(`${API_BASE}/api/synanno/ng-url/${projectId}`, {
        withCredentials: true
      });
      setNeuroglancerUrl(res.data.url);
    } catch (err) {
      console.error('Failed to fetch Neuroglancer URL', err);
      message.error('Failed to load Neuroglancer viewer');
    }
  };

  /**
   * Update status of current synapse locally
   */
  const updateStatus = (status) => {
    if (synapses[currentIndex]) {
      const updated = [...synapses];
      updated[currentIndex] = { ...updated[currentIndex], status };
      setSynapses(updated);
    }
  };

  /**
   * Save current synapse to backend
   */
  const saveCurrent = async () => {
    if (!synapses[currentIndex]) return;

    try {
      await axios.put(
        `${API_BASE}/api/synapses/${synapses[currentIndex].id}`,
        {
          status: synapses[currentIndex].status,
          pre_neuron_id: synapses[currentIndex].pre_neuron_id,
          post_neuron_id: synapses[currentIndex].post_neuron_id
        },
        { withCredentials: true }
      );
      message.success('Synapse updated');

      // Update reviewed count
      const reviewed = synapses.filter(s => s.status !== 'error').length;
      setReviewedCount(reviewed);
    } catch (err) {
      console.error('Failed to update synapse', err);
      message.error('Failed to save changes');
    }
  };

  /**
   * Save synapse with provided updates
   */
  const handleSave = async (updates) => {
    if (!synapses[currentIndex]) return;

    try {
      await axios.put(
        `${API_BASE}/api/synapses/${synapses[currentIndex].id}`,
        updates,
        { withCredentials: true }
      );

      // Update local state
      const updated = [...synapses];
      updated[currentIndex] = { ...updated[currentIndex], ...updates };
      setSynapses(updated);

      message.success('Synapse updated');

      // Update reviewed count
      const reviewed = updated.filter(s => s.status !== 'error').length;
      setReviewedCount(reviewed);
    } catch (err) {
      console.error('Failed to update synapse', err);
      message.error('Failed to save changes');
    }
  };

  /**
   * Navigate to next synapse
   */
  const goToNext = () => {
    if (currentIndex < synapses.length - 1) {
      setCurrentIndex(currentIndex + 1);
    } else {
      message.info('You have reached the last synapse');
    }
  };

  /**
   * Navigate to previous synapse
   */
  const goToPrevious = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
    } else {
      message.info('You are at the first synapse');
    }
  };

  // Loading state
  if (loading) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100%',
        minHeight: '400px'
      }}>
        <Spin size="large" tip="Loading synapses..." />
      </div>
    );
  }

  // Empty state
  if (synapses.length === 0) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100%',
        minHeight: '400px'
      }}>
        <Empty
          description="No synapses found for proofreading"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      </div>
    );
  }

  return (
    <Layout style={{ height: 'calc(100vh - 160px)', background: '#fff' }}>
      {/* Left Panel: Synapse List */}
      <Sider
        width="15%"
        theme="light"
        style={{
          borderRight: '1px solid #f0f0f0',
          minWidth: '200px'
        }}
      >
        <SynapseList
          synapses={synapses}
          currentIndex={currentIndex}
          onSelectSynapse={setCurrentIndex}
          reviewedCount={reviewedCount}
        />
      </Sider>

      {/* Center: Neuroglancer Viewer */}
      <Content style={{ padding: '16px', background: '#fafafa' }}>
        <NeuroglancerViewer
          url={neuroglancerUrl}
          currentSynapse={synapses[currentIndex]}
        />
      </Content>

      {/* Right Panel: Proofreading Controls */}
      <Sider
        width="15%"
        theme="light"
        style={{
          borderLeft: '1px solid #f0f0f0',
          minWidth: '200px'
        }}
      >
        <ProofreadingControls
          currentSynapse={synapses[currentIndex]}
          onSave={handleSave}
          onNext={goToNext}
        />
      </Sider>
    </Layout>
  );
}

export default ProofReading;
