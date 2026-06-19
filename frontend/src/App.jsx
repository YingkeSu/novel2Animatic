import React, { Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { App as AntdApp } from 'antd'
import useStore from './stores/auth'

const Login = React.lazy(() => import('./pages/Login'))
const Dashboard = React.lazy(() => import('./pages/Dashboard'))
const CreateProject = React.lazy(() => import('./pages/CreateProject'))
const ProjectDetail = React.lazy(() => import('./pages/ProjectDetail'))
const ChatPage = React.lazy(() => import('./pages/ChatPage'))

function RouteLoading() {
  return (
    <main className="route-loading" role="status" aria-live="polite" aria-busy="true">
      <div className="route-loading-mark" aria-hidden="true" />
      <div>
        <p className="route-loading-title">正在加载页面</p>
        <p className="route-loading-subtitle">准备项目数据与编辑界面...</p>
      </div>
    </main>
  )
}

function PrivateRoute({ children }) {
  const token = useStore((s) => s.token)
  return token ? children : <Navigate to="/login" />
}

export default function App() {
  const token = useStore((s) => s.token)

  return (
    <BrowserRouter>
      <AntdApp>
        <Suspense fallback={<RouteLoading />}>
          <Routes>
          <Route path="/login" element={token ? <Navigate to="/" /> : <Login onLogin={() => window.location.href = '/'} />} />
          <Route path="/" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
          <Route path="/create" element={<PrivateRoute><CreateProject /></PrivateRoute>} />
          <Route path="/project/:id" element={<PrivateRoute><ProjectDetail /></PrivateRoute>} />
          <Route path="/chat" element={<PrivateRoute><ChatPage /></PrivateRoute>} />
          <Route path="/chat/project/:id" element={<PrivateRoute><ChatPage /></PrivateRoute>} />
        </Routes>
      </Suspense>
      </AntdApp>
    </BrowserRouter>
  )
}
