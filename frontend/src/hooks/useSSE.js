import { useEffect, useRef, useState, useCallback } from 'react'

/**
 * Parse a single SSE frame (the text between two `\n\n` separators) into an
 * event object `{ event, data }`. Lines starting with `:` are comments
 * (keepalive heartbeats) and are ignored. Multiple `data:` lines are joined
 * with `\n` per the SSE spec.
 *
 * Exported for unit testing.
 */
export function parseSseFrame(frame) {
  const event = { event: 'message', data: '' }
  const dataLines = []
  for (const rawLine of frame.split('\n')) {
    if (!rawLine || rawLine.startsWith(':')) continue
    const idx = rawLine.indexOf(':')
    const field = idx === -1 ? rawLine : rawLine.slice(0, idx)
    // Per spec, a leading space after the colon is stripped.
    let value = idx === -1 ? '' : rawLine.slice(idx + 1)
    if (value.startsWith(' ')) value = value.slice(1)
    if (field === 'event') {
      event.event = value
    } else if (field === 'data') {
      dataLines.push(value)
    }
  }
  event.data = dataLines.join('\n')
  return event
}

/**
 * useSSE(projectId) — consume `/api/projects/{projectId}/events` via
 * fetch + ReadableStream with manual SSE frame parsing.
 *
 * Why not EventSource: EventSource cannot set the `Authorization` header, and
 * this app authenticates via a Bearer token in localStorage (same constraint
 * as the asset routes, which are fetched as authenticated blobs). So we use
 * fetch and parse the stream by hand.
 *
 * Behaviour:
 * - On mount (and after any reconnection), the caller is expected to do ONE
 *   `GET /progress` to recover current state — this hook deliberately does
 *   NOT poll. It exposes `connected` so the caller can trigger that recovery.
 * - Auto-reconnects on disconnect / network error with capped backoff.
 * - Returns `{ connected, lastEvent, close }`.
 *
 * @param {string|number|null|undefined} projectId — null/undefined disables.
 * @param {(event) => void} [onEvent] — invoked for every parsed SSE event.
 */
export default function useSSE(projectId, onEvent) {
  const [connected, setConnected] = useState(false)
  const [lastEvent, setLastEvent] = useState(null)
  const onEventRef = useRef(onEvent)
  const abortedRef = useRef(false)
  const reconnectTimerRef = useRef(null)
  const attemptRef = useRef(0)
  const activeControllerRef = useRef(null)

  // Keep the latest onEvent without re-subscribing on every render.
  useEffect(() => {
    onEventRef.current = onEvent
  }, [onEvent])

  const close = useCallback(() => {
    abortedRef.current = true
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
  }, [])

  useEffect(() => {
    abortedRef.current = false
    if (projectId === null || projectId === undefined) {
      setConnected(false)
      return
    }

    const base = import.meta.env.BASE_URL || '/'
    const url = `${base}api/projects/${projectId}/events`

    const connect = async () => {
      if (abortedRef.current) return
      const token = localStorage.getItem('token')
      const headers = { Accept: 'text/event-stream' }
      if (token) headers.Authorization = `Bearer ${token}`

      // AbortController lets cleanup cancel the in-flight fetch + reader
      // immediately on unmount (rather than waiting for the next chunk/close),
      // and keeps the connect closure from touching state post-unmount.
      const controller = new AbortController()
      activeControllerRef.current = controller

      let response
      try {
        response = await fetch(url, { headers, signal: controller.signal })
      } catch (e) {
        // An intentional abort during unmount is not a reconnect-worthy error.
        if (abortedRef.current || controller.signal.aborted) return
        scheduleReconnect()
        return
      }
      if (!response.ok || !response.body) {
        // 401 etc. — let the api interceptor-equivalent handle redirect in the
        // caller; for non-auth errors we retry.
        if (!abortedRef.current) scheduleReconnect()
        return
      }

      if (abortedRef.current) {
        controller.abort()
        return
      }

      setConnected(true)
      attemptRef.current = 0

      const reader = response.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''

      try {
        while (true) {
          if (abortedRef.current) break
          const { value, done } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })

          // Frames are separated by a blank line. The stream may split a frame
          // across chunks, so only complete frames are dispatched.
          let sep
          while ((sep = buffer.indexOf('\n\n')) !== -1) {
            const frame = buffer.slice(0, sep)
            buffer = buffer.slice(sep + 2)
            if (!frame.trim()) continue
            const parsed = parseSseFrame(frame)
            // data is JSON in our protocol; fall back to raw string if parse fails.
            let payload = parsed.data
            if (parsed.data) {
              try {
                payload = JSON.parse(parsed.data)
              } catch {
                payload = parsed.data
              }
            }
            const evt = { type: parsed.event, data: payload }
            setLastEvent(evt)
            if (onEventRef.current) onEventRef.current(evt)
          }
        }
      } catch (e) {
        // Network drop / read error — fall through to reconnect.
      } finally {
        try {
          reader.releaseLock()
        } catch {
          // already released
        }
      }

      if (!abortedRef.current) {
        setConnected(false)
        scheduleReconnect()
      }
    }

    const scheduleReconnect = () => {
      if (abortedRef.current) return
      // Capped exponential backoff: 1s, 2s, 4s, ... up to 15s.
      const delay = Math.min(1000 * 2 ** attemptRef.current, 15000)
      attemptRef.current += 1
      reconnectTimerRef.current = setTimeout(() => {
        reconnectTimerRef.current = null
        connect()
      }, delay)
    }

    connect()

    return () => {
      abortedRef.current = true
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      // Cancel any in-flight fetch / reader so the connect closure stops
      // touching state after unmount. Guarded: abort() is a no-op if already
      // aborted, and we clear the ref so the next connect starts fresh.
      try {
        if (activeControllerRef.current) {
          activeControllerRef.current.abort()
        }
      } catch {
        // already aborted — ignore
      }
      activeControllerRef.current = null
      setConnected(false)
    }
  }, [projectId])

  return { connected, lastEvent, close }
}
