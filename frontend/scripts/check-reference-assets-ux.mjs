import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const projectDetail = readFileSync(resolve(root, 'src/pages/ProjectDetail.jsx'), 'utf8')

const requiredSnippets = [
  'referenceUrl',
  'referenceAsset',
  'reference.png',
  '/reference',
  'generate_refs',
  'Reference image',
]

const missing = requiredSnippets.filter((snippet) => !projectDetail.includes(snippet))

if (missing.length > 0) {
  console.error(`Reference assets UX check failed. Missing: ${missing.join(', ')}`)
  process.exit(1)
}
