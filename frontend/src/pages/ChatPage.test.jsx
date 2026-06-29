import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { App as AntdApp } from 'antd'

// Mock the api module so no real network calls happen.
const apiMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}))
vi.mock('../services/api', () => ({
  default: { get: (...a) => apiMocks.get(...a), post: (...a) => apiMocks.post(...a) },
}))

import ChatPage from './ChatPage'

const PLAY_PROJECT = {
  id: 42,
  title: '竹林探险',
  source_type: 'play_world',
  direction: '竹林深处的冒险',
  status: 'created',
  scenes: [],
}

function renderChatAt(path = '/chat/project/42') {
  return render(
    <AntdApp>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/chat/project/:id" element={<ChatPage />} />
          <Route path="/chat" element={<ChatPage />} />
        </Routes>
      </MemoryRouter>
    </AntdApp>
  )
}

describe('ChatPage — play_world turn', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'test-token')
    apiMocks.get.mockReset()
    apiMocks.post.mockReset()
    // Project list (sidebar) — resolve empty so it doesn't throw.
    apiMocks.get.mockResolvedValue({ data: [] })
  })

  afterEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('submits an action to the play endpoint and renders the returned narration + suggested actions', async () => {
    const user = userEvent.setup()

    // First get() is the projects list; the second is /projects/42 (project load).
    apiMocks.get
      .mockResolvedValueOnce({ data: [] }) // /projects
      .mockResolvedValueOnce({ data: PLAY_PROJECT }) // /projects/42

    // /play returns one scene of narration.
    apiMocks.post.mockResolvedValueOnce({
      data: {
        scene_text: '竹林沙沙作响，一缕薄雾从脚下升起。',
        suggested_actions: ['向深处走去', '拔剑戒备'],
        turn: 1,
        action_kind: 'explore',
      },
    })

    renderChatAt('/chat/project/42')

    // Wait for the project to load and the welcome line to render.
    await waitFor(() =>
      expect(screen.getByText(/已加载项目「竹林探险」/)).toBeInTheDocument()
    )

    const input = screen.getByPlaceholderText('输入你的动作...')
    const sendButton = screen.getByRole('button', { name: '发送' })

    await user.type(input, '我走入竹林深处')
    await user.click(sendButton)

    // The play endpoint is hit with the raw input + context.
    await waitFor(() => {
      expect(apiMocks.post).toHaveBeenCalledWith(
        '/projects/42/play',
        expect.objectContaining({
          raw_input: '我走入竹林深处',
          context: '竹林深处的冒险',
        })
      )
    })

    // Narration is rendered.
    await waitFor(() =>
      expect(screen.getByText('竹林沙沙作响，一缕薄雾从脚下升起。')).toBeInTheDocument()
    )

    // Suggested actions render as quick-action buttons.
    expect(await screen.findByRole('button', { name: '向深处走去' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '拔剑戒备' })).toBeInTheDocument()
  })
})
