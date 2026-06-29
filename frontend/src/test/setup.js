import '@testing-library/jest-dom/vitest'

// jsdom 26 (as wired by Vitest) does not expose localStorage/sessionStorage by
// default. The auth store (stores/auth.js) and the api interceptor both touch
// localStorage at import/runtime, so provide a minimal in-memory polyfill.
function makeStorage() {
  let store = {}
  return {
    getItem: (key) => (Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null),
    setItem: (key, value) => {
      store[key] = String(value)
    },
    removeItem: (key) => {
      delete store[key]
    },
    clear: () => {
      store = {}
    },
    key: (i) => Object.keys(store)[i] ?? null,
    get length() {
      return Object.keys(store).length
    },
  }
}

if (!globalThis.localStorage) {
  Object.defineProperty(globalThis, 'localStorage', { value: makeStorage(), configurable: true })
}
if (!globalThis.sessionStorage) {
  Object.defineProperty(globalThis, 'sessionStorage', { value: makeStorage(), configurable: true })
}

// jsdom does not implement URL.createObjectURL / revokeObjectURL; the
// asset-loading code paths in ProjectDetail call these, so stub them out.
if (typeof URL.createObjectURL !== 'function') {
  URL.createObjectURL = () => 'blob:mock'
}
if (typeof URL.revokeObjectURL !== 'function') {
  URL.revokeObjectURL = () => {}
}

// Smooth scroll is not implemented in jsdom.
if (typeof window !== 'undefined' && window.Element) {
  window.Element.prototype.scrollIntoView = window.Element.prototype.scrollIntoView || (() => {})
}

// AntD components (e.g. Progress) depend on ResizeObserver, which jsdom lacks.
if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}
if (typeof window !== 'undefined' && typeof window.ResizeObserver === 'undefined') {
  window.ResizeObserver = globalThis.ResizeObserver
}
