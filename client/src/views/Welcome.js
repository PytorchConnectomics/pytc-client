import React, { useContext, useEffect } from 'react';
import { Card, Button, Typography, Space } from 'antd';
import { RocketOutlined } from '@ant-design/icons';
import { UserContext } from '../contexts/UserContext';

const { Title, Text } = Typography;

function Welcome() {
  const { signIn, autoSignOut } = useContext(UserContext);

  useEffect(() => {
    autoSignOut();
  }, [autoSignOut]);

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      padding: 20
    }}>
      <Card
        style={{
          maxWidth: 480,
          width: '100%',
          textAlign: 'center',
          borderRadius: 16,
          boxShadow: '0 10px 25px rgba(0,0,0,0.2)',
          border: 'none',
          overflow: 'hidden'
        }}
        bodyStyle={{ padding: '40px 32px' }}
      >
        <div style={{ marginBottom: 24 }}>
          <div style={{
            width: 80,
            height: 80,
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 16px',
            color: 'white',
            fontSize: 32,
            boxShadow: '0 4px 10px rgba(118, 75, 162, 0.3)'
          }}>
            <RocketOutlined />
          </div>
          <Title level={2} style={{ marginBottom: 8, color: '#333' }}>PyTC Client</Title>
          <Text type="secondary" style={{ fontSize: 16 }}>
            Advanced Connectomics Workflow Interface
          </Text>
        </div>

        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Button
            type='primary'
            size='large'
            block
            style={{
              height: 48,
              fontSize: 16,
              borderRadius: 8,
              background: 'linear-gradient(90deg, #667eea 0%, #764ba2 100%)',
              border: 'none'
            }}
            onClick={signIn}
          >
            Enter as Guest
          </Button>
        </Space>

        <div style={{ marginTop: 32, borderTop: '1px solid #f0f0f0', paddingTop: 16 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            &copy; {new Date().getFullYear()} PyTC Client. All rights reserved.
          </Text>
        </div>
      </Card>

    </div>
  );
}

export default Welcome;
