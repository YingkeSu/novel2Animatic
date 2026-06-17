import React, { useState, useEffect } from 'react'
import { Form, Input, Select, Button, Card, message, Typography, Space } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { projects, styles as stylesApi } from '../services/api'

const { Title, Text } = Typography
const { TextArea } = Input

export default function CreateProject() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [writingStyles, setWritingStyles] = useState([])
  const [visualStyles, setVisualStyles] = useState([])
  const [audioStyles, setAudioStyles] = useState([])

  useEffect(() => {
    stylesApi.list('writing').then((r) => setWritingStyles(r.data)).catch(() => {})
    stylesApi.list('visual').then((r) => setVisualStyles(r.data)).catch(() => {})
    stylesApi.list('audio').then((r) => setAudioStyles(r.data)).catch(() => {})
  }, [])

  const handleSubmit = async (values) => {
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

  return (
    <div style={{ padding: 24, maxWidth: 800, margin: '0 auto' }}>
      <Space style={{ marginBottom: 24 }}>
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/')} style={{ color: 'var(--text-secondary)' }} />
        <Title level={3} style={{ margin: 0, color: '#fff' }}>创建新项目</Title>
      </Space>

      <Card>
        <Form
          layout="vertical"
          onFinish={handleSubmit}
          initialValues={{ style_writing: 'modern', style_visual: 'ink_wash', style_audio: 'ancient_male' }}
        >
          <Form.Item name="title" label="项目标题" rules={[{ required: true, message: '请输入标题' }]}>
            <Input placeholder="例如：斗破苍穹 - 三年之约" size="large" />
          </Form.Item>

          <Form.Item name="source_text" label="输入文段" rules={[{ required: true, message: '请输入文段' }]}>
            <TextArea
              rows={10}
              placeholder="粘贴你的小说/文段内容...&#10;&#10;支持直接粘贴小说片段，AI 会自动拆分为多个场景"
              style={{ fontSize: 15, lineHeight: 1.8 }}
            />
          </Form.Item>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
            <Form.Item name="style_writing" label="📝 文风">
              <Select size="large">
                {writingStyles.map((s) => (
                  <Select.Option key={s.name} value={s.name}>
                    {s.display}
                  </Select.Option>
                ))}
              </Select>
            </Form.Item>

            <Form.Item name="style_visual" label="🎨 画风">
              <Select size="large">
                {visualStyles.map((s) => (
                  <Select.Option key={s.name} value={s.name}>
                    {s.display}
                  </Select.Option>
                ))}
              </Select>
            </Form.Item>

            <Form.Item name="style_audio" label="🎙️ 音频风格">
              <Select size="large">
                {audioStyles.map((s) => (
                  <Select.Option key={s.name} value={s.name}>
                    {s.display}
                  </Select.Option>
                ))}
              </Select>
            </Form.Item>
          </div>

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} size="large" block>
              🚀 开始创作
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}
