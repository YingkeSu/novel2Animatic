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
]

const missing = requiredSections.filter((snippet) => !readme.includes(snippet))

if (missing.length > 0) {
  console.error(`README check failed. Missing: ${missing.join(', ')}`)
  process.exit(1)
}
