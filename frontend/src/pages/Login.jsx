import React, { useState } from 'react'
import { Form, Input, Button, Card, App, Tabs, Typography } from 'antd'
import { auth } from '../services/api'
import useStore from '../stores/auth'

const { Title, Text } = Typography

const emailRules = [
  { required: true, message: '请输入邮箱' },
  { type: 'email', message: '请输入有效的邮箱' },
]

const passwordRules = [
  { required: true, message: '请输入密码' },
  { min: 8, message: '密码至少8位' },
]

export default function Login({ onLogin }) {
  const [loading, setLoading] = useState(false)
  const setToken = useStore((s) => s.setToken)
  const { message } = App.useApp()

  const handleSubmit = async (values, isRegister) => {
    setLoading(true)
    try {
      const fn = isRegister ? auth.register : auth.login
      const res = await fn(values.email, values.password)
      setToken(res.data.access_token)
      message.success(isRegister ? '注册成功' : '登录成功')
      onLogin()
    } catch (e) {
      const detail = e.response?.data?.detail
      const msg = Array.isArray(detail) ? detail[0]?.msg || '操作失败' : detail || '操作失败'
      message.error(msg)
    } finally {
      setLoading(false)
    }
  }

  const items = [
    {
      key: 'login',
      label: '登录',
      children: (
        <Form onFinish={(v) => handleSubmit(v, false)}>
          <Form.Item name="email" rules={emailRules}>
            <Input placeholder="邮箱" size="large" />
          </Form.Item>
          <Form.Item name="password" rules={passwordRules}>
            <Input.Password placeholder="密码" size="large" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block size="large">登录</Button>
          </Form.Item>
        </Form>
      ),
    },
    {
      key: 'register',
      label: '注册',
      children: (
        <Form onFinish={(v) => handleSubmit(v, true)}>
          <Form.Item name="email" rules={emailRules}>
            <Input placeholder="邮箱" size="large" />
          </Form.Item>
          <Form.Item name="password" rules={passwordRules}>
            <Input.Password placeholder="密码" size="large" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block size="large">注册</Button>
          </Form.Item>
        </Form>
      ),
    },
  ]

  return (
    <div style={{
      display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh',
      background: 'linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #0f0f1a 100%)'
    }}>
      <Card style={{ width: 420, background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <Title level={2} style={{ color: 'var(--accent)', margin: 0 }}>🎬 novel2Animatic</Title>
          <Text style={{ color: 'var(--text-secondary)' }}>AI 手书创作平台</Text>
        </div>
        <Tabs items={items} centered />
      </Card>
    </div>
  )
}
