import React, { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Typography, Progress, Button, Space, Tag, message, Alert } from 'antd'
import { ArrowLeftOutlined, ReloadOutlined } from '@ant-design/icons'
import api, { projects, pipeline, styles as stylesApi } from '../services/api'

const { Title, Text, Paragraph } = Typography

const PIPELINE_STEPS = [
  { key: 'split_scenes', label: '拆分场景', icon: '📝' },
  { key: 'generate_refs', label: '角色参考', icon: '👤' },
  { key: 'generate_images', label: '生成图片', icon: '🎨' },
  { key: 'generate_audio', label: '生成音频', icon: '🎙️' },
  { key: 'assemble_video', label: '合成视频', icon: '🎬' },
  { key: 'complete', label: '完成', icon: '✅' },
]

const NON_TERMINAL_TASK_STATUSES = ['pending', 'running']
const isNonTerminalTaskStatus = (status) => NON_TERMINAL_TASK_STATUSES.includes(status)

export default function ProjectDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [project, setProject] = useState(null)
  const [taskProgress, setTaskProgress] = useState(null)
  const [loading, setLoading] = useState(false)
  const [detailLoading, setDetailLoading] = useState(true)
  const [detailError, setDetailError] = useState(null)
  const [styleMap, setStyleMap] = useState({})
  const [selectedScene, setSelectedScene] = useState(null)
  const [assetLoadingCount, setAssetLoadingCount] = useState(0)
  const [assetError, setAssetError] = useState('')
  const [sceneAssetLoadingCount, setSceneAssetLoadingCount] = useState(0)
  const [sceneAssetError, setSceneAssetError] = useState('')
  const [sceneAssetSceneSeq, setSceneAssetSceneSeq] = useState(null)
  const [imageUrl, setImageUrl] = useState('')
  const [audioUrl, setAudioUrl] = useState('')
  const [videoUrl, setVideoUrl] = useState('')
  const [referenceUrl, setReferenceUrl] = useState('')
  const [referenceAsset, setReferenceAsset] = useState(null)
  const pollIntervalRef = useRef(null)
  const sceneAssetRequestRef = useRef(0)
  const canRun = ['created', 'failed', 'done'].includes(project?.status)
  const isRunning = project?.status === 'running' || isNonTerminalTaskStatus(taskProgress?.status)
  const isDone = project?.status === 'done'
  const pipelineFailure = project?.status === 'failed'
  const assetLoading = assetLoadingCount > 0
  const sceneAssetLoading = sceneAssetLoadingCount > 0

  useEffect(() => {
    Promise.all([
      stylesApi.list('writing'),
      stylesApi.list('visual'),
      stylesApi.list('audio'),
    ]).then(([w, v, a]) => {
      const map = {}
      w.data.forEach(s => { map[s.name] = s.display })
      v.data.forEach(s => { map[s.name] = s.display })
      a.data.forEach(s => { map[s.name] = s.display })
      setStyleMap(map)
    }).catch(() => {})
  }, [])

  const loadProjectProgress = async () => {
    try {
      const progress = await pipeline.progress(id)
      setTaskProgress(progress.data)
    } catch {
      setTaskProgress(null)
    }
  }

  const loadProject = async () => {
    setDetailLoading(true)
    setDetailError(null)
    try {
      const res = await projects.get(id)
      const project = res.data
      setProject(project)
      if (project.scenes?.length > 0 && !selectedScene) {
        setSelectedScene(project.scenes[0])
      }
      if (project.status === 'failed' || project.status === 'running') {
        await loadProjectProgress()
      }
      if (project.status === 'running') {
        pollProgress()
      }
    } catch (e) {
      console.error(e)
      setProject(null)
      const detail = e.response?.data?.detail || e.message || '项目加载失败'
      const isNotFound = e.response?.status === 404 || /not found|不存在|未找到/i.test(detail)
      setDetailError({ detail, isNotFound })
    } finally {
      setDetailLoading(false)
    }
  }

  useEffect(() => { loadProject() }, [id])

  useEffect(() => () => {
    if (imageUrl) {
      URL.revokeObjectURL(imageUrl)
    }
  }, [imageUrl])

  useEffect(() => () => {
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl)
    }
  }, [audioUrl])

  useEffect(() => () => {
    if (videoUrl) {
      URL.revokeObjectURL(videoUrl)
    }
  }, [videoUrl])

  useEffect(() => () => {
    if (referenceUrl) {
      URL.revokeObjectURL(referenceUrl)
    }
  }, [referenceUrl])

  const clearPollInterval = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current)
      pollIntervalRef.current = null
    }
  }

  useEffect(() => () => {
    clearPollInterval()
  }, [])

  const loadAuthenticatedAssetUrl = async (path, setter) => {
    setAssetLoadingCount((count) => count + 1)
    setAssetError('')
    try {
      const response = await api.get(path, { responseType: 'blob' })
      const objectUrl = URL.createObjectURL(response.data)
      setter((current) => {
        if (current) {
          URL.revokeObjectURL(current)
        }
        return objectUrl
      })
    } catch (e) {
      setAssetError(e.response?.data?.detail || '媒体资源加载失败')
      setter((current) => {
        if (current) {
          URL.revokeObjectURL(current)
        }
        return ''
      })
    } finally {
      setAssetLoadingCount((count) => Math.max(0, count - 1))
    }
  }

  const loadSceneAssetUrl = async (path, setter, requestKey) => {
    setSceneAssetLoadingCount((count) => count + 1)
    setSceneAssetError('')
    try {
      const response = await api.get(path, { responseType: 'blob' })
      const objectUrl = URL.createObjectURL(response.data)
      if (requestKey !== sceneAssetRequestRef.current) {
        URL.revokeObjectURL(objectUrl)
        return
      }
      setter((current) => {
        if (current) {
          URL.revokeObjectURL(current)
        }
        return objectUrl
      })
    } catch (e) {
      if (requestKey !== sceneAssetRequestRef.current) {
        return
      }
      setSceneAssetError(e.response?.data?.detail || '当前场景媒体加载失败')
      setter((current) => {
        if (current) {
          URL.revokeObjectURL(current)
        }
        return ''
      })
    } finally {
      if (requestKey === sceneAssetRequestRef.current) {
        setSceneAssetLoadingCount((count) => Math.max(0, count - 1))
      }
    }
  }

  useEffect(() => {
    if (!isDone || !selectedScene) {
      return
    }

    setImageUrl('')
    setAudioUrl('')
    sceneAssetRequestRef.current += 1
    const requestKey = sceneAssetRequestRef.current
    setSceneAssetSceneSeq(selectedScene.seq)
    setSceneAssetLoadingCount(0)
    setSceneAssetError('')
    loadSceneAssetUrl(`/projects/${id}/scenes/${selectedScene.seq}/image`, setImageUrl, requestKey)
    loadSceneAssetUrl(`/projects/${id}/scenes/${selectedScene.seq}/audio`, setAudioUrl, requestKey)
  }, [id, isDone, selectedScene])

  useEffect(() => {
    if (!isDone) {
      return
    }

    loadAuthenticatedAssetUrl(`/projects/${id}/reference`, setReferenceUrl)
    setReferenceAsset({ fileName: 'reference.png' })
  }, [id, isDone])

  useEffect(() => {
    if (!isDone) {
      return
    }

    loadAuthenticatedAssetUrl(`/projects/${id}/video`, setVideoUrl)
  }, [id, isDone])

  const handleRun = async () => {
    setLoading(true)
    try {
      await pipeline.run(id)
      message.success('Pipeline 已启动')
      pollProgress()
    } catch (e) {
      message.error(e.response?.data?.detail || '启动失败')
    } finally {
      setLoading(false)
    }
  }

  const pollProgress = () => {
    clearPollInterval()
    // Immediate first poll, then every 2s
    const doPoll = async () => {
      try {
        const res = await pipeline.progress(id)
        setTaskProgress(res.data)
        if (!isNonTerminalTaskStatus(res.data.status)) {
          clearPollInterval()
          loadProject()
        }
      } catch {
        // Transient error — keep polling, don't stop
      }
    }
    doPoll()
    pollIntervalRef.current = setInterval(doPoll, 2000)
  }

  if (detailLoading && !project) {
    return (
      <div className="project-detail-state">
        <div className="project-detail-state-card">
          <div className="route-loading-mark" aria-hidden="true" />
          <Title level={3} style={{ color: '#fff', marginBottom: 8 }}>正在加载项目详情</Title>
          <Text style={{ color: 'var(--text-secondary)' }}>正在读取项目信息、场景和生成状态...</Text>
        </div>
      </div>
    )
  }

  if (detailError && !project) {
    const { detail, isNotFound } = detailError

    return (
      <div className="project-detail-state">
        <div className="project-detail-state-card">
          <Title level={3} style={{ color: '#fff', marginBottom: 8 }}>
            {isNotFound ? '项目不存在' : '项目加载失败'}
          </Title>
          <Text style={{ color: 'var(--text-secondary)' }}>
            {isNotFound ? '该项目可能已被删除，或当前链接无效。' : detail}
          </Text>
          <Space style={{ marginTop: 24 }}>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/')}>
              返回项目列表
            </Button>
            {!isNotFound && (
              <Button type="primary" icon={<ReloadOutlined />} onClick={loadProject}>
                重试
              </Button>
            )}
          </Space>
        </div>
      </div>
    )
  }

  if (!project) {
    return (
      <div className="project-detail-state">
        <div className="project-detail-state-card">
          <Title level={3} style={{ color: '#fff', marginBottom: 8 }}>项目暂不可用</Title>
          <Text style={{ color: 'var(--text-secondary)' }}>当前项目状态无法显示，请返回项目列表后重试。</Text>
          <div style={{ marginTop: 24 }}>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/')}>
              返回项目列表
            </Button>
          </div>
        </div>
      </div>
    )
  }

  const displayName = (key) => styleMap[key] || key

  const currentStepIndex = taskProgress
    ? PIPELINE_STEPS.findIndex(s => s.key === taskProgress.step)
    : isDone ? PIPELINE_STEPS.length - 1 : -1
  const pipelineFailureMessage = taskProgress?.error_msg || project.error_msg || 'Pipeline 执行失败，请重试生成。'
  const currentSceneOwnsAssetStatus = isDone && selectedScene && sceneAssetSceneSeq === selectedScene.seq
  const currentSceneAssetStatus = isDone && selectedScene
    ? (!currentSceneOwnsAssetStatus
      ? ''
      : sceneAssetLoading
      ? `正在加载当前场景媒体：Scene ${selectedScene.seq}`
      : sceneAssetError
        ? `当前场景媒体加载失败：Scene ${selectedScene.seq}`
        : `当前场景媒体已就绪：Scene ${selectedScene.seq}`)
    : ''

  return (
    <div className="project-detail-page">
      {/* Top toolbar */}
      <div className="app-header">
        <Space>
          <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/')} style={{ color: 'var(--text-secondary)' }} />
          <Title level={3} style={{ margin: 0, color: '#fff' }}>{project.title}</Title>
          <span className={`status-badge ${project.status}`}>
            {isRunning ? '⏳ 生成中' : isDone ? '✅ 已完成' : pipelineFailure ? '❌ 失败' : '📝 待生成'}
          </span>
        </Space>
        <Space>
          <Tag color="purple">{displayName(project.style_writing)}</Tag>
          <Tag color="cyan">{displayName(project.style_visual)}</Tag>
          <Tag color="orange">{displayName(project.style_audio)}</Tag>
          {canRun && (
            <Button
              type="primary"
              icon={<ReloadOutlined />}
              loading={loading}
              onClick={handleRun}
            >
              {project.status === 'created' ? '开始生成' : '重新生成'}
            </Button>
          )}
        </Space>
      </div>

      {/* Step progress bar */}
      {(isRunning || isDone || pipelineFailure) && (
        <div className="step-progress">
          {PIPELINE_STEPS.map((step, i) => (
            <React.Fragment key={step.key}>
              <div className={`step-item ${i < currentStepIndex ? 'completed' : i === currentStepIndex ? 'active' : ''}`}>
                <span>{step.icon}</span>
                <span>{step.label}</span>
                {taskProgress?.status === 'failed' && i === currentStepIndex && <span>❌</span>}
              </div>
              {i < PIPELINE_STEPS.length - 1 && (
                <div className={`step-connector ${i < currentStepIndex ? 'completed' : ''}`} />
              )}
            </React.Fragment>
          ))}
        </div>
      )}

      {/* Main content */}
      <div className="project-detail-main">
        {/* Left: Scene list */}
        <div className="project-detail-sidebar">
          <Text style={{ color: 'var(--text-secondary)', fontSize: 12, marginBottom: 12, display: 'block' }}>
            场景列表 ({project.scenes?.length || 0})
          </Text>
          {project.scenes?.map(scene => (
            <div
              key={scene.id}
              className={`scene-card ${selectedScene?.id === scene.id ? 'selected' : ''}`}
              style={{ marginBottom: 8, padding: 12 }}
              onClick={() => setSelectedScene(scene)}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <Text style={{ color: '#fff', fontSize: 13, fontWeight: 500 }}>Scene {scene.seq}</Text>
                <Tag style={{ fontSize: 11, margin: 0 }}>{scene.shot_type}</Tag>
              </div>
              <Text style={{ color: 'var(--text-secondary)', fontSize: 12 }} ellipsis>
                {scene.title}
              </Text>
              {scene.character && (
                <Tag color="blue" style={{ fontSize: 11, marginTop: 4 }}>{scene.character}</Tag>
              )}
            </div>
          ))}
        </div>

        {/* Center: Preview area */}
        <div className="project-detail-preview">
          {currentSceneAssetStatus && (
            <div className="project-detail-asset-status" aria-live="polite">
              <Text type={sceneAssetError ? 'danger' : sceneAssetLoading ? 'secondary' : 'success'}>
                {currentSceneAssetStatus}
              </Text>
            </div>
          )}

          {currentSceneOwnsAssetStatus && sceneAssetError && (
            <Alert
              type="warning"
              showIcon
              message={sceneAssetError}
              style={{ marginBottom: 16 }}
            />
          )}

          {assetError && (
            <Alert
              type="warning"
              showIcon
              message={assetError}
              style={{ marginBottom: 16 }}
            />
          )}

          {assetLoading && (
            <Alert
              type="info"
              showIcon
              message="正在加载项目媒体资源..."
              style={{ marginBottom: 16 }}
            />
          )}

          {isDone && selectedScene ? (
            <div className="project-detail-preview-stack">
              {/* Scene image */}
              <div className="video-container project-detail-preview-image">
                <img
                  src={imageUrl}
                  alt={selectedScene.title}
                  style={{ width: '100%', maxHeight: 400, objectFit: 'contain', background: '#000' }}
                />
              </div>

              {/* Scene info */}
              <div style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius)', padding: 20, marginBottom: 16 }}>
                <Title level={4} style={{ color: '#fff', marginBottom: 8 }}>{selectedScene.title}</Title>
                <Space style={{ marginBottom: 12 }}>
                  <Tag>{selectedScene.shot_type}</Tag>
                  {selectedScene.character && <Tag color="blue">{selectedScene.character}</Tag>}
                </Space>
                <Paragraph style={{ color: 'var(--text-secondary)', fontSize: 15, lineHeight: 1.8 }}>
                  {selectedScene.narration}
                </Paragraph>
              </div>

              <div className="project-detail-prompt-panel">
                <Text className="project-detail-prompt-title">生成依据</Text>
                <div className="project-detail-prompt-grid">
                  <div>
                    <Text className="project-detail-prompt-label">场景原文</Text>
                    <Paragraph className="project-detail-prompt-copy">
                      {selectedScene.text}
                    </Paragraph>
                  </div>
                  <div>
                    <Text className="project-detail-prompt-label">图像提示词</Text>
                    <Paragraph className="project-detail-prompt-copy">
                      {selectedScene.edit_prompt}
                    </Paragraph>
                  </div>
                  <div>
                    <Text className="project-detail-prompt-label">TTS 指令</Text>
                    <Paragraph className="project-detail-prompt-copy">
                      {selectedScene.instruction}
                    </Paragraph>
                  </div>
                </div>
              </div>

              {referenceUrl && (
                <div style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius)', padding: 16, marginBottom: 16 }}>
                  <Text style={{ color: 'var(--text-secondary)', fontSize: 12, marginBottom: 8, display: 'block' }}>
                    Reference image
                  </Text>
                  <Text style={{ color: 'var(--text-secondary)', fontSize: 11, marginBottom: 8, display: 'block' }}>
                    {referenceAsset?.fileName}
                  </Text>
                  <img
                    src={referenceUrl}
                    alt="Reference image"
                    style={{ width: '100%', maxHeight: 240, objectFit: 'contain', background: '#000' }}
                  />
                </div>
              )}

              {/* Audio player */}
              <div className="project-detail-preview-audio">
                <Text style={{ color: 'var(--text-secondary)', fontSize: 12, marginBottom: 8, display: 'block' }}>🎙️ 旁白音频</Text>
                <audio
                  controls
                  style={{ width: '100%' }}
                  src={audioUrl}
                />
              </div>
            </div>
          ) : isDone ? (
            <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-secondary)' }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>👈</div>
              <Text>从左侧选择一个场景查看详情</Text>
            </div>
          ) : isRunning ? (
            <div style={{ textAlign: 'center', padding: 60 }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>⏳</div>
              <Title level={4} style={{ color: 'var(--text-secondary)' }}>
                {PIPELINE_STEPS[currentStepIndex]?.label || '处理中'}...
              </Title>
              <Progress
                percent={taskProgress?.progress || 0}
                strokeColor="var(--accent)"
                trailColor="var(--bg-card)"
                style={{ maxWidth: 400, margin: '16px auto' }}
              />
              <Text style={{ color: 'var(--text-secondary)' }}>
                {taskProgress?.progress || 0}% 完成
              </Text>
            </div>
          ) : pipelineFailure ? (
            <div className="project-detail-failure">
              <div className="project-detail-failure-icon" aria-hidden="true">!</div>
              <Title level={4} className="project-detail-failure-title">
                Pipeline 生成失败
              </Title>
              <Paragraph className="project-detail-failure-message">
                {pipelineFailureMessage}
              </Paragraph>
              <Space wrap>
                <Button
                  type="primary"
                  icon={<ReloadOutlined />}
                  loading={loading}
                  onClick={handleRun}
                >
                  重试生成
                </Button>
                <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/')}>
                  返回项目列表
                </Button>
              </Space>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: 60 }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>🎬</div>
              <Title level={4} style={{ color: 'var(--text-secondary)' }}>点击右上角"开始生成"</Title>
              <Text style={{ color: 'var(--text-secondary)' }}>AI 将自动拆分场景、生成图片和音频、合成视频</Text>
            </div>
        )}
        </div>

        {/* Right: Video player (only when done) */}
        {isDone && (
          <div className="project-detail-video-panel">
            <Text style={{ color: 'var(--text-secondary)', fontSize: 12, marginBottom: 12, display: 'block' }}>🎬 完整视频</Text>
            <div className="video-container">
              <video
                controls
                src={videoUrl}
              />
            </div>

            <div style={{ marginTop: 16 }}>
              <Text style={{ color: 'var(--text-secondary)', fontSize: 12, marginBottom: 8, display: 'block' }}>📊 项目信息</Text>
              <div style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius-sm)', padding: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <Text style={{ color: 'var(--text-secondary)' }}>场景数</Text>
                  <Text style={{ color: '#fff' }}>{project.scenes?.length || 0}</Text>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <Text style={{ color: 'var(--text-secondary)' }}>文风</Text>
                  <Text style={{ color: '#fff' }}>{displayName(project.style_writing)}</Text>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <Text style={{ color: 'var(--text-secondary)' }}>画风</Text>
                  <Text style={{ color: '#fff' }}>{displayName(project.style_visual)}</Text>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Text style={{ color: 'var(--text-secondary)' }}>音频</Text>
                  <Text style={{ color: '#fff' }}>{displayName(project.style_audio)}</Text>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
