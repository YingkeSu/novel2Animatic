# novel2Animatic

novel2Animatic turns a pasted novel excerpt into a short AI animatic: scene breakdown, generated still images, narrated audio, and an assembled MP4. The current app is a local-first MVP with user auth, project management, style selection, pipeline progress polling, and asset preview/download through authenticated API endpoints.

## 快速开始

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 16, or the provided Docker Compose service
- `ffmpeg` on `PATH` for video assembly
- A StepFun API key

Start local infrastructure:

```bash
docker compose up -d postgres redis
```

Redis is included in Compose and `REDIS_URL` exists in config, but the current pipeline does not use Redis or a worker process yet.

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cat > .env <<'EOF'
SECRET_KEY=replace-with-a-long-random-secret
STEPFUN_API_KEY=replace-with-your-stepfun-key
DATABASE_URL=postgresql+asyncpg://novel2animatic:novel2animatic@localhost:5432/novel2animatic
REDIS_URL=redis://localhost:6379/0
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
EOF

alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend exposes `/health`, `/api/auth/*`, `/api/projects/*`, `/api/styles`, and authenticated asset endpoints for generated images, audio, and video.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite serves the React app at `http://localhost:3000` and proxies `/api` to `http://localhost:8000`.

## 架构概览

- `frontend/`: React + Vite + Ant Design SPA. It provides login/register, project dashboard, project creation, style selection, pipeline start/retry, progress polling, scene preview, audio playback, and final video preview.
- `backend/app/main.py`: FastAPI entrypoint with CORS and routers for auth, projects, pipeline, styles, and assets.
- `backend/app/models/`: SQLAlchemy async models for users, projects, scenes, assets, and tasks.
- `backend/app/services/stepfun_client.py`: OpenAI-compatible StepFun client for LLM, image generation/editing, and TTS.
- `backend/app/services/pipeline.py`: in-process async pipeline launched with `asyncio.create_task`; it writes generated files under `backend/storage/{user_id}/{project_id}/`.
- `backend/styles/`: YAML style plugins grouped by `writing`, `visual`, and `audio`.
- `docker-compose.yml`: local PostgreSQL and Redis services.

The current implementation stores metadata in PostgreSQL and generated files on local disk. `ARCHITECTURE.md` describes a broader target architecture with Celery, Redis-backed jobs, SSE, and MinIO; those pieces are not fully wired into the current runtime. The pipeline runs in-process via `asyncio.create_task` (no external worker), passwords use PBKDF2 (not bcrypt), only JWT access tokens are issued (no refresh tokens), and progress is polled via `/api/projects/{id}/progress` (SSE exists but is not on the active generation path). For the authoritative description of the current runtime, see [`CLAUDE.md`](./CLAUDE.md); where `ARCHITECTURE.md` and `CLAUDE.md` disagree, `CLAUDE.md` is the source of truth.

## Environment Variables

Required:

- `SECRET_KEY`: JWT signing secret. Use a long random value outside tests.
- `STEPFUN_API_KEY`: API key used by `StepFunClient`.

Common optional/defaulted settings:

- `DATABASE_URL`: defaults to `postgresql+asyncpg://novel2animatic:novel2animatic@localhost:5432/novel2animatic`.
- `REDIS_URL`: defaults to `redis://localhost:6379/0`; currently reserved for planned worker/progress infrastructure.
- `STEPFUN_BASE_URL`: defaults to `https://api.stepfun.com/step_plan/v1`.
- `ALGORITHM`: defaults to `HS256`.
- `ACCESS_TOKEN_EXPIRE_MINUTES`: defaults to `15`; must be a positive integer.
- `CORS_ALLOWED_ORIGINS`: comma-separated list accepted by the settings parser. Defaults include localhost/127.0.0.1 on ports `3000` and `5173`, plus `http://test` for tests.

`backend/app/config.py` loads `.env` via Pydantic settings. When following the backend quick start, place `.env` in `backend/`.

## Style Plugins And Pipeline

Style plugins are YAML files loaded safely from `backend/styles`:

- `writing/*.yaml`: scene split and writing prompts for the StepFun LLM.
- `visual/*.yaml`: prompt suffixes for image generation.
- `audio/*.yaml`: TTS voice, instruction, speed, and volume.

Project source text must contain at least `80 个字符` after trimming before scene splitting; the frontend and backend both enforce this minimum so the pipeline can split scenes stably.

Current pipeline flow:

1. Split source text into scenes with StepFun `step-3.7-flash`; invalid or empty JSON falls back to one safe scene.
2. Generate a project-level character/reference image as `reference.png` for visual continuity.
3. Generate one image per scene with `step-image-edit-2` using each scene prompt plus the selected visual suffix.
4. Generate one MP3 narration per scene with `stepaudio-2.5-tts` and selected audio parameters.
5. Assemble scene images and audio into MP4 segments, then concatenate them into `final.mp4` with `ffmpeg`.

Progress is persisted in the `tasks` table and polled by the frontend through `GET /api/projects/{id}/progress`.

## 测试

Backend tests expect PostgreSQL to be running and use the hard-coded test database `novel2animatic_test` from `backend/tests/conftest.py`.

```bash
createdb -h localhost -U novel2animatic novel2animatic_test

cd backend
source .venv/bin/activate
python -m pytest tests
```

Migration and frontend checks:

```bash
node scripts/check-alembic.mjs

cd frontend
npm run check
npm run docs:check
```

`npm run check` runs the dashboard UX check and a Vite production build. `npm run docs:check` verifies this README contains required top-level sections.

## 开发循环

Use the same local services as quick start, then run focused checks before handing off changes:

```bash
docker compose up -d postgres redis

cd backend
source .venv/bin/activate
python -m pytest tests
node scripts/check-alembic.mjs

cd ../frontend
npm run check
npm run docs:check
```

Backend feature changes should include or update the matching pytest coverage and pass the Alembic check when models or migrations change. Frontend changes should pass `npm run check`; README or runbook changes should pass `npm run docs:check`. For pipeline work, also verify the required local tools and StepFun credentials from quick start before starting a generation job.

## 故障排查

- PostgreSQL tests: ensure the Compose PostgreSQL service is running and create `novel2animatic_test` before `python -m pytest tests`. If `createdb` fails because the database already exists, reuse it or drop/recreate it intentionally.
- Missing env: backend runtime requires `backend/.env` with at least `SECRET_KEY` and `STEPFUN_API_KEY`. Keep `DATABASE_URL` aligned with the local PostgreSQL user, password, host, and database.
- `ffmpeg`: video assembly requires `ffmpeg` on `PATH`. If pipeline jobs reach video assembly and fail, run `ffmpeg -version` from the same shell that starts `uvicorn`.
- StepFun API: invalid, missing, or quota-limited `STEPFUN_API_KEY` can fail scene splitting, image generation, or TTS. `STEPFUN_BASE_URL` defaults to the StepFun endpoint listed above; only override it when testing against a compatible API.
- Vite proxy/API connection: the frontend expects the backend at `http://localhost:8000` for `/api` during local dev. Start `uvicorn` first, check `/health`, and keep `CORS_ALLOWED_ORIGINS` including the Vite origin you use.
- Local generated assets: generated files are stored under `backend/storage/{user_id}/{project_id}/` and served only through authenticated project asset routes. Asset records pointing outside the storage root are rejected, and browser previews load media through authenticated blob URLs.

## Security Notes

- `SECRET_KEY` and `STEPFUN_API_KEY` are required at runtime and must not be committed.
- CORS rejects origins outside `CORS_ALLOWED_ORIGINS`; keep production origins explicit.
- Project, progress, and asset routes enforce user ownership. Asset routes remain authenticated, and browser previews load media through authenticated blob URLs.
- Passwords are stored as hashes, and access tokens expire according to the positive-integer `ACCESS_TOKEN_EXPIRE_MINUTES` setting.
- Style plugin loading rejects path traversal and only reads single-component YAML names from the configured styles directory.

## Known Limitations

- Pipeline execution is in-process. A server restart cancels active jobs, and there is no external worker, retry queue, or concurrency control yet.
- Redis, Celery, SSE, and MinIO are dependencies or architecture targets but are not part of the active pipeline path.
- Generated asset paths are local filesystem paths, so deployment needs persistent shared storage before scaling beyond one backend instance.
