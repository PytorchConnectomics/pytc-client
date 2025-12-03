import React, { useState, useContext, useEffect } from 'react';
import { Card, Button, Input, Modal, Typography, message, Space } from 'antd';
import { UserOutlined, LockOutlined, RocketOutlined } from '@ant-design/icons';
import { UserContext } from '../contexts/UserContext';

const { Title, Text } = Typography;

function Welcome() {
  const { signIn, signUp, autoSignOut } = useContext(UserContext);
  const [showSignIn, setShowSignIn] = useState(false);
  const [showSignUp, setShowSignUp] = useState(false);
  const [signInName, setSignInName] = useState('');
  const [signInPassword, setSignInPassword] = useState('');
  const [signUpName, setSignUpName] = useState('');
  const [signUpPassword, setSignUpPassword] = useState('');

  useEffect(() => {
    autoSignOut();
  }, [autoSignOut]);

  const handleSignIn = async () => {
    const ok = await signIn(signInName, signInPassword);
    if (!ok) message.error('Invalid credentials');
    setShowSignIn(false);
  };

  const handleSignUp = async () => {
    const ok = await signUp(signUpName, signUpPassword);
    if (!ok) message.error('Sign up failed');
    setShowSignUp(false);
  };

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
            onClick={() => setShowSignIn(true)}
          >
            Sign In
          </Button>
          <Button
            size='large'
            block
            style={{
              height: 48,
              fontSize: 16,
              borderRadius: 8,
              borderColor: '#d9d9d9'
            }}
            onClick={() => setShowSignUp(true)}
          >
            Create Account
          </Button>
        </Space>

        <div style={{ marginTop: 32, borderTop: '1px solid #f0f0f0', paddingTop: 16 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            &copy; {new Date().getFullYear()} PyTC Client. All rights reserved.
          </Text>
        </div>
      </Card>

      {/* Sign In Modal */}
      <Modal
        title={<div style={{ textAlign: 'center', marginBottom: 20 }}>Sign In</div>}
        open={showSignIn}
        onCancel={() => setShowSignIn(false)}
        onOk={handleSignIn}
        okText='Sign In'
        centered
        width={360}
        okButtonProps={{ style: { background: '#764ba2', borderColor: '#764ba2' } }}
      >
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Input
            size="large"
            placeholder='Username'
            prefix={<UserOutlined style={{ color: '#bfbfbf' }} />}
            value={signInName}
            onChange={e => setSignInName(e.target.value)}
          />
          <Input.Password
            size="large"
            placeholder='Password'
            prefix={<LockOutlined style={{ color: '#bfbfbf' }} />}
            value={signInPassword}
            onChange={e => setSignInPassword(e.target.value)}
            onPressEnter={handleSignIn}
          />
        </Space>
      </Modal>

      {/* Sign Up Modal */}
      <Modal
        title={<div style={{ textAlign: 'center', marginBottom: 20 }}>Create Account</div>}
        open={showSignUp}
        onCancel={() => setShowSignUp(false)}
        onOk={handleSignUp}
        okText='Sign Up'
        centered
        width={360}
        okButtonProps={{ style: { background: '#764ba2', borderColor: '#764ba2' } }}
      >
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Input
            size="large"
            placeholder='Choose Username'
            prefix={<UserOutlined style={{ color: '#bfbfbf' }} />}
            value={signUpName}
            onChange={e => setSignUpName(e.target.value)}
          />
          <Input.Password
            size="large"
            placeholder='Choose Password'
            prefix={<LockOutlined style={{ color: '#bfbfbf' }} />}
            value={signUpPassword}
            onChange={e => setSignUpPassword(e.target.value)}
            onPressEnter={handleSignUp}
          />
        </Space>
      </Modal>
    </div>
  );
}

export default Welcome;
