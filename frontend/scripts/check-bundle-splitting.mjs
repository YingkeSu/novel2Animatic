import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const checkDist = process.argv.includes('--dist')
const app = readFileSync(resolve(root, 'src/App.jsx'), 'utf8')

const requiredAppSnippets = [
  'React.lazy',
  '<Suspense',
  "import('./pages/Login')",
  "import('./pages/Dashboard')",
  "import('./pages/CreateProject')",
  "import('./pages/ProjectDetail')",
]

const missingAppSnippets = requiredAppSnippets.filter((snippet) => !app.includes(snippet))

if (missingAppSnippets.length > 0) {
  console.error(`Bundle splitting check failed. Missing App.jsx snippets: ${missingAppSnippets.join(', ')}`)
  process.exit(1)
}

const assetsDir = resolve(root, 'dist/assets')

if (!checkDist) {
  process.exit(0)
}

if (!existsSync(assetsDir)) {
  console.error('Bundle splitting check failed. Build assets directory is missing.')
  process.exit(1)
}

const jsAssets = readdirSync(assetsDir)
  .filter((file) => file.endsWith('.js'))
  .map((file) => ({
    file,
    size: statSync(resolve(assetsDir, file)).size,
  }))

if (jsAssets.length < 2) {
  console.error('Bundle splitting check failed. Expected at least two JavaScript assets after build.')
  process.exit(1)
}

const oversizedAssets = jsAssets.filter((asset) => asset.size > 500 * 1024)

if (oversizedAssets.length > 0) {
  const formatted = oversizedAssets
    .map((asset) => `${asset.file} (${Math.round(asset.size / 1024)} kB)`)
    .join(', ')

  console.error(`Bundle splitting check failed. JavaScript assets over 500 kB: ${formatted}`)
  process.exit(1)
}
