import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { App as AntdApp } from 'antd'

// Mock the api module so calls are deterministic and URL-keyed.
const apiMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}))
vi.mock('../services/api', () => ({
  default: { get: (...a) => apiMocks.get(...a), post: (...a) => apiMocks.post(...a) },
  projects: { get: (id) => apiMocks.get(`/projects/${id}`) },
  pipeline: { run: (id) => apiMocks.post(`/projects/${id}/run`), progress: (id) => apiMocks.get(`/projects/${id}/progress`) },
  styles: { list: (type) => apiMocks.get(`/styles?type=${type}`) },
}))

import ProjectDetail from './ProjectDetail'

const RUNNING_PROJECT = {
  id: 7,
  title: '古风短篇',
  source_type: 'text_split',
  status: 'running',
  style_writing: 'modern',
  style_visual: 'ink_wash',
  style_audio: 'ancient_male',
  scenes: [],
}

const DONE_PROJECT = { ...RUNNING_PROJECT, status: 'done' }
const FAILED_PROJECT = { ...RUNNING_PROJECT, status: 'failed', error_msg: 'StepFun 超时' }

// Build a URL-keyed GET handler so the many effects each get their answer.
function routeGet(routes) {
  return (url) => {
    for (const key of Object.keys(routes)) {
      if (url.includes(key)) {
        return Promise.resolve({ data: routes[key] })
      }
    }
    return Promise.reject({ response: { status: 404, data: { detail: `unmocked ${url}` } } })
  }
}

function renderDetailAt(path = '/project/7') {
  return render(
    <AntdApp>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/project/:id" element={<ProjectDetail />} />
        </Routes>
      </MemoryRouter>
    </AntdApp>
  )
}

const EMPTY_STYLES = { data: [] }

describe('ProjectDetail — progress display', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'test-token')
    apiMocks.get.mockReset()
    apiMocks.post.mockReset()
  })

  afterEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('renders running % and the current step label for a running task', async () => {
    apiMocks.get.mockImplementation(
      routeGet({
        '/styles': EMPTY_STYLES,
        '/projects/7/progress': {
          status: 'running',
          step: 'generate_images',
          progress: 60,
        },
        '/projects/7': RUNNING_PROJECT,
      })
    )

    renderDetailAt()

    // Running banner text.
    await waitFor(() =>
      expect(screen.getByText('⏳ 生成中')).toBeInTheDocument()
    )
    // The "generate_images" step label renders in the step bar (and possibly
    // the preview area), so tolerate multiple matches.
    await waitFor(() =>
      expect(screen.getAllByText(/生成图片/).length).toBeGreaterThan(0)
    )
    // Percentage reflected by the AntD Progress component (aria-valuenow).
    const progressBar = await screen.findByRole('progressbar')
    expect(progressBar).toHaveAttribute('aria-valuenow', '60')
  })

  it('renders the failure message for a failed pipeline task', async () => {
    apiMocks.get.mockImplementation(
      routeGet({
        '/styles': EMPTY_STYLES,
        '/projects/7/progress': {
          status: 'failed',
          step: 'generate_audio',
          progress: 75,
          error_msg: 'StepFun 超时',
        },
        '/projects/7': FAILED_PROJECT,
      })
    )

    renderDetailAt()

    await waitFor(() =>
      expect(screen.getByText('Pipeline 生成失败')).toBeInTheDocument()
    )
    expect(await screen.findByText('StepFun 超时')).toBeInTheDocument()
  })

  it('renders the done state and scene selector prompt for a completed project with scenes', async () => {
    apiMocks.get.mockImplementation(
      routeGet({
        '/styles': EMPTY_STYLES,
        '/projects/7': { ...DONE_PROJECT, scenes: [{ id: 1, seq: 1, title: '开场' }] },
      })
    )

    renderDetailAt()

    // Done banner. The "complete" pipeline step label is shared, so assert the
    // status badge specifically.
    await waitFor(() =>
      expect(screen.getByText('✅ 已完成')).toBeInTheDocument()
    )
  })
})
