import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import useStore from '../stores/auth'
import api from '../services/api'
import useSSE from '../hooks/useSSE'

const SOURCE_TYPES = [
  { key: 'text_split', label: '📝 文本拆分', desc: '输入长文本，AI 自动拆分成场景' },
  { key: 'short_fiction', label: '📖 短篇小说', desc: 'AI 三明治 pipeline 生成完整故事' },
  { key: 'play_world', label: '🌍 开放世界', desc: '交互式文字冒险，每回合推进剧情' },
]

const STATUS_LABELS = {
  created: '待生成',
  running: '生成中',
  done: '已完成',
  failed: '失败',
}

export default function ChatPage() {
  const { id: projectId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const token = useStore((s) => s.token)

  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [projects, setProjects] = useState([])
  const [currentProject, setCurrentProject] = useState(null)
  const [contextPanelOpen, setContextPanelOpen] = useState(false)
  const [selectedScene, setSelectedScene] = useState(null)
  const [sourceType, setSourceType] = useState(location.state?.sourceType || 'text_split')
  const [direction, setDirection] = useState('')
  const [suggestedActions, setSuggestedActions] = useState([])
  const messagesEndRef = useRef(null)

  // SSE-driven generation (issue #48): when a text_split / short_fiction run
  // is kicked off, sseProjectId holds the project id being watched. The
  // useSSE subscription delivers live progress + terminal events, replacing
  // the previous 5s polling loops. pendingGenRef resolves when the run
  // reaches a terminal state (complete/error).
  const [sseProjectId, setSseProjectId] = useState(null)
  const pendingGenRef = useRef(null)
  const seenStepRef = useRef('')

  const addMessage = useCallback((role, content) => {
    setMessages(prev => [...prev, {
      id: `${role}-${Date.now()}-${Math.random()}`,
      role,
      content,
      parts: [{ type: 'text', content }],
    }])
  }, [])

  const finalizeGeneration = useCallback(async (projectId, kind) => {
    // kind: 'done' | 'failed' — fetch the project to read final status/scenes.
    try {
      const detail = await api.get(`/projects/${projectId}`)
      const proj = detail.data
      if (kind === 'done') {
        const scenes = proj.scenes || []
        addMessage('assistant', `✅ 生成完成！共 ${scenes.length} 个场景。查看完整项目：/project/${projectId}`)
        for (const s of scenes.slice(0, 5)) {
          addMessage('system', `🎬 场景 ${s.seq}: ${s.title}\n${s.text?.substring(0, 80)}...`)
        }
        if (scenes.length > 5) {
          addMessage('system', `...还有 ${scenes.length - 5} 个场景，请查看项目详情`)
        }
      } else {
        addMessage('system', `❌ 生成失败: ${proj.latest_error_msg || '未知错误'}`)
      }
    } catch {
      if (kind === 'done') {
        addMessage('assistant', `✅ 生成完成。查看完整项目：/project/${projectId}`)
      } else {
        addMessage('system', '❌ 生成失败，请稍后查看项目状态')
      }
    }
    api.get('/projects').then(res => setProjects(res.data)).catch(() => {})
  }, [addMessage])

  const onSseEvent = useCallback((evt) => {
    if (!evt || !pendingGenRef.current) return
    const { projectId, resolve } = pendingGenRef.current
    if (evt.type === 'progress' && evt.data) {
      const { step, progress } = evt.data
      if (step && step !== seenStepRef.current) {
        seenStepRef.current = step
        addMessage('system', `⏳ ${step}... (${progress ?? 0}%)`)
      }
    } else if (evt.type === 'complete') {
      addMessage('system', '✅ 后台流水线已完成，正在加载结果...')
      finalizeGeneration(projectId, 'done').finally(() => {
        if (pendingGenRef.current) {
          const p = pendingGenRef.current
          pendingGenRef.current = null
          setSseProjectId(null)
          p.resolve()
        }
      })
    } else if (evt.type === 'error') {
      finalizeGeneration(projectId, 'failed').finally(() => {
        if (pendingGenRef.current) {
          const p = pendingGenRef.current
          pendingGenRef.current = null
          setSseProjectId(null)
          p.resolve()
        }
      })
    }
  }, [addMessage, finalizeGeneration])

  useSSE(sseProjectId, onSseEvent)

  // Run a generation to completion via SSE. Returns a promise that resolves on
  // a terminal event, with a hard safety-net timeout (the SSE is the primary
  // signal; this only guards against a permanently-silent stream so the UI is
  // never stuck "loading"). This is NOT polling /progress.
  const runGenerationViaSse = (projectId, { timeoutMs = 600000 } = {}) =>
    new Promise((resolve) => {
      seenStepRef.current = ''
      pendingGenRef.current = { projectId, resolve }
      setSseProjectId(String(projectId))
      // Safety net: if no terminal event ever arrives (e.g. SSE unreachable on
      // this client), fall back to a single recovery GET and resolve.
      const timer = setTimeout(() => {
        if (pendingGenRef.current && pendingGenRef.current.projectId === projectId) {
          pendingGenRef.current = null
          setSseProjectId(null)
          addMessage('system', '⏰ 实时连接超时，请稍后查看项目状态')
          api.get(`/projects/${projectId}`).then(res => {
            if (res.data.status === 'done') finalizeGeneration(projectId, 'done')
            else if (res.data.status === 'failed') finalizeGeneration(projectId, 'failed')
          }).catch(() => {}).finally(resolve)
        } else {
          resolve()
        }
      }, timeoutMs)
      // Clear the safety net when the SSE path resolves.
      const origResolve = resolve
      const wrapped = pendingGenRef.current
      wrapped.resolve = () => { clearTimeout(timer); origResolve() }
      pendingGenRef.current = wrapped
    })

  // Load projects list
  useEffect(() => {
    api.get('/projects').then(res => setProjects(res.data)).catch(() => {})
  }, [])

  // Load current project if projectId provided
  useEffect(() => {
    if (projectId) {
      api.get(`/projects/${projectId}`).then(res => {
        setCurrentProject(res.data)
        setSourceType(res.data.source_type || 'text_split')
        setMessages([{
          id: 'system-1',
          role: 'system',
          content: `已加载项目「${res.data.title}」（${res.data.source_type}）`,
          parts: [{ type: 'text', content: `已加载项目「${res.data.title}」（${res.data.source_type}）` }],
        }])
      }).catch(() => {})
    }
  }, [projectId])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const createProject = async (title, srcType, dir, srcText = '') => {
    const res = await api.post('/projects', {
      title,
      source_type: srcType,
      direction: dir,
      source_text: srcText,
      style_writing: 'modern',
      style_visual: 'ink_wash',
      style_audio: 'ancient_male',
    })
    return res.data
  }

  const handleSend = async () => {
    if (!input.trim() || loading) return

    const text = input.trim()
    addMessage('user', text)
    setInput('')
    setLoading(true)

    try {
      if (sourceType === 'short_fiction') {
        // Create project and generate
        addMessage('system', '正在创建项目并生成短篇小说...')
        const project = await createProject(text.substring(0, 50) || '短篇小说', 'short_fiction', text)
        addMessage('system', `项目「${project.title}」已创建，开始生成（预计 2-5 分钟）...`)

        // Start generation (async)
        await api.post(`/projects/${project.id}/generate`, {
          source_type: 'short_fiction',
          chapter_count: 3,
        })

        // Wait for completion via SSE (issue #48): live progress messages are
        // appended by onSseEvent; no polling of /progress.
        await runGenerationViaSse(project.id)

      } else if (sourceType === 'play_world') {
        // Play world mode
        if (!currentProject) {
          // Create a new play_world project
          addMessage('system', '正在创建开放世界项目...')
          const project = await createProject(text.substring(0, 50) || '开放世界', 'play_world', text)
          setCurrentProject(project)
          setSourceType('play_world')
          addMessage('system', `🌍 世界「${project.title}」已创建！输入你的第一个动作。`)
          api.get('/projects').then(res => setProjects(res.data)).catch(() => {})
          setLoading(false)
          return
        }

        // Execute a world turn
        addMessage('system', '正在执行回合...')
        const playRes = await api.post(`/projects/${currentProject.id}/play`, {
          raw_input: text,
          context: currentProject.direction || '未知世界',
        })
        const { scene_text, suggested_actions, turn, action_kind } = playRes.data
        addMessage('assistant', scene_text)
        setSuggestedActions(suggested_actions || [])

      } else {
        // text_split mode — create project and run pipeline
        if (text.length < 80) {
          addMessage('system', '⚠️ 文本拆分模式需要至少 80 个字符的文本。请粘贴更长的小说/文段内容。')
          setLoading(false)
          return
        }

        addMessage('system', '正在创建项目并启动文本拆分 pipeline...')
        const title = text.substring(0, 50).replace(/\n/g, ' ') || '文本拆分项目'
        const project = await createProject(title, 'text_split', '', text)
        addMessage('system', `项目「${title}」已创建，启动 pipeline（预计 3-8 分钟）...`)

        // Run pipeline
        await api.post(`/projects/${project.id}/run`)

        // Wait for completion via SSE (issue #48): live progress messages are
        // appended by onSseEvent; no polling of /progress.
        await runGenerationViaSse(project.id)
      }
    } catch (err) {
      console.error('Failed:', err)
      const detail = err.response?.data?.detail
      const msg = Array.isArray(detail) ? detail[0]?.msg || err.message : detail || err.message
      addMessage('system', `❌ 错误: ${msg}`)
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

        {/* Source Type Selector */}
        <div className="sidebar-projects">
          <div className="sidebar-section-title">生成方式</div>
          {SOURCE_TYPES.map(st => (
            <div
              key={st.key}
              className={`sidebar-project-item ${sourceType === st.key ? 'active' : ''}`}
              onClick={() => setSourceType(st.key)}
            >
              <span className="project-title">{st.label}</span>
            </div>
          ))}
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
              <span className={`project-status status-${p.status}`}>{STATUS_LABELS[p.status] || p.status}</span>
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
              <p>{SOURCE_TYPES.find(s => s.key === sourceType)?.desc}</p>
              <div className="quick-actions">
                {sourceType === 'short_fiction' && (
                  <>
                    <button onClick={() => setInput('古风爱情')}>🏛️ 古风爱情</button>
                    <button onClick={() => setInput('科幻冒险')}>🚀 科幻冒险</button>
                    <button onClick={() => setInput('悬疑推理')}>🔍 悬疑推理</button>
                  </>
                )}
                {sourceType === 'play_world' && (
                  <>
                    <button onClick={() => { setInput('竹林深处'); setDirection('竹林探险'); }}>🎋 竹林探险</button>
                    <button onClick={() => { setInput('古代宫廷'); setDirection('宫廷权谋'); }}>🏯 宫廷权谋</button>
                    <button onClick={() => { setInput('未来都市'); setDirection('赛博朋克'); }}>🌃 赛博朋克</button>
                  </>
                )}
                {sourceType === 'text_split' && (
                  <>
                    <button onClick={() => setInput('从前有一座山，山上有一座庙，庙里住着一个老和尚和一个小和尚。老和尚对小和尚说，从前有一座山，山上有一座庙，庙里住着一个老和尚和一个小和尚。日复一日，年复一年，春夏秋冬，四季轮回，故事代代相传。')}>📝 粘贴文本</button>
                    <button onClick={() => navigate('/create')}>⚙️ 高级创建</button>
                  </>
                )}
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

        {/* Suggested Actions */}
        {suggestedActions.length > 0 && (
          <div className="quick-actions" style={{ padding: '0 24px 8px' }}>
            {suggestedActions.map((action, i) => (
              <button key={i} onClick={() => setInput(action)}>{action}</button>
            ))}
          </div>
        )}

        <div className="chat-input-area">
          <div className="input-wrapper">
            <textarea
              className="chat-input"
              placeholder={
                sourceType === 'short_fiction' ? '输入创作方向，如"古风爱情"...' :
                sourceType === 'play_world' ? '输入你的动作...' :
                '粘贴你的小说/文段内容（至少80字符）...'
              }
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
