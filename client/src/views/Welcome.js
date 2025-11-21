import React, { useState, useContext, useEffect } from 'react';
import { Modal, Button, Input, Card, Typography, message } from 'antd';
import { UserContext } from '../contexts/UserContext';

const { Title, Paragraph } = Typography;

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
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'linear-gradient(135deg, #e0e7ff 0%, #f5f7fa 100%)' }}>
      <Card style={{ maxWidth: 420, width: '100%', textAlign: 'center', boxShadow: '0 8px 32px #0001' }}>
        <Title level={2} style={{ marginBottom: 8 }}>Pytc Client</Title>
        <Paragraph style={{ fontSize: 18, marginBottom: 24 }}>
          Welcome to Pytc Client!<br />A modern interface for connectomics workflows.<br />Sign in or sign up to get started.
        </Paragraph>
        <Button type='primary' size='large' style={{ margin: 8 }} onClick={() => setShowSignIn(true)}>Sign In</Button>
        <Button size='large' style={{ margin: 8 }} onClick={() => setShowSignUp(true)}>Sign Up</Button>
      </Card>
      <Modal title='Sign In' open={showSignIn} onCancel={() => setShowSignIn(false)} onOk={handleSignIn} okText='Sign In'>
        <Input placeholder='Username' value={signInName} onChange={e => setSignInName(e.target.value)} style={{ marginBottom: 12 }} />
        <Input.Password placeholder='Password' value={signInPassword} onChange={e => setSignInPassword(e.target.value)} />
      </Modal>
      <Modal title='Sign Up' open={showSignUp} onCancel={() => setShowSignUp(false)} onOk={handleSignUp} okText='Sign Up'>
        <Input placeholder='Username' value={signUpName} onChange={e => setSignUpName(e.target.value)} style={{ marginBottom: 12 }} />
        <Input.Password placeholder='Password' value={signUpPassword} onChange={e => setSignUpPassword(e.target.value)} />
      </Modal>
    </div>
  );
}

export default Welcome;
        <Paragraph style={{ fontSize: 16, marginBottom: 24 }}>
          A desktop client for connectomics workflows — visualize data, run inference, and manage experiments.
        </Paragraph>
        <Paragraph style={{ color: '#555', marginBottom: 28 }}>
          Welcome — get started by signing in or creating a new account.
        </Paragraph>
        <Space size='large'>
          <Button type='primary' size='large' onClick={() => { console.log('Sign in clicked'); setSignInOpen(true); }}>Sign in</Button>
          <Button size='large' onClick={() => { console.log('Sign up clicked'); setSignUpOpen(true); }}>Sign up</Button>
        </Space>

        <Modal
          title='Sign in'
          open={isSignInOpen}
          onCancel={() => setSignInOpen(false)}
          footer={null}
        >
          <Form layout='vertical' onFinish={onSignIn}>
            <Form.Item name='name' label='Name' rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            <Form.Item name='password' label='Password' rules={[{ required: true }]}>
              <Input.Password />
            </Form.Item>
            <Form.Item>
              <Button type='primary' htmlType='submit' block>Sign in</Button>
            </Form.Item>
          </Form>
        </Modal>

        <Modal
          title='Create account'
          open={isSignUpOpen}
          onCancel={() => setSignUpOpen(false)}
          footer={null}
        >
          <Form layout='vertical' onFinish={onSignUp}>
            <Form.Item name='name' label='Name' rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            <Form.Item name='password' label='Password' rules={[{ required: true, min: 6 }]}>
              <Input.Password />
            </Form.Item>
            <Form.Item>
              <Button type='primary' htmlType='submit' block>Create account</Button>
            </Form.Item>
          </Form>
        </Modal>
      </div>
    </div>
  )
}

export default Welcome
