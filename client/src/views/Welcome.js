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
      background: 'linear-gradient(180deg, #f6f7f9 0%, #eef1f5 100%)',
      padding: 20
    }}>
      <Card
        style={{
          maxWidth: 480,
          width: '100%',
          textAlign: 'center',
          borderRadius: 12,
          boxShadow: '0 8px 24px rgba(0,0,0,0.08)',
          border: '1px solid #f0f0f0',
          overflow: 'hidden'
        }}
        bodyStyle={{ padding: '40px 32px' }}
      >
        <div style={{ marginBottom: 24 }}>
          <div style={{
            width: 80,
            height: 80,
            background: '#e6f4ff',
            borderRadius: 12,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 16px',
            color: '#1677ff',
            fontSize: 32,
            border: '1px solid #d6e4ff'
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
              borderRadius: 8
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
