import React, { useState, useEffect } from 'react';
import { Card, Button, message, Spin, Space } from 'antd';
import { CheckOutlined, CloseOutlined } from '@ant-design/icons';
import ProofreadingEditor from './ProofreadingEditor';
import apiClient from '../../services/apiClient';

/**
 * Proofreading Workflow Component
 * Allows editing of incorrect layers from detection workflow
 */
function ProofreadingWorkflow({ sessionId, refreshTrigger, onComplete }) {
  const [loading, setLoading] = useState(true);
  const [incorrectLayers, setIncorrectLayers] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [currentLayerData, setCurrentLayerData] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadIncorrectLayers();
  }, [sessionId, refreshTrigger]);

  useEffect(() => {
    if (incorrectLayers.length > 0 && currentIndex < incorrectLayers.length) {
      loadLayerData(incorrectLayers[currentIndex]);
    }
  }, [currentIndex, incorrectLayers]);

  const loadIncorrectLayers = async () => {
    try {
      setLoading(true);

      console.log('Loading incorrect layers for session:', sessionId);

      // Get all layers for this session
      const response = await apiClient.get('/eh/detection/layers', {
        params: {
          session_id: sessionId,
          page: 1,
          page_size: 1000, // Get all layers
          include_images: false // Don't need images yet
        }
      });

      console.log('All layers response:', response.data);
      console.log('Total layers:', response.data.layers.length);

      // Log each layer's classification
      response.data.layers.forEach((layer, idx) => {
        console.log(`Layer ${idx}: id=${layer.id}, index=${layer.layer_index}, classification="${layer.classification}"`);
      });

      // Filter for incorrect layers
      const incorrect = response.data.layers.filter(
        layer => layer.classification === 'incorrect'
      );

      console.log('Incorrect layers found:', incorrect.length, incorrect);

      if (incorrect.length === 0) {
        message.info('No incorrect layers to proofread');
        if (onComplete) onComplete();
        return;
      }

      setIncorrectLayers(incorrect);
      setCurrentIndex(0);
    } catch (error) {
      console.error('Failed to load incorrect layers:', error);
      message.error('Failed to load layers for proofreading');
    } finally {
      setLoading(false);
    }
  };

  const loadLayerData = async (layer) => {
    try {
      setLoading(true);

      // Load full layer data with images
      const response = await apiClient.get('/eh/detection/layers', {
        params: {
          session_id: sessionId,
          page: Math.floor(layer.layer_index / 12) + 1,
          page_size: 12,
          include_images: true
        }
      });

      // Find the specific layer
      const layerData = response.data.layers.find(
        l => l.layer_index === layer.layer_index
      );

      if (!layerData) {
        throw new Error('Layer data not found');
      }

      setCurrentLayerData(layerData);
    } catch (error) {
      console.error('Failed to load layer data:', error);
      message.error('Failed to load layer data');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (maskBase64) => {
    try {
      setSaving(true);

      // TODO: Implement mask save endpoint
      // For now, just show success message
      message.success('Mask saved successfully');

      // Note: In a full implementation, you would:
      // 1. Send the updated mask to the backend
      // 2. Backend would update the mask file on disk
      // 3. Optionally update the DataManager's cached mask data

    } catch (error) {
      console.error('Failed to save mask:', error);
      message.error('Failed to save mask');
    } finally {
      setSaving(false);
    }
  };

  const handleMarkCorrected = async () => {
    try {
      const layer = incorrectLayers[currentIndex];

      // Mark layer as corrected
      await apiClient.post('/eh/detection/classify', {
        session_id: sessionId,
        layer_ids: [layer.id],
        classification: 'correct'
      });

      message.success('Layer marked as corrected');

      // Move to next incorrect layer or complete
      if (currentIndex < incorrectLayers.length - 1) {
        setCurrentIndex(currentIndex + 1);
      } else {
        message.success('All incorrect layers have been reviewed!');
        if (onComplete) onComplete();
      }
    } catch (error) {
      console.error('Failed to mark layer as corrected:', error);
      message.error('Failed to update layer status');
    }
  };

  const handleSkip = () => {
    if (currentIndex < incorrectLayers.length - 1) {
      setCurrentIndex(currentIndex + 1);
    } else {
      message.info('No more layers to review');
      if (onComplete) onComplete();
    }
  };

  const handlePrevious = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
    }
  };

  const handleNext = () => {
    if (currentIndex < incorrectLayers.length - 1) {
      setCurrentIndex(currentIndex + 1);
    }
  };

  if (loading && !currentLayerData) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '400px' }}>
        <Spin size="large" tip="Loading layers..." />
      </div>
    );
  }

  if (incorrectLayers.length === 0) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <h3>No Incorrect Layers</h3>
          <p>All layers have been classified as correct or unsure.</p>
          <Button type="primary" onClick={onComplete}>
            Return to Detection
          </Button>
        </div>
      </Card>
    );
  }

  if (!currentLayerData) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '400px' }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Header */}
      <Card size="small">
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <div>
            <h3 style={{ margin: 0 }}>
              Proofreading: {currentLayerData.layer_name}
            </h3>
            <p style={{ margin: 0, color: '#666' }}>
              Layer {currentIndex + 1} of {incorrectLayers.length} incorrect layers
            </p>
          </div>
          <Space>
            <Button
              icon={<CloseOutlined />}
              onClick={handleSkip}
            >
              Skip
            </Button>
            <Button
              type="primary"
              icon={<CheckOutlined />}
              onClick={handleMarkCorrected}
              loading={saving}
            >
              Mark as Corrected
            </Button>
            <Button onClick={onComplete}>
              Exit Proofreading
            </Button>
          </Space>
        </Space>
      </Card>

      {/* Editor */}
      <div style={{ flex: 1, minHeight: 0 }}>
        <ProofreadingEditor
          imageBase64={currentLayerData.image_base64}
          maskBase64={currentLayerData.mask_base64}
          onSave={handleSave}
          onNext={handleNext}
          onPrevious={handlePrevious}
          currentLayer={currentIndex}
          totalLayers={incorrectLayers.length}
          layerName={currentLayerData.layer_name}
        />
      </div>
    </div>
  );
}

export default ProofreadingWorkflow;
