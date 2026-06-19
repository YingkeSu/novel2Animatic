import React, { useEffect, useState } from 'react'
import { Button, Tag, Typography, message, Popconfirm, Tooltip } from 'antd'
import {
  ExclamationCircleOutlined,
  ClockCircleOutlined,
  DeleteOutlined,
  FileTextOutlined,
  FolderOpenOutlined,
  LogoutOutlined,
  PlusOutlined,
  RightOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { projects, styles as stylesApi } from '../services/api'
import useStore from '../stores/auth'

const { Title, Text, Paragraph } = Typography

const statusMeta = {
  created: {
    label: '待生成',
    description: '等待启动生成',
    icon: '·',
  },
  running: {
    label: '生成中',
    description: '正在生成资产',
    icon: '↻',
  },
  done: {
    label: '已完成',
    description: '可查看成片',
    icon: '✓',
  },
  failed: {
    label: '失败',
    description: '需要重新处理',
    icon: '!',
  },
}

const formatDate = (date) => {
  if (!date) return '时间未知'
  return new Date(date).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

export default function Dashboard() {
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(false)
  const [styleMap, setStyleMap] = useState({})
  const navigate = useNavigate()
  const logout = useStore((s) => s.logout)

  const load = async () => {
    setLoading(true)
    try {
      const res = await projects.list()
      setList(res.data)
    } catch (e) {
      message.error('加载项目列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
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

  const handleDelete = async (projectId, event) => {
    event?.stopPropagation?.()
    try {
      await projects.delete(projectId)
      message.success('项目已删除')
      load()
    } catch (e) {
      const status = e.response?.status
      const detail = e.response?.data?.detail
      message.error(status === 409 ? '项目正在生成中，暂时无法删除' : detail || '删除失败')
    }
  }

  const displayName = (key) => styleMap[key] || key
  const getStatus = (status) => statusMeta[status] || {
    label: status || '未知',
    description: '状态未知',
    icon: '?',
  }

  return (
    <main className="dashboard-page">
      <header className="dashboard-toolbar">
        <div className="dashboard-heading">
          <Text className="dashboard-kicker">项目工作台</Text>
          <Title level={2} className="dashboard-title">我的项目</Title>
          <Text className="dashboard-subtitle">创建、生成并管理你的 AI 手书项目</Text>
        </div>
        <div className="dashboard-actions">
          <div className="dashboard-count" aria-label={`当前共有 ${list.length} 个项目`}>
            <FolderOpenOutlined />
            <span>{list.length} 个项目</span>
          </div>
          <Button type="primary" icon={<PlusOutlined />} size="large" onClick={() => navigate('/create')}>
            立即创建
          </Button>
          <Button icon={<LogoutOutlined />} onClick={logout} className="dashboard-logout">
            退出
          </Button>
        </div>
      </header>

      {/* Quick Start — 三种生成方式入口 */}
      <section className="dashboard-quick-start">
        <Text className="dashboard-kicker">快速开始</Text>
        <div className="dashboard-quick-grid">
          <article
            className="dashboard-quick-card"
            onClick={() => navigate('/chat', { state: { sourceType: 'text_split' } })}
            tabIndex={0}
          >
            <span className="quick-card-icon">📝</span>
            <Title level={4} className="quick-card-title">文本拆分</Title>
            <Text className="quick-card-desc">输入长文本，AI 自动拆分成场景，生成分镜、画面、音频和成片</Text>
          </article>
          <article
            className="dashboard-quick-card"
            onClick={() => navigate('/chat', { state: { sourceType: 'short_fiction' } })}
            tabIndex={0}
          >
            <span className="quick-card-icon">📖</span>
            <Title level={4} className="quick-card-title">短篇小说</Title>
            <Text className="quick-card-desc">输入创作方向，AI 三明治 pipeline 自动生成完整故事场景</Text>
          </article>
          <article
            className="dashboard-quick-card"
            onClick={() => navigate('/chat', { state: { sourceType: 'play_world' } })}
            tabIndex={0}
          >
            <span className="quick-card-icon">🌍</span>
            <Title level={4} className="quick-card-title">开放世界</Title>
            <Text className="quick-card-desc">交互式文字冒险，每回合推进剧情，实时生成场景画面</Text>
          </article>
        </div>
      </section>

      {loading ? (
        <section className="dashboard-loading" aria-live="polite" aria-busy="true">
          <div className="dashboard-loading-copy">
            <ClockCircleOutlined />
            <div>
              <Text className="dashboard-loading-title">正在加载项目</Text>
              <Text className="dashboard-loading-subtitle">同步项目状态与风格信息...</Text>
            </div>
          </div>
          <div className="dashboard-grid" aria-hidden="true">
            {[0, 1, 2].map((item) => (
              <div className="dashboard-card dashboard-card-skeleton" key={item}>
                <span className="skeleton-line skeleton-line-title" />
                <span className="skeleton-line skeleton-line-short" />
                <span className="skeleton-line" />
                <span className="skeleton-line skeleton-line-footer" />
              </div>
            ))}
          </div>
        </section>
      ) : list.length === 0 ? (
        <section className="empty-state">
          <div className="empty-state-icon">
            <FileTextOutlined />
          </div>
          <Title level={3} className="empty-state-title">还没有项目</Title>
          <Paragraph className="empty-state-copy">
            从小说文本开始创建第一个 AI 手书项目，生成分镜、画面、音频和成片。
          </Paragraph>
          <Button type="primary" size="large" icon={<PlusOutlined />} onClick={() => navigate('/create')}>
            立即创建
          </Button>
        </section>
      ) : (
        <section className="dashboard-grid">
          {list.map(project => {
            const meta = getStatus(project.status)
            const isDeleteDisabled = project.status === 'running'
            const deleteAriaLabel = isDeleteDisabled
              ? `生成中不可删除：${project.title}`
              : `删除 ${project.title}`
            const deleteTooltip = isDeleteDisabled ? '生成中不可删除' : undefined

            return (
              <article
                key={project.id}
                className="dashboard-card"
                onClick={() => navigate(`/project/${project.id}`)}
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    navigate(`/project/${project.id}`)
                  }
                }}
              >
                <div className="dashboard-card-header">
                  <div className="dashboard-card-title-group">
                    <Title level={4} className="dashboard-card-title">{project.title}</Title>
                    <Text className="dashboard-card-date">
                      创建于 {formatDate(project.created_at)}
                    </Text>
                  </div>
                  <span className={`status-badge ${project.status}`}>
                    <span aria-hidden="true">{meta.icon}</span>
                    {meta.label}
                  </span>
                </div>

                <Text className="dashboard-card-status">{meta.description}</Text>
                {project.status === 'failed' && project.latest_error_msg && (
                  <div className="dashboard-card-error" title={project.latest_error_msg}>
                    <ExclamationCircleOutlined />
                    <Text>{project.latest_error_msg}</Text>
                  </div>
                )}

                <div className="dashboard-card-tags">
                  <Tag color="purple" title={displayName(project.style_writing)}>
                    文案 {displayName(project.style_writing)}
                  </Tag>
                  <Tag color="cyan" title={displayName(project.style_visual)}>
                    视觉 {displayName(project.style_visual)}
                  </Tag>
                  <Tag color="orange" title={displayName(project.style_audio)}>
                    音频 {displayName(project.style_audio)}
                  </Tag>
                </div>

                <div className="dashboard-card-footer">
                  <Text className="dashboard-card-id">
                    #{project.id}
                  </Text>
                  <div className="dashboard-card-actions">
                    <Tooltip title={deleteTooltip}>
                      <span
                        className="dashboard-delete-action"
                        onClick={(event) => event.stopPropagation()}
                      >
                        <Popconfirm
                          title="确定删除此项目？"
                          onConfirm={(event) => handleDelete(project.id, event)}
                          onCancel={(event) => event?.stopPropagation?.()}
                          okText="删除"
                          cancelText="取消"
                          disabled={isDeleteDisabled}
                        >
                          <Button
                            type="text"
                            size="small"
                            icon={<DeleteOutlined />}
                            danger
                            disabled={isDeleteDisabled}
                            aria-label={deleteAriaLabel}
                            title={deleteTooltip}
                          />
                        </Popconfirm>
                      </span>
                    </Tooltip>
                    <Button size="small" type="link" className="dashboard-open-link">
                      打开 <RightOutlined />
                    </Button>
                  </div>
                </div>
              </article>
            )
          })}
        </section>
      )}
    </main>
  )
}
