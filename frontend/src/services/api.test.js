import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

// api.js installs response interceptors that read window.location and localStorage.
// Because the module reads these at module-evaluation time only through interceptors,
// importing it once and exercising the live axios instance is enough.
import api from './api'

describe('api axios instance — 401 handling', () => {
  let originalLocation
  let getItemSpy

  beforeEach(() => {
    originalLocation = window.location
    localStorage.clear()
    getItemSpy = vi.spyOn(Storage.prototype, 'getItem')
  })

  afterEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('clears the token and redirects to /login on a 401 when not already on /login', async () => {
    // Simulate a logged-in user carrying a token.
    localStorage.setItem('token', 'stale-token')
    getItemSpy.mockReturnValue('stale-token')

    // Force the request adapter to resolve with a 401 so the response-error
    // interceptor runs. We point at /api via baseURL; the adapter short-circuits
    // any real network call.
    api.defaults.adapter = (config) =>
      Promise.reject({
        response: { status: 401, data: {}, headers: {}, config },
        config,
        isAxiosError: true,
        message: 'Request failed with status code 401',
      })

    // Pretend we are somewhere other than /login.
    Object.defineProperty(window, 'location', {
      value: { ...originalLocation, pathname: '/project/123', href: '/project/123' },
      writable: true,
    })

    const hrefSetter = vi.fn()
    Object.defineProperty(window.location, 'href', {
      get: () => '/project/123',
      set: hrefSetter,
      configurable: true,
    })

    await expect(api.get('/projects')).rejects.toBeTruthy()

    expect(localStorage.getItem('token')).toBeNull()
    expect(hrefSetter).toHaveBeenCalledWith('/login')
  })

  it('does NOT redirect when already on /login (Login component handles the error)', async () => {
    localStorage.setItem('token', 'stale-token')

    api.defaults.adapter = (config) =>
      Promise.reject({
        response: { status: 401, data: {}, headers: {}, config },
        config,
        isAxiosError: true,
        message: 'Request failed with status code 401',
      })

    Object.defineProperty(window, 'location', {
      value: { ...originalLocation, pathname: '/login', href: '/login' },
      writable: true,
    })

    const hrefSetter = vi.fn()
    Object.defineProperty(window.location, 'href', {
      get: () => '/login',
      set: hrefSetter,
      configurable: true,
    })

    await expect(api.get('/auth/login')).rejects.toBeTruthy()

    // Token is still cleared (user is unauthenticated) ...
    expect(localStorage.getItem('token')).toBeNull()
    // ... but no navigation occurs — the Login component shows the error itself.
    expect(hrefSetter).not.toHaveBeenCalled()
  })

  it('attaches the Bearer token to requests when one is present', async () => {
    localStorage.setItem('token', 'abc123')
    let capturedConfig
    api.defaults.adapter = (config) => {
      capturedConfig = config
      return Promise.resolve({ data: {}, status: 200, statusText: 'OK', headers: {}, config })
    }

    await api.get('/projects')

    expect(capturedConfig.headers.Authorization).toBe('Bearer abc123')
  })
})
