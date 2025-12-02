import React, { useState, useEffect } from 'react';
import { Button, Input, Space, Typography, Divider } from 'antd';
import { CheckOutlined, CloseOutlined, QuestionOutlined, ArrowRightOutlined } from '@ant-design/icons';

const { Text } = Typography;

/**
 * ProofreadingControls Component
 * 
 * Provides UI controls for classifying synapses and editing neuron IDs.
 * Includes status buttons, input fields, and save/navigation buttons.
 * 
 * @param {object} currentSynapse - Currently selected synapse
 * @param {function} onSave - Callback to save changes
 * @param {function} onNext - Callback to navigate to next synapse
 */
function ProofreadingControls({ currentSynapse, onSave, onNext }) {
  const [status, setStatus] = useState('error');
  const [preNeuronId, setPreNeuronId] = useState('');
  const [postNeuronId, setPostNeuronId] = useState('');

  // Update local state when current synapse changes
  useEffect(() => {
    if (currentSynapse) {
      setStatus(currentSynapse.status);
      setPreNeuronId(currentSynapse.pre_neuron_id || '');
      setPostNeuronId(currentSynapse.post_neuron_id || '');
    }
  }, [currentSynapse]);

  const handleSave = async () => {
    const updates = {
      status,
      pre_neuron_id: preNeuronId ? parseInt(preNeuronId) : null,
      post_neuron_id: postNeuronId ? parseInt(postNeuronId) : null
    };

    await onSave(updates);
  };

  const handleSaveAndNext = async () => {
    await handleSave();
    onNext();
  };

  if (!currentSynapse) {
    return (
      <div style={{ padding: '16px', textAlign: 'center' }}>
        <Text type="secondary">No synapse selected</Text>
      </div>
    );
  }

  return (
    <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Current Synapse Info */}
      <div>
        <Text strong style={{ fontSize: '14px' }}>Synapse #{currentSynapse.id}</Text>
        <div style={{ marginTop: '8px' }}>
          <Text type="secondary" style={{ fontSize: '12px', display: 'block' }}>
            Position: ({currentSynapse.x.toFixed(1)}, {currentSynapse.y.toFixed(1)}, {currentSynapse.z.toFixed(1)})
          </Text>
          {currentSynapse.confidence && (
            <Text type="secondary" style={{ fontSize: '12px', display: 'block' }}>
              Confidence: {(currentSynapse.confidence * 100).toFixed(0)}%
            </Text>
          )}
        </div>
      </div>

      <Divider style={{ margin: '0' }} />

      {/* Status Classification */}
      <div>
        <Text strong style={{ display: 'block', marginBottom: '12px' }}>Status Classification</Text>
        <Space direction="vertical" style={{ width: '100%' }} size="small">
          <Button
            block
            type={status === 'correct' ? 'primary' : 'default'}
            icon={<CheckOutlined />}
            onClick={() => setStatus('correct')}
            style={{
              backgroundColor: status === 'correct' ? '#52c41a' : undefined,
              borderColor: status === 'correct' ? '#52c41a' : undefined
            }}
          >
            Correct (C)
          </Button>
          <Button
            block
            type={status === 'incorrect' ? 'primary' : 'default'}
            danger={status === 'incorrect'}
            icon={<CloseOutlined />}
            onClick={() => setStatus('incorrect')}
          >
            Incorrect (X)
          </Button>
          <Button
            block
            type={status === 'unsure' ? 'primary' : 'default'}
            icon={<QuestionOutlined />}
            onClick={() => setStatus('unsure')}
            style={{
              backgroundColor: status === 'unsure' ? '#faad14' : undefined,
              borderColor: status === 'unsure' ? '#faad14' : undefined,
              color: status === 'unsure' ? '#fff' : undefined
            }}
          >
            Unsure (U)
          </Button>
        </Space>
      </div>

      <Divider style={{ margin: '0' }} />

      {/* Neuron ID Inputs */}
      <div>
        <Text strong style={{ display: 'block', marginBottom: '8px' }}>Pre-synaptic Neuron ID</Text>
        <Input
          value={preNeuronId}
          onChange={(e) => setPreNeuronId(e.target.value)}
          placeholder="Enter neuron ID"
          type="number"
        />
      </div>

      <div>
        <Text strong style={{ display: 'block', marginBottom: '8px' }}>Post-synaptic Neuron ID</Text>
        <Input
          value={postNeuronId}
          onChange={(e) => setPostNeuronId(e.target.value)}
          placeholder="Enter neuron ID"
          type="number"
        />
      </div>

      <Divider style={{ margin: '0' }} />

      {/* Action Buttons */}
      <Space direction="vertical" style={{ width: '100%' }} size="small">
        <Button block onClick={handleSave}>
          Save (S)
        </Button>
        <Button
          block
          type="primary"
          icon={<ArrowRightOutlined />}
          onClick={handleSaveAndNext}
        >
          Save & Next (→)
        </Button>
      </Space>
    </div>
  );
}

export default ProofreadingControls;
