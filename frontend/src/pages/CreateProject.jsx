import React, { useState, useEffect } from 'react'
import { Form, Input, Select, Button, Card, message, Typography, Space, Alert } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { projects, styles as stylesApi } from '../services/api'

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

export default function CreateProject() {
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
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
    if ((values.source_text || '').trim().length < minimumSceneTextLength) {
      message.warning(`文段至少需要 ${minimumSceneTextLength} 个字符，才能生成稳定的场景拆分`)
      return
    }

    setLoading(true)
    try {
      const res = await projects.create(values)
      message.success('项目创建成功')
      navigate(`/project/${res.data.id}`)
    } catch (e) {
      message.error(e.response?.data?.detail || '创建失败')
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

          <Form.Item name="source_text" label="输入文段" rules={[{ required: true, message: '请输入文段' }]}>
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
