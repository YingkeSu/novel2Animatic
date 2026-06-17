import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const createProject = readFileSync(resolve(root, 'src/pages/CreateProject.jsx'), 'utf8')

const requiredSnippets = [
  'style-description',
  'source-text-meter',
  'sourceTextLength',
  'styleLoadError',
  'disabled={styleLoading || loading}',
  'minimumSceneTextLength',
  'maximumProjectTitleLength',
  'max: maximumProjectTitleLength',
  'sourceTextRules',
  'validateSourceTextLength',
  'whitespace: true',
]

const missing = requiredSnippets.filter((snippet) => !createProject.includes(snippet))

if (missing.length > 0) {
  console.error(`Create project UX check failed. Missing: ${missing.join(', ')}`)
  process.exit(1)
}

if (!/if \(!sourceText\) \{\s*return Promise\.resolve\(\)\s*\}/m.test(createProject)) {
  console.error('Create project UX check failed. Empty source text must be handled by the required rule only.')
  process.exit(1)
}
