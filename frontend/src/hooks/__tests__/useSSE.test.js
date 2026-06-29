import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import useSSE, { parseSseFrame } from '../useSSE'

// Build a ReadableStream that emits `chunks` then either closes (`closes=true`,
// the default — simulates the server ending the stream) or stays open (so
// `connected` remains true and we can assert on it).
function makeReadableStream(chunks, { closes = true } = {}) {
  const sent = [...chunks]
  return new ReadableStream({
    start(controller) {
      const pump = () => {
        if (sent.length === 0) {
          if (closes) controller.close()
          return
        }
        controller.enqueue(new TextEncoder().encode(sent.shift()))
        setTimeout(pump, 0)
      }
      setTimeout(pump, 0)
    },
  })
}

function mockFetchStream(chunks, opts) {
  return vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      body: makeReadableStream(chunks, opts),
    })
  )
}

describe('parseSseFrame', () => {
  it('parses event + JSON data lines', () => {
    const frame = 'event: progress\ndata: {"step":"generate_refs","progress":25}'
    const parsed = parseSseFrame(frame)
    expect(parsed.event).toBe('progress')
    expect(parsed.data).toBe('{"step":"generate_refs","progress":25}')
  })

  it('ignores comment (keepalive) lines', () => {
    const parsed = parseSseFrame(': connected\nevent: complete\ndata: {}')
    expect(parsed.event).toBe('complete')
  })

  it('joins multiple data: lines with newline', () => {
    const parsed = parseSseFrame('data: a\ndata: b')
    expect(parsed.data).toBe('a\nb')
  })

  it('defaults event to message', () => {
    expect(parseSseFrame('data: x').event).toBe('message')
  })
})

describe('useSSE', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'test-token')
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('consumes a streamed SSE frame, parses JSON, and dispatches via onEvent', async () => {
    const onEvent = vi.fn()
    const fetchMock = mockFetchStream([
      ': connected\n\n',
      'event: progress\ndata: {"step":"generate_images","progress":40,"status":"running"}\n\n',
    ])
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderHook(() => useSSE('7', onEvent))

    await waitFor(() => {
      const progressCalls = onEvent.mock.calls.filter((c) => c[0].type === 'progress')
      expect(progressCalls.length).toBe(1)
    })

    const evt = onEvent.mock.calls.find((c) => c[0].type === 'progress')[0]
    expect(evt.data).toEqual({ step: 'generate_images', progress: 40, status: 'running' })
    expect(result.current.lastEvent.type).toBe('progress')
    expect(result.current.lastEvent.data).toEqual({
      step: 'generate_images',
      progress: 40,
      status: 'running',
    })
  })

  it('attaches the Bearer token from localStorage and targets the events URL', async () => {
    const fetchMock = mockFetchStream([': connected\n\n'])
    vi.stubGlobal('fetch', fetchMock)

    renderHook(() => useSSE('42'))
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/api/projects/42/events')
    expect(init.headers.Authorization).toBe('Bearer test-token')
    expect(init.headers.Accept).toBe('text/event-stream')
  })

  it('does not connect when projectId is null', async () => {
    const fetchMock = mockFetchStream([])
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useSSE(null))
    expect(result.current.connected).toBe(false)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('dispatches a terminal complete event', async () => {
    const onEvent = vi.fn()
    const fetchMock = mockFetchStream([
      'event: complete\ndata: {"status":"done","project_id":7}\n\n',
    ])
    vi.stubGlobal('fetch', fetchMock)

    renderHook(() => useSSE('7', onEvent))
    await waitFor(() => {
      expect(onEvent.mock.calls.some((c) => c[0].type === 'complete')).toBe(true)
    })
    const complete = onEvent.mock.calls.find((c) => c[0].type === 'complete')[0]
    expect(complete.data).toEqual({ status: 'done', project_id: 7 })
  })

  it('auto-reconnects after a network error', async () => {
    let calls = 0
    const fetchMock = vi.fn(() => {
      calls += 1
      if (calls === 1) {
        return Promise.reject(new Error('network down'))
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        body: makeReadableStream([': connected\n\n']),
      })
    })
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderHook(() => useSSE('7'))
    // After the rejected first attempt, the hook back off and retries; the
    // second attempt succeeds and dispatches the keepalive.
    await waitFor(() => expect(result.current.lastEvent || calls >= 2).toBeTruthy(), {
      timeout: 5000,
    })
    expect(calls).toBeGreaterThanOrEqual(2)
  })
})
