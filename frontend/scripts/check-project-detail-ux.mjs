import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const projectDetail = readFileSync(resolve(root, 'src/pages/ProjectDetail.jsx'), 'utf8')
const theme = readFileSync(resolve(root, 'src/styles/theme.css'), 'utf8')

const componentSnippets = [
  'pollIntervalRef',
  'clearPollInterval',
  "setImageUrl('')",
  "setAudioUrl('')",
  'detailLoading',
  'detailError',
  'isNotFound',
  'pipelineFailure',
  'taskProgress?.error_msg',
  'project-detail-failure',
  'project-detail-state',
  'project-detail-page',
  'project-detail-main',
  'project-detail-sidebar',
  'project-detail-preview',
  'project-detail-video-panel',
  'project-detail-prompt-panel',
  'selectedScene.edit_prompt',
  'selectedScene.instruction',
  'selectedScene.text',
  'loadProjectProgress',
  'project.status === \'running\'',
  'pipeline.progress(id)',
  'pollProgress()',
  'NON_TERMINAL_TASK_STATUSES',
  "['pending', 'running']",
  'isNonTerminalTaskStatus(taskProgress?.status)',
  'isNonTerminalTaskStatus(res.data.status)',
  'project-detail-asset-status',
  '正在加载当前场景媒体',
  'aria-live="polite"',
  'sceneAssetLoadingCount',
  'sceneAssetError',
  'loadSceneAssetUrl',
  '当前场景媒体加载失败',
  'sceneAssetRequestRef',
  'requestKey !== sceneAssetRequestRef.current',
  'sceneAssetSceneSeq',
  'currentSceneOwnsAssetStatus',
  'sceneAssetSceneSeq === selectedScene.seq',
]

const styleSnippets = [
  '.project-detail-state',
  '.project-detail-state-card',
  '.project-detail-failure',
  '.project-detail-main',
  '.project-detail-sidebar',
  '.project-detail-video-panel',
  '.project-detail-prompt-panel',
  '.project-detail-asset-status',
  '@media (max-width: 900px)',
  'grid-template-columns: 1fr',
]

const missingComponent = componentSnippets.filter((snippet) => !projectDetail.includes(snippet))
const missingStyle = styleSnippets.filter((snippet) => !theme.includes(snippet))

if (missingComponent.length > 0 || missingStyle.length > 0) {
  if (missingComponent.length > 0) {
    console.error(`Project detail UX check failed. Missing component snippets: ${missingComponent.join(', ')}`)
  }
  if (missingStyle.length > 0) {
    console.error(`Project detail UX check failed. Missing style snippets: ${missingStyle.join(', ')}`)
  }
  process.exit(1)
}
