import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const readmePath = resolve(process.cwd(), '..', 'README.md')

if (!existsSync(readmePath)) {
  console.error('README check failed. Missing: README.md')
  process.exit(1)
}

const readme = readFileSync(readmePath, 'utf8')

const requiredSections = [
  '# novel2Animatic',
  '## 快速开始',
  '## 架构概览',
  '## 测试',
  '## 开发循环',
  '## 故障排查',
]

const missing = requiredSections.filter((snippet) => !readme.includes(snippet))

if (missing.length > 0) {
  console.error(`README check failed. Missing: ${missing.join(', ')}`)
  process.exit(1)
}

const requiredSnippets = [
  'authenticated blob URLs',
]

const missingSnippets = requiredSnippets.filter((snippet) => !readme.includes(snippet))

if (missingSnippets.length > 0) {
  console.error(`README check failed. Missing snippets: ${missingSnippets.join(', ')}`)
  process.exit(1)
}

const forbiddenSnippets = [
  'query-token',
  'query tokens',
]

const presentForbiddenSnippets = forbiddenSnippets.filter((snippet) => readme.includes(snippet))

if (presentForbiddenSnippets.length > 0) {
  console.error(`README check failed. Outdated snippets: ${presentForbiddenSnippets.join(', ')}`)
  process.exit(1)
}
