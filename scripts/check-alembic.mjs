import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')

const requiredFiles = [
  'backend/alembic.ini',
  'backend/alembic/env.py',
  'backend/alembic/script.py.mako',
  'backend/alembic/versions/0001_initial_schema.py',
]

const missing = requiredFiles.filter((file) => !existsSync(resolve(root, file)))

const revisions = existsSync(resolve(root, 'backend/alembic/versions'))
  ? readdirSync(resolve(root, 'backend/alembic/versions')).filter((file) => file.endsWith('.py'))
  : []

const env = existsSync(resolve(root, 'backend/alembic/env.py'))
  ? readFileSync(resolve(root, 'backend/alembic/env.py'), 'utf8')
  : ''

const initialRevision = existsSync(resolve(root, 'backend/alembic/versions/0001_initial_schema.py'))
  ? readFileSync(resolve(root, 'backend/alembic/versions/0001_initial_schema.py'), 'utf8')
  : ''

const readme = readFileSync(resolve(root, 'README.md'), 'utf8')

const requiredSnippets = [
  [env, 'target_metadata = Base.metadata', 'env.py target_metadata'],
  [env, 'async_engine_from_config', 'env.py async migration engine'],
  [initialRevision, 'revision = "0001_initial_schema"', 'initial revision id'],
  [initialRevision, 'op.create_table("users"', 'users migration'],
  [initialRevision, 'op.create_table("projects"', 'projects migration'],
  [initialRevision, 'op.create_table("assets"', 'assets migration'],
  [readme, 'alembic upgrade head', 'README migration command'],
]

const missingSnippets = requiredSnippets
  .filter(([content, snippet]) => !content.includes(snippet))
  .map(([, , label]) => label)

if (missing.length > 0 || revisions.length === 0 || missingSnippets.length > 0) {
  if (missing.length > 0) {
    console.error(`Alembic check failed. Missing files: ${missing.join(', ')}`)
  }
  if (revisions.length === 0) {
    console.error('Alembic check failed. No migration revisions found.')
  }
  if (missingSnippets.length > 0) {
    console.error(`Alembic check failed. Missing snippets: ${missingSnippets.join(', ')}`)
  }
  process.exit(1)
}
