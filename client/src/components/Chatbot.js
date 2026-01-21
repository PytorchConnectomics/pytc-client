import React, { useEffect, useState, useRef } from 'react'
import { Button, Input, List, Typography, Space, Spin, Popconfirm } from 'antd'
import { SendOutlined, CloseOutlined, DeleteOutlined } from '@ant-design/icons'
import { queryChatBot, clearChat } from '../utils/api'
import ReactMarkdown from 'react-markdown'

const { TextArea } = Input
const { Text } = Typography
const initialMessage = [{ id: 1, text: "Hello! I'm your AI assistant. How can I help you today?", isUser: false }]

function Chatbot({ onClose }) {
  const [messages, setMessages] = useState(() => {
    const saved = localStorage.getItem('chatMessages')
    return saved ? JSON.parse(saved) : initialMessage
  })
  const [inputValue, setInputValue] = useState('')
  const [isSending, setIsSending] = useState(false)
  const lastMessageRef = useRef(null)

  const scrollToLastMessage = () => {
    setTimeout(() => {
      if (lastMessageRef.current) {
        lastMessageRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    }, 0)
  }

  useEffect(() => {
    localStorage.setItem('chatMessages', JSON.stringify(messages))
  }, [messages])

  useEffect(() => {
    scrollToLastMessage()
  }, [messages, isSending])

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isSending) return
    const query = inputValue
    setInputValue('')
    const userMessage = { id: messages.length + 1, text: query, isUser: true }
    setMessages(prev => [...prev, userMessage])
    setIsSending(true)
    try {
      const responseText = await queryChatBot(query)
      const botMessage = { id: userMessage.id + 1, text: responseText || 'Sorry, I could not generate a response.', isUser: false }
      setMessages(prev => [...prev, botMessage])
    } catch (e) {
      setMessages(prev => [...prev, { id: prev.length + 1, text: 'Error contacting chatbot.', isUser: false }])
    } finally {
      setIsSending(false)
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const handleClearChat = async () => {
    try {
      await clearChat()
      setMessages(initialMessage)
      localStorage.setItem('chatMessages', JSON.stringify(initialMessage))
    } catch (e) {
      console.error('Failed to clear chat:', e)
    }
  }

  return (
    <div
      style={{
        height: '100%',
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden'
      }}
    >
      <div
        style={{
          padding: '16px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <Text strong>AI Assistant</Text>
        <Space>
          <Popconfirm
            title="Clear chat history"
            onConfirm={handleClearChat}
            okText="Clear"
            cancelText="Cancel"
          >
            <Button
              type="text"
              icon={<DeleteOutlined />}
              size="small"
            />
          </Popconfirm>
          <Button
            type="text"
            icon={<CloseOutlined />}
            onClick={onClose}
            size="small"
          />
        </Space>
      </div>
      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflow: 'auto',
          padding: '16px',
        }}
      >
        <List
          dataSource={messages}
          renderItem={(message, index) => {
            const isLastMessage = index === messages.length - 1
            return (
              <List.Item
                ref={isLastMessage ? lastMessageRef : null}
                style={{
                  border: 'none',
                  padding: '8px 0',
                  justifyContent: message.isUser ? 'flex-end' : 'flex-start'
                }}
              >
              <div
                style={{
                  maxWidth: '80%',
                  padding: '8px 12px',
                  borderRadius: '12px',
                  backgroundColor: message.isUser ? '#1890ff' : '#f5f5f5',
                  color: message.isUser ? 'white' : 'black',

                }}
              >
                {message.isUser ? (
                  <Text style={{ color: 'white' }}>
                    {message.text}
                  </Text>
                ) : (
                  <ReactMarkdown
                    components={{
                      ul: ({ children }) => <ul style={{ paddingLeft: '20px' }}>{children}</ul>,
                      ol: ({ children }) => <ol style={{ paddingLeft: '20px' }}>{children}</ol>
                    }}
                  >
                    {message.text}
                  </ReactMarkdown>
                )}
              </div>
            </List.Item>
            )
          }}
        />
        {isSending && (
          <Spin size="small" />
        )}
      </div>
      <div style={{ padding: '16px' }}>
        <Space.Compact style={{ width: '100%' }}>
          <TextArea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your message..."
            autoSize={{ minRows: 1, maxRows: 3 }}
          />
          <Button
            icon={<SendOutlined />}
            onClick={handleSendMessage}
            disabled={!inputValue.trim() || isSending}
          />
        </Space.Compact>
      </div>
    </div>
  )
}

export default Chatbot
