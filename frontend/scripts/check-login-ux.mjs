import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const login = readFileSync(resolve(root, 'src/pages/Login.jsx'), 'utf8')

const requiredSnippets = [
  'emailRules',
  'passwordRules',
  'type: \'email\'',
  'min: 8',
  '密码至少8位',
  'App.useApp',
]

const missing = requiredSnippets.filter((snippet) => !login.includes(snippet))

if (missing.length > 0) {
  console.error(`Login UX check failed. Missing: ${missing.join(', ')}`)
  process.exit(1)
}
