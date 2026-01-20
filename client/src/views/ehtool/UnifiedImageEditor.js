import React, { useState, useEffect, useRef } from 'react';
import { Modal, Button, Radio, Space, Divider, message } from 'antd';
import { SaveOutlined, CheckCircleOutlined, CloseCircleOutlined, QuestionCircleOutlined } from '@ant-design/icons';
import ProofreadingEditor from './ProofreadingEditor';
import apiClient from '../../services/apiClient';

/**
 * Unified Image Editor Component
 * Combines mask editing with quality labeling in a full-screen-ish modal
 */
function UnifiedImageEditor({ visible, layer, sessionId, onClose, onSaveSuccess }) {
  const [currentLabel, setCurrentLabel] = useState('error');
  const [saving, setSaving] = useState(false);
  const editorRef = useRef(null);

  useEffect(() => {
    if (layer) {
      setCurrentLabel(layer.classification || 'error');
    }
  }, [layer, visible]);

  // Keyboard shortcuts for Modal
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (!visible) return;

      // Prevent shortcuts when typing in input fields
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

      switch (e.key.toLowerCase()) {
        case 's':
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            handleTriggerSave();
          }
          break;
        case 'c':
          setCurrentLabel('correct');
          break;
        case 'x':
          setCurrentLabel('incorrect');
          break;
        case 'u':
          setCurrentLabel('unsure');
          break;
        case 'escape':
          onClose();
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [visible, currentLabel]);

  if (!layer) return null;

  const handleTriggerSave = () => {
    if (editorRef.current) {
      editorRef.current.save();
    }
  };

  const handleSave = async (maskBase64) => {
    setSaving(true);
    try {
      // 1. Save Mask
      await apiClient.post('/eh/detection/mask', {
        session_id: sessionId,
        layer_index: layer.layer_index,
        mask_base64: maskBase64
      });

      // 2. Save Classification
      await apiClient.post('/eh/detection/classify', {
        session_id: sessionId,
        layer_ids: [layer.id],
        classification: currentLabel
      });

      message.success('Layer updated successfully');
      if (onSaveSuccess) onSaveSuccess();
      onClose();
    } catch (error) {
      console.error('Failed to save layer updates:', error);
      message.error(error.response?.data?.detail || 'Failed to save changes');
    } finally {
      setSaving(false);
    }
  };

  const handleLabelChange = (e) => {
    setCurrentLabel(e.target.value);
  };

  return (
    <Modal
      title={
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingRight: '24px' }}>
          <span>Image Inspection: {layer.layer_name} (Layer {layer.layer_index + 1})</span>
          <Space>
            <Radio.Group value={currentLabel} onChange={handleLabelChange} buttonStyle="solid">
              <Radio.Button value="correct">
                <CheckCircleOutlined /> Correct (C)
              </Radio.Button>
              <Radio.Button value="incorrect">
                <CloseCircleOutlined /> Incorrect (X)
              </Radio.Button>
              <Radio.Button value="unsure">
                <QuestionCircleOutlined /> Unsure (U)
              </Radio.Button>
            </Radio.Group>
            <Divider type="vertical" />
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={handleTriggerSave}
              loading={saving}
            >
              Save (S)
            </Button>
          </Space>
        </div>
      }
      open={visible}
      onCancel={onClose}
      width="95%"
      style={{ top: 20 }}
      footer={null}
      destroyOnClose
      maskClosable={false}
      keyboard={true}
      bodyStyle={{ padding: '12px', height: 'calc(100vh - 120px)', overflow: 'hidden' }}
    >
      <div style={{ height: '100%', overflow: 'hidden' }}>
        <ProofreadingEditor
          ref={editorRef}
          imageBase64={layer.image_base64}
          maskBase64={layer.mask_base64}
          onSave={handleSave}
          layerName={layer.layer_name}
          currentLayer={layer.layer_index}
          totalLayers={1}
        />
      </div>
    </Modal>
  );
}

export default UnifiedImageEditor;
