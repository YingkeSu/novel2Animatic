import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const app = readFileSync(resolve(root, 'src/App.jsx'), 'utf8')
const theme = readFileSync(resolve(root, 'src/styles/theme.css'), 'utf8')

const appSnippets = [
  'RouteLoading',
  'fallback={<RouteLoading />}',
  'route-loading',
  'role="status"',
  'aria-live="polite"',
]

const styleSnippets = [
  '.route-loading',
  '.route-loading-mark',
  '.route-loading-title',
]

const missingApp = appSnippets.filter((snippet) => !app.includes(snippet))
const missingStyle = styleSnippets.filter((snippet) => !theme.includes(snippet))

if (app.includes('fallback={null}')) {
  console.error('Route loading UX check failed. Suspense fallback must not be null.')
  process.exit(1)
}

if (missingApp.length > 0 || missingStyle.length > 0) {
  if (missingApp.length > 0) {
    console.error(`Route loading UX check failed. Missing App.jsx snippets: ${missingApp.join(', ')}`)
  }
  if (missingStyle.length > 0) {
    console.error(`Route loading UX check failed. Missing style snippets: ${missingStyle.join(', ')}`)
  }
  process.exit(1)
}
