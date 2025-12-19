import React, { useState, useEffect } from 'react';
import { Layout, message, Spin } from 'antd';
import DatasetLoader from './DatasetLoader';
import LayerGrid from './LayerGrid';
import ClassificationPanel from './ClassificationPanel';
import ProgressTracker from './ProgressTracker';
import UnifiedImageEditor from './UnifiedImageEditor';
import apiClient from '../../services/apiClient';

const { Sider, Content } = Layout;

/**
 * Detection Workflow Component
 * Main interface for error detection workflow
 */
function DetectionWorkflow({ sessionId, setSessionId, refreshTrigger }) {
  const [projectName, setProjectName] = useState('');
  const [totalLayers, setTotalLayers] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [layers, setLayers] = useState([]);
  const [selectedLayers, setSelectedLayers] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [editingLayer, setEditingLayer] = useState(null);

  const pageSize = 12; // 12 layers per page (3x4 grid)

  // Load layers when session or page changes
  useEffect(() => {
    if (sessionId) {
      loadLayers();
      loadStats();
    }
  }, [sessionId, currentPage, refreshTrigger]);

  // Keyboard shortcuts for main grid
  useEffect(() => {
    const handleKeyPress = (e) => {
      // Don't trigger shortcuts when typing in input fields or when modal is open
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || editingLayer) return;
      if (!sessionId) return;

      switch (e.key.toLowerCase()) {
        case 'c':
          if (selectedLayers.length > 0) handleClassify('correct');
          break;
        case 'x':
          if (selectedLayers.length > 0) handleClassify('incorrect');
          break;
        case 'u':
          if (selectedLayers.length > 0) handleClassify('unsure');
          break;
        case 'a':
          if (e.ctrlKey) {
            e.preventDefault();
            selectAllLayers();
          }
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [sessionId, selectedLayers, layers, editingLayer]);

  const handleDatasetLoad = async (datasetPath, maskPath, projectName) => {
    setLoading(true);
    try {
      const response = await apiClient.post('/eh/detection/load', {
        dataset_path: datasetPath,
        mask_path: maskPath || null,
        project_name: projectName
      });

      setSessionId(response.data.session_id);
      setProjectName(response.data.project_name);
      setTotalLayers(response.data.total_layers);
      setCurrentPage(1);
      message.success(`Loaded ${response.data.total_layers} layers successfully`);
    } catch (error) {
      console.error('Failed to load dataset:', error);
      message.error(error.response?.data?.detail || 'Failed to load dataset');
    } finally {
      setLoading(false);
    }
  };

  const loadLayers = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get('/eh/detection/layers', {
        params: {
          session_id: sessionId,
          page: currentPage,
          page_size: pageSize,
          include_images: true
        }
      });

      setLayers(response.data.layers);
    } catch (error) {
      console.error('Failed to load layers:', error);
      message.error('Failed to load layers');
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const response = await apiClient.get('/eh/detection/stats', {
        params: { session_id: sessionId }
      });

      setStats(response.data);
    } catch (error) {
      console.error('Failed to load stats:', error);
    }
  };

  const handleClassify = async (classification) => {
    if (selectedLayers.length === 0) {
      message.warning('Please select at least one layer');
      return;
    }

    try {
      await apiClient.post('/eh/detection/classify', {
        session_id: sessionId,
        layer_ids: selectedLayers,
        classification: classification
      });

      // Update local layer states
      setLayers(layers.map(layer =>
        selectedLayers.includes(layer.id)
          ? { ...layer, classification }
          : layer
      ));

      // Reload stats
      await loadStats();

      message.success(`Classified ${selectedLayers.length} layer(s) as '${classification}'`);
      setSelectedLayers([]);
    } catch (error) {
      console.error('Failed to classify layers:', error);
      message.error('Failed to classify layers');
    }
  };

  const handleLayerSelect = (layerId, e) => {
    // If Ctrl or Shift is pressed, or if clicking the card normally (selection mode)
    // We'll treat clicking the thumbnail as "Inspection" and clicking the card body as "Selection"
    // OR we just use a specific area for selection.
    // For simplicity, let's say normal click opens the editor, and we use the Badge/Checkbox for selection?
    // Actually, the user said "On clicking any, open a high-resolution...".
    // So click = Inspection.

    // We'll pass both to LayerGrid and let it decide.
  };

  const handleOpenEditor = (layer) => {
    setEditingLayer(layer);
  };

  const selectAllLayers = () => {
    const allLayerIds = layers.map(l => l.id);
    setSelectedLayers(allLayerIds);
  };

  const clearSelection = () => {
    setSelectedLayers([]);
  };

  const handlePageChange = (page) => {
    setCurrentPage(page);
    setSelectedLayers([]); // Clear selection when changing pages
  };

  // Show dataset loader if no session
  if (!sessionId) {
    return (
      <div style={{ padding: '24px' }}>
        <DatasetLoader onLoad={handleDatasetLoad} loading={loading} />
      </div>
    );
  }

  // Show main detection interface
  return (
    <Layout style={{ height: 'calc(100vh - 200px)', background: '#fff' }}>
      {/* Left Panel: Progress Tracker */}
      <Sider
        width="20%"
        theme="light"
        style={{
          borderRight: '1px solid #f0f0f0',
          minWidth: '250px',
          maxWidth: '350px'
        }}
      >
        <ProgressTracker
          stats={stats}
          projectName={projectName}
          totalLayers={totalLayers}
          onNewSession={() => {
            setSessionId(null);
            setSelectedLayers([]);
          }}
          onStartProofreading={() => {
            // Find first incorrect layer and open it
            const firstIncorrect = layers.find(l => l.classification === 'incorrect');
            if (firstIncorrect) {
              setEditingLayer(firstIncorrect);
            } else {
              message.info('No incorrect layers visible on this page. Try scrolling or filtering.');
            }
          }}
        />
      </Sider>

      {/* Center: Layer Grid */}
      <Content style={{ padding: '16px', background: '#fafafa', overflow: 'auto' }}>
        {loading ? (
          <div style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: '100%'
          }}>
            <Spin size="large" tip="Loading layers..." />
          </div>
        ) : (
          <LayerGrid
            layers={layers}
            selectedLayers={selectedLayers}
            onLayerSelect={(layerId) => {
              setSelectedLayers(prev =>
                prev.includes(layerId)
                  ? prev.filter(id => id !== layerId)
                  : [...prev, layerId]
              );
            }}
            onLayerClick={(layer) => setEditingLayer(layer)}
            currentPage={currentPage}
            totalPages={Math.ceil(totalLayers / pageSize)}
            onPageChange={handlePageChange}
          />
        )}
      </Content>

      {/* Right Panel: Classification Controls */}
      <Sider
        width="20%"
        theme="light"
        style={{
          borderLeft: '1px solid #f0f0f0',
          minWidth: '250px',
          maxWidth: '350px'
        }}
      >
        <ClassificationPanel
          selectedCount={selectedLayers.length}
          onClassify={handleClassify}
          onSelectAll={selectAllLayers}
          onClearSelection={clearSelection}
        />
      </Sider>

      {/* Integrated Image Editor Modal */}
      <UnifiedImageEditor
        visible={!!editingLayer}
        layer={editingLayer}
        sessionId={sessionId}
        onClose={() => setEditingLayer(null)}
        onSaveSuccess={() => {
          loadLayers();
          loadStats();
        }}
      />
    </Layout>
  );
}

export default DetectionWorkflow;
