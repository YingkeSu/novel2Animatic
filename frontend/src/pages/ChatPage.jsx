import React, { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import useStore from '../stores/auth'
import api from '../services/api'

/**
 * ChatPage — Chat-centric workbench with three-column layout.
 *
 * Layout:
 * ┌──────────┬────────────────────────┬──────────┐
 * │ Sidebar  │ Chat Area              │ Context  │
 * │ (260px)  │ (flex-1)               │ (300px)  │
 * └──────────┴────────────────────────┴──────────┘
 *
 * Inspired by InkOS Studio's ChatPage design.
 */
export default function ChatPage() {
  const { id: projectId } = useParams()
  const navigate = useNavigate()
  const token = useStore((s) => s.token)

  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [projects, setProjects] = useState([])
  const [currentProject, setCurrentProject] = useState(null)
  const [contextPanelOpen, setContextPanelOpen] = useState(false)
  const [selectedScene, setSelectedScene] = useState(null)
  const messagesEndRef = useRef(null)

  // Load projects list
  useEffect(() => {
    api.get('/api/projects').then(res => setProjects(res.data)).catch(() => {})
  }, [])

  // Load current project if projectId provided
  useEffect(() => {
    if (projectId) {
      api.get(`/api/projects/${projectId}`).then(res => {
        setCurrentProject(res.data)
        // Add initial system message
        setMessages([{
          id: 'system-1',
          role: 'system',
          content: `已加载项目「${res.data.title}」。你可以输入文本创建新场景，或使用快捷操作。`,
          parts: [{ type: 'text', content: `已加载项目「${res.data.title}」。你可以输入文本创建新场景，或使用快捷操作。` }],
        }])
      }).catch(() => {})
    }
  }, [projectId])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || loading) return

    const userMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: input,
      parts: [{ type: 'text', content: input }],
    }
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      // For now, simulate a response (will integrate with backend later)
      const assistantMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: `收到你的消息：「${input}」。正在处理中...`,
        parts: [{ type: 'text', content: `收到你的消息：「${input}」。正在处理中...` }],
      }
      setMessages(prev => [...prev, assistantMessage])
    } catch (err) {
      console.error('Failed to send message:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="chat-page">
      {/* Left Sidebar */}
      <aside className="chat-sidebar" data-testid="chat-sidebar">
        <div className="sidebar-header">
          <div className="sidebar-logo" onClick={() => navigate('/')}>
            <span className="logo-icon">🎬</span>
            <span className="logo-text">novel2Animatic</span>
          </div>
        </div>

        <div className="sidebar-projects">
          <div className="sidebar-section-title">项目列表</div>
          {projects.map(p => (
            <div
              key={p.id}
              className={`sidebar-project-item ${currentProject?.id === p.id ? 'active' : ''}`}
              onClick={() => navigate(`/chat/project/${p.id}`)}
            >
              <span className="project-title">{p.title}</span>
              <span className={`project-status status-${p.status}`}>{p.status}</span>
            </div>
          ))}
          <button
            className="sidebar-new-project"
            onClick={() => navigate('/create')}
          >
            + 新建项目
          </button>
        </div>

        <div className="sidebar-actions">
          <button onClick={() => navigate('/')}>📊 Dashboard</button>
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="chat-main" data-testid="chat-main">
        <div className="chat-messages">
          {messages.length === 0 && (
            <div className="chat-welcome">
              <h2>🎬 novel2Animatic</h2>
              <p>输入文段或使用快捷操作来创建动画场景</p>
              <div className="quick-actions">
                <button onClick={() => setInput('帮我生成一个古风场景')}>🏛️ 古风场景</button>
                <button onClick={() => setInput('生成科幻风格动画')}>🚀 科幻风格</button>
                <button onClick={() => setInput('查看当前项目状态')}>📋 项目状态</button>
              </div>
            </div>
          )}
          {messages.map(msg => (
            <div key={msg.id} className={`chat-message message-${msg.role}`}>
              <div className="message-avatar">
                {msg.role === 'user' ? '👤' : msg.role === 'system' ? '⚙️' : '🤖'}
              </div>
              <div className="message-content">
                {msg.parts.map((part, i) => (
                  <div key={i} className={`message-part part-${part.type}`}>
                    {part.type === 'text' && <p>{part.content}</p>}
                    {part.type === 'tool' && (
                      <div className="tool-execution-card">
                        <span className="tool-name">{part.name}</span>
                        <span className={`tool-status status-${part.status}`}>{part.status}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
          {loading && (
            <div className="chat-message message-assistant">
              <div className="message-avatar">🤖</div>
              <div className="message-content">
                <div className="typing-indicator">
                  <span>●</span><span>●</span><span>●</span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="chat-input-area">
          <div className="input-wrapper">
            <textarea
              className="chat-input"
              placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
            />
            <button
              className="send-button"
              onClick={handleSend}
              disabled={!input.trim() || loading}
            >
              发送
            </button>
          </div>
        </div>
      </main>

      {/* Right Context Panel */}
      <aside className={`context-panel ${contextPanelOpen ? 'open' : ''}`} data-testid="context-panel">
        <button
          className="context-panel-toggle"
          onClick={() => setContextPanelOpen(!contextPanelOpen)}
        >
          {contextPanelOpen ? '✕' : '◀'}
        </button>
        {contextPanelOpen && currentProject && (
          <div className="context-panel-content">
            <h3>{currentProject.title}</h3>
            <div className="context-section">
              <div className="context-section-title">场景列表</div>
              {currentProject.scenes?.map((scene, i) => (
                <div
                  key={i}
                  className={`context-scene-item ${selectedScene === i ? 'active' : ''}`}
                  onClick={() => setSelectedScene(i)}
                >
                  <span className="scene-number">{i + 1}</span>
                  <span className="scene-title">{scene.title || `场景 ${i + 1}`}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </aside>
    </div>
  )
}
