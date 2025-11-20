import React, { useState, useContext, useEffect } from 'react'
import { Button, Typography, Space, Modal, Form, Input, message } from 'antd'
import { UserContext } from '../contexts/UserContext'

const { Title, Paragraph } = Typography

function Welcome () {
  const { createUser, authenticate } = useContext(UserContext)
  const [isSignInOpen, setSignInOpen] = useState(false)
  const [isSignUpOpen, setSignUpOpen] = useState(false)

  useEffect(() => {
    console.log('Debug: Welcome component rendered')
  }, [])

  const onSignUp = async (values) => {
    try {
      await createUser(values.name, values.password)
      message.success('Account created — signed in')
      setSignUpOpen(false)
    } catch (e) {
      message.error(e.message || 'Failed to create account')
    }
  }

  const onSignIn = async (values) => {
    try {
      await authenticate(values.name, values.password)
      message.success('Signed in')
      setSignInOpen(false)
    } catch (e) {
      message.error(e.message || 'Sign in failed')
    }
  }

  return (
    <div className='welcome-container'>
      <div className='welcome-card'>
        {/* Debug message removed */}
        <Title level={1} style={{ marginBottom: 8 }}>Pytorch Connectomics</Title>
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
