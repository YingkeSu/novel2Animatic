import React, { useState, useEffect } from 'react'
import { Form, Input, Select, Button, Card, App, Typography, Space, Alert } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import api, { projects, pipeline, styles as stylesApi } from '../services/api'

const { Title, Text } = Typography
const { TextArea } = Input
const minimumSceneTextLength = 80
const maximumProjectTitleLength = 255

const fallbackStyleDescriptions = {
  modern: '语言更清晰直接，适合把小说段落整理成节奏明确的分镜文本。',
  classical: '保留古典语感和叙事腔调，适合古风、仙侠或历史题材。',
  humorous: '语气更轻松，适合带有吐槽、反差或喜剧节奏的桥段。',
  ink_wash: '偏水墨与留白，适合古风意境、山水场景和克制的动作表达。',
  anime: '角色表情和动作更鲜明，适合情绪强、节奏快的剧情。',
  realistic: '画面更贴近真实影视质感，适合现代、悬疑或沉浸式场景。',
  ancient_male: '偏沉稳的男声叙述，适合古风、玄幻和正剧氛围。',
  modern_female: '偏清晰自然的女声叙述，适合现代剧情和细腻情绪。',
  cinematic: '音频更强调空间感和戏剧张力，适合关键场景和转折段落。',
}

const getStyleDescription = (style) => (
  style?.description || fallbackStyleDescriptions[style?.name] || '使用该风格生成分镜、画面提示和音频方向。'
)

const SOURCE_TYPES = [
  { key: 'text_split', label: '📝 文本拆分', desc: '输入长文本，AI 自动拆分成场景' },
  { key: 'short_fiction', label: '📖 短篇小说', desc: '输入创作方向，AI 三明治 pipeline 自动生成' },
  { key: 'play_world', label: '🌍 开放世界', desc: '交互式文字冒险，每回合推进剧情' },
]

const validateSourceTextLength = (_, value) => {
  const sourceText = (value || '').trim()
  if (!sourceText) {
    return Promise.resolve()
  }
  if (sourceText.length < minimumSceneTextLength) {
    return Promise.reject(new Error(`文段至少需要 ${minimumSceneTextLength} 个字符，才能生成稳定的场景拆分`))
  }
  return Promise.resolve()
}

const sourceTextRules = [
  { required: true, whitespace: true, message: '请输入文段' },
  { validator: validateSourceTextLength },
]

export default function CreateProject() {
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const { message } = App.useApp()
  const [loading, setLoading] = useState(false)
  const [sourceType, setSourceType] = useState('text_split')
  const [styleLoading, setStyleLoading] = useState(true)
  const [styleLoadError, setStyleLoadError] = useState('')
  const [writingStyles, setWritingStyles] = useState([])
  const [visualStyles, setVisualStyles] = useState([])
  const [audioStyles, setAudioStyles] = useState([])
  const selectedWritingStyle = Form.useWatch('style_writing', form)
  const selectedVisualStyle = Form.useWatch('style_visual', form)
  const selectedAudioStyle = Form.useWatch('style_audio', form)
  const sourceText = Form.useWatch('source_text', form) || ''
  const sourceTextLength = sourceText.trim().length

  useEffect(() => {
    let mounted = true

    const loadStyles = async () => {
      setStyleLoading(true)
      setStyleLoadError('')
      try {
        const [writing, visual, audio] = await Promise.all([
          stylesApi.list('writing'),
          stylesApi.list('visual'),
          stylesApi.list('audio'),
        ])

        if (!mounted) return
        setWritingStyles(writing.data)
        setVisualStyles(visual.data)
        setAudioStyles(audio.data)
      } catch (e) {
        if (!mounted) return
        setStyleLoadError('风格列表加载失败，请稍后重试')
      } finally {
        if (mounted) {
          setStyleLoading(false)
        }
      }
    }

    loadStyles()

    return () => {
      mounted = false
    }
  }, [])

  const handleSubmit = async (values) => {
    setLoading(true)
    try {
      const payload = { ...values, source_type: sourceType }
      if (sourceType !== 'text_split') {
        payload.direction = values.direction || ''
        delete payload.source_text
      }
      const res = await projects.create(payload)
      const projectId = res.data.id
      message.success('项目创建成功')

      // Auto-start pipeline for text_split; for short_fiction the generate endpoint handles it
      if (sourceType === 'text_split') {
        await pipeline.run(projectId)
        message.success('Pipeline 已启动')
      } else if (sourceType === 'short_fiction') {
        await api.post(`/projects/${projectId}/generate`, {
          source_type: 'short_fiction',
          chapter_count: 3,
        })
        message.success('短篇小说生成已启动')
      }

      navigate(`/project/${projectId}`)
    } catch (e) {
      const detail = e.response?.data?.detail
      const msg = Array.isArray(detail) ? detail[0]?.msg || '创建失败' : detail || '创建失败'
      message.error(msg)
    } finally {
      setLoading(false)
    }
  }

  const selectedStyles = [
    { label: '文风', value: selectedWritingStyle, options: writingStyles },
    { label: '画风', value: selectedVisualStyle, options: visualStyles },
    { label: '音频', value: selectedAudioStyle, options: audioStyles },
  ]

  return (
    <div style={{ padding: 24, maxWidth: 800, margin: '0 auto' }}>
      <Space style={{ marginBottom: 24 }}>
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/')} style={{ color: 'var(--text-secondary)' }} />
        <Title level={3} style={{ margin: 0, color: '#fff' }}>创建新项目</Title>
      </Space>

      <Card>
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          initialValues={{ style_writing: 'modern', style_visual: 'ink_wash', style_audio: 'ancient_male' }}
        >
          <Form.Item label="生成方式">
            <div style={{ display: 'flex', gap: 12 }}>
              {SOURCE_TYPES.map(st => (
                <div
                  key={st.key}
                  onClick={() => setSourceType(st.key)}
                  style={{
                    flex: 1, padding: 16, borderRadius: 8, cursor: 'pointer',
                    background: sourceType === st.key ? 'var(--accent)' : 'var(--bg-card)',
                    border: sourceType === st.key ? '2px solid var(--accent)' : '1px solid var(--border)',
                    textAlign: 'center', transition: 'all 0.2s',
                  }}
                >
                  <div style={{ fontSize: 16, marginBottom: 4 }}>{st.label}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{st.desc}</div>
                </div>
              ))}
            </div>
          </Form.Item>

          <Form.Item
            name="title"
            label="项目标题"
            rules={[
              { required: true, message: '请输入标题' },
              { max: maximumProjectTitleLength, message: `标题不能超过 ${maximumProjectTitleLength} 个字符` },
            ]}
          >
            <Input
              placeholder="例如：斗破苍穹 - 三年之约"
              size="large"
              maxLength={maximumProjectTitleLength}
              showCount
            />
          </Form.Item>

          {sourceType === 'text_split' ? (
            <>
              <Form.Item name="source_text" label="输入文段" rules={sourceTextRules}>
                <TextArea
                  rows={10}
                  placeholder={'粘贴你的小说/文段内容...\n\n支持直接粘贴小说片段，AI 会自动拆分为多个场景'}
                  style={{ fontSize: 15, lineHeight: 1.8 }}
                />
              </Form.Item>
              <div className="source-text-meter">
                <Text type={sourceTextLength >= minimumSceneTextLength ? 'success' : 'secondary'}>
                  已输入 {sourceTextLength} 字符，建议至少 {minimumSceneTextLength} 字符以便稳定拆分场景。
                </Text>
              </div>
            </>
          ) : (
            <Form.Item
              name="direction"
              label={sourceType === 'short_fiction' ? '创作方向' : '世界设定'}
              rules={[{ required: true, message: sourceType === 'short_fiction' ? '请输入创作方向' : '请输入世界设定' }]}
            >
              <TextArea
                rows={4}
                placeholder={
                  sourceType === 'short_fiction'
                    ? '例如：古风爱情，主角是一位失忆的剑客，在竹林中遇到一位神秘女子...'
                    : '例如：一个被遗弃在荒野中的旅人，周围是无尽的沙漠和废墟...'
                }
                style={{ fontSize: 15, lineHeight: 1.8 }}
              />
            </Form.Item>
          )}

          {styleLoadError && (
            <Alert
              type="warning"
              showIcon
              message={styleLoadError}
              style={{ marginBottom: 16 }}
            />
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
            <Form.Item name="style_writing" label="📝 文风">
              <Select size="large" loading={styleLoading} disabled={styleLoading}>
                {writingStyles.map((s) => (
                  <Select.Option key={s.name} value={s.name}>
                    {s.display}
                  </Select.Option>
                ))}
              </Select>
            </Form.Item>

            <Form.Item name="style_visual" label="🎨 画风">
              <Select size="large" loading={styleLoading} disabled={styleLoading}>
                {visualStyles.map((s) => (
                  <Select.Option key={s.name} value={s.name}>
                    {s.display}
                  </Select.Option>
                ))}
              </Select>
            </Form.Item>

            <Form.Item name="style_audio" label="🎙️ 音频风格">
              <Select size="large" loading={styleLoading} disabled={styleLoading}>
                {audioStyles.map((s) => (
                  <Select.Option key={s.name} value={s.name}>
                    {s.display}
                  </Select.Option>
                ))}
              </Select>
            </Form.Item>
          </div>

          <div className="style-description">
            {selectedStyles.map(({ label, value, options }) => {
              const style = options.find((s) => s.name === value)

              return (
                <div key={label}>
                  <Text strong>{label}</Text>
                  <Text type="secondary">
                    {styleLoading ? '正在加载风格说明...' : getStyleDescription(style)}
                  </Text>
                </div>
              )
            })}
          </div>

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} disabled={styleLoading || loading} size="large" block>
              🚀 开始创作
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}
