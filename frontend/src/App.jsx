import React, { Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import useStore from './stores/auth'

const Login = React.lazy(() => import('./pages/Login'))
const Dashboard = React.lazy(() => import('./pages/Dashboard'))
const CreateProject = React.lazy(() => import('./pages/CreateProject'))
const ProjectDetail = React.lazy(() => import('./pages/ProjectDetail'))

function PrivateRoute({ children }) {
  const token = useStore((s) => s.token)
  return token ? children : <Navigate to="/login" />
}

export default function App() {
  const token = useStore((s) => s.token)

  return (
    <BrowserRouter>
      <Suspense fallback={null}>
        <Routes>
          <Route path="/login" element={token ? <Navigate to="/" /> : <Login onLogin={() => window.location.href = '/'} />} />
          <Route path="/" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
          <Route path="/create" element={<PrivateRoute><CreateProject /></PrivateRoute>} />
          <Route path="/project/:id" element={<PrivateRoute><ProjectDetail /></PrivateRoute>} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
