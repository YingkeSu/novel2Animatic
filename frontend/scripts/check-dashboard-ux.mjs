import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const dashboard = readFileSync(resolve(root, 'src/pages/Dashboard.jsx'), 'utf8')

const requiredSnippets = [
  'const statusMeta',
  'empty-state',
  '立即创建',
  'dashboard-toolbar',
  'latest_error_msg',
  'dashboard-card-error',
  'status === 409',
  '项目正在生成中，暂时无法删除',
]

const missing = requiredSnippets.filter((snippet) => !dashboard.includes(snippet))

if (missing.length > 0) {
  console.error(`Dashboard UX check failed. Missing: ${missing.join(', ')}`)
  process.exit(1)
}
