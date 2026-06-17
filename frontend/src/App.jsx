import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import useStore from './stores/auth'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import CreateProject from './pages/CreateProject'
import ProjectDetail from './pages/ProjectDetail'

function PrivateRoute({ children }) {
  const token = useStore((s) => s.token)
  return token ? children : <Navigate to="/login" />
}

export default function App() {
  const token = useStore((s) => s.token)

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={token ? <Navigate to="/" /> : <Login onLogin={() => window.location.href = '/'} />} />
        <Route path="/" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
        <Route path="/create" element={<PrivateRoute><CreateProject /></PrivateRoute>} />
        <Route path="/project/:id" element={<PrivateRoute><ProjectDetail /></PrivateRoute>} />
      </Routes>
    </BrowserRouter>
  )
}
