import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const projectDetail = readFileSync(resolve(root, 'src/pages/ProjectDetail.jsx'), 'utf8')

const requiredSnippets = [
  'loadAuthenticatedAssetUrl',
  'assetLoading',
  'URL.createObjectURL',
  'assetError',
]

const forbiddenSnippets = [
  '?token=',
]

const missing = requiredSnippets.filter((snippet) => !projectDetail.includes(snippet))
const forbidden = forbiddenSnippets.filter((snippet) => projectDetail.includes(snippet))

if (missing.length > 0 || forbidden.length > 0) {
  if (missing.length > 0) {
    console.error(`Asset auth UX check failed. Missing: ${missing.join(', ')}`)
  }
  if (forbidden.length > 0) {
    console.error(`Asset auth UX check failed. Forbidden: ${forbidden.join(', ')}`)
  }
  process.exit(1)
}
