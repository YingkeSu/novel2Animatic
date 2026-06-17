import React, { useEffect, useState } from 'react'
import { Button, Tag, Space, Typography, message, Popconfirm } from 'antd'
import { PlusOutlined, LogoutOutlined, DeleteOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { projects, styles as stylesApi } from '../services/api'
import useStore from '../stores/auth'

const { Title, Text } = Typography

const statusLabels = {
  created: '待生成',
  running: '生成中',
  done: '已完成',
  failed: '失败',
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

  const handleDelete = async (e, projectId) => {
    e.stopPropagation()
    try {
      await projects.delete(projectId)
      message.success('项目已删除')
      load()
    } catch (e) {
      message.error('删除失败')
    }
  }

  const displayName = (key) => styleMap[key] || key

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <Title level={2} style={{ margin: 0, color: '#fff' }}>我的项目</Title>
          <Text style={{ color: 'var(--text-secondary)' }}>创建和管理你的 AI 手书项目</Text>
        </div>
        <Space>
          <Button type="primary" icon={<PlusOutlined />} size="large" onClick={() => navigate('/create')}>
            创建项目
          </Button>
          <Button icon={<LogoutOutlined />} onClick={logout} style={{ color: 'var(--text-secondary)' }}>
            退出
          </Button>
        </Space>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-secondary)' }}>加载中...</div>
      ) : list.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>📝</div>
          <Title level={4} style={{ color: 'var(--text-secondary)' }}>还没有项目</Title>
          <Text style={{ color: 'var(--text-secondary)' }}>点击上方按钮创建你的第一个 AI 手书项目</Text>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 20 }}>
          {list.map(project => (
            <div
              key={project.id}
              className="scene-card"
              onClick={() => navigate(`/project/${project.id}`)}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                <Title level={4} style={{ margin: 0, color: '#fff', fontSize: 16 }}>{project.title}</Title>
                <span className={`status-badge ${project.status}`}>
                  {statusLabels[project.status] || project.status}
                </span>
              </div>

              <Space wrap style={{ marginBottom: 12 }}>
                <Tag color="purple">{displayName(project.style_writing)}</Tag>
                <Tag color="cyan">{displayName(project.style_visual)}</Tag>
                <Tag color="orange">{displayName(project.style_audio)}</Tag>
              </Space>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
                <Text style={{ color: 'var(--text-secondary)', fontSize: 12 }}>
                  {new Date(project.created_at).toLocaleDateString('zh-CN')}
                </Text>
                <Space>
                  <Popconfirm
                    title="确定删除此项目？"
                    onConfirm={(e) => handleDelete(e, project.id)}
                    onCancel={(e) => e.stopPropagation()}
                    okText="删除"
                    cancelText="取消"
                  >
                    <Button
                      type="text"
                      size="small"
                      icon={<DeleteOutlined />}
                      style={{ color: 'var(--error)' }}
                      onClick={(e) => e.stopPropagation()}
                    />
                  </Popconfirm>
                  <Button size="small" type="link" style={{ color: 'var(--accent)' }}>
                    打开 →
                  </Button>
                </Space>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
