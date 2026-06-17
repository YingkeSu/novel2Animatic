# novel2Animatic — 技术架构方案

## 一、项目定位

将网络小说/文段自动转化为 AI 手书短剧（静态图 + 配音旁白 + 视频），支持文风/画风/音频风格插件切换，多用户隔离。

MVP 并发：常态 5，峰值 20。

---

## 二、整体架构

```
┌─────────────────────────────────────────────────────────┐
│                  前端 (React + Vite)                      │
│  登录/注册 │ 项目列表 │ 创作工作台 │ 风格选择 │ 进度/预览  │
└────────────────────────┬────────────────────────────────┘
                         │ REST API / SSE(进度推送)
┌────────────────────────▼────────────────────────────────┐
│              后端 (FastAPI + Celery + Redis)               │
│                                                           │
│  ┌─────────┐  ┌──────────┐  ┌─────────────────────────┐  │
│  │ Auth    │  │ Project  │  │ Pipeline Orchestrator    │  │
│  │ JWT/RBAC│  │ CRUD     │  │ (Celery chain)           │  │
│  └─────────┘  └──────────┘  └─────────────────────────┘  │
│                                                           │
│  ┌───────────────────────────────────────────────────┐    │
│  │              StepFun API Client                    │    │
│  │  Base: https://api.stepfun.com/step_plan/v1       │    │
│  │  ┌─────────────┐ ┌──────────────┐ ┌────────────┐  │    │
│  │  │ LLM         │ │ Image Gen    │ │ TTS        │  │    │
│  │  │ step-3.7-   │ │ step-image-  │ │ stepaudio- │  │    │
│  │  │ flash       │ │ edit-2       │ │ 2.5-tts    │  │    │
│  │  └─────────────┘ └──────────────┘ └────────────┘  │    │
│  └───────────────────────────────────────────────────┘    │
│                                                           │
│  ┌───────────┐  ┌─────────────┐  ┌──────────────────┐    │
│  │ Style     │  │ FFmpeg      │  │ Progress Tracker │    │
│  │ Plugin    │  │ Video Asm   │  │ (Redis + SSE)    │    │
│  │ System    │  │             │  │                   │    │
│  └───────────┘  └─────────────┘  └──────────────────┘    │
└────────────────────────────┬─────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────┐
│                       存储层                              │
│  PostgreSQL (用户/项目/任务)  │  MinIO (图片/音频/视频)    │
└──────────────────────────────────────────────────────────┘
```

---

## 三、技术栈

| 层       | 选型                         | 说明                          |
|----------|------------------------------|-------------------------------|
| 前端     | React + Vite + Ant Design    | SPA, 快速开发                 |
| 后端框架  | FastAPI                      | 异步, 高性能, OpenAPI 自带文档 |
| 任务队列  | Celery + Redis               | 并发控制, 重试, 链式任务       |
| 数据库   | PostgreSQL                   | 多用户隔离, JSON 字段灵活      |
| 对象存储  | MinIO (兼容 S3)              | 图片/音频/视频存储             |
| LLM      | StepFun step-3.7-flash       | 拆场景 + 文风变换              |
| 图像     | StepFun step-image-edit-2    | 场景图生成                     |
| TTS      | StepFun stepaudio-2.5-tts    | 旁白音频                       |
| 视频合成  | ffmpeg                       | 图片+音频→mp4→concat          |
| 进度推送  | SSE (Server-Sent Events)     | 实时进度                       |

---

## 四、StepFun API 统一客户端

所有 AI 能力走同一个 endpoint：

```python
# config
STEPFUN_BASE_URL = "https://api.stepfun.com/step_plan/v1"
STEPFUN_API_KEY  = "..."  # 从环境变量读取

# 三个模型
LLM_MODEL   = "step-3.7-flash"
IMAGE_MODEL = "step-image-edit-2"
TTS_MODEL   = "stepaudio-2.5-tts"
```

封装为统一的 `StepFunClient` 类，内部按能力分方法：
- `client.llm.chat(messages, **kwargs)` → 文本
- `client.image.generate(prompt, **kwargs)` → 图片 b64/url
- `client.image.edit(image, prompt, **kwargs)` → 图片
- `client.tts.speak(text, voice, **kwargs)` → 音频 bytes

---

## 五、Pipeline 五步链

```
用户输入文段
    │
    ▼
[Step 1] LLM 拆场景 ──────────────────────────────────────
    输入: 原始文段 + 文风插件 prompt
    输出: scene_data.json (每场景: title, text, shot_type,
          character, narration, edit_prompt, instruction)
    模型: step-3.7-flash
    文风: 注入 system prompt (古风/现代/武侠/玄幻 模板)

    │
    ▼
[Step 2] 角色参考图生成 ────────────────────────────────────
    输入: character profiles (name + 外貌描述)
    输出: ref_{name}.png (角色锚定图)
    模型: step-image-edit-2 (images.generate)
    画风: 注入 prompt 后缀 (水墨/动漫/写实/赛博)

    │
    ▼
[Step 3] 场景图生成 ───────────────────────────────────────
    输入: 每场景 edit_prompt + 角色参考图 (如有)
    输出: scene_{id}.png
    模型: step-image-edit-2 (images.edit 有角色 / images.generate 无角色)
    画风: 同 Step 2 风格后缀

    │
    ▼
[Step 4] TTS 旁白生成 ─────────────────────────────────────
    输入: 每场景 narration + audio 风格参数
    输出: scene_{id}.mp3
    模型: stepaudio-2.5-tts
    音频风格: voice + instruction (语速/语调/情感)

    │
    ▼
[Step 5] 视频合成 ─────────────────────────────────────────
    输入: scene_*.png + scene_*.mp3
    输出: final.mp4 (ffmpeg concat)
    工具: ffmpeg (每个场景图+音频→segment, 再 concat)
```

Celery 链式执行：
```python
chain(
    split_scenes.s(input_text, style_id),
    generate_refs.s(),
    generate_images.s(),
    generate_audio.s(),
    assemble_video.s()
).apply_async()
```

---

## 六、风格插件系统

### 6.1 目录结构

```
styles/
├── writing/              # 文风插件 (LLM prompt 模板)
│   ├── ancient.yaml      # 古风
│   ├── modern.yaml       # 现代
│   ├── wuxia.yaml        # 武侠
│   ├── xuanhuan.yaml     # 玄幻
│   └── custom_{uid}/     # 用户自定义
├── visual/               # 画风插件 (图像 prompt 后缀)
│   ├── ink_wash.yaml     # 水墨
│   ├── anime.yaml        # 动漫
│   ├── realistic.yaml    # 写实
│   ├── cyberpunk.yaml    # 赛博
│   └── custom_{uid}/
└── audio/                # 音频风格插件 (TTS 参数)
    ├── ancient_male.yaml # 古风男声
    ├── modern_female.yaml# 现代女声
    ├── hot_youth.yaml    # 热血少年
    └── custom_{uid}/
```

### 6.2 插件 YAML 格式

```yaml
# writing/ancient.yaml
name: 古风
description: 古典文学风格，文言与白话交融
system_prompt: |
  你是一位精通古典文学的编剧。请用古风文笔改写以下内容：
  - 用词典雅，适当使用文言句式
  - 保持情节完整，增强意境描写
  - 对话用古典用语，但保持可读性
scene_split_prompt: |
  请将以下古风文段拆分为 N 个场景...
output_format:
  narration_style: "语气沉稳，古韵悠长"
  instruction_default: "语速适中，带有古典韵味"
```

```yaml
# visual/ink_wash.yaml
name: 水墨画风
description: 中国传统水墨画风格
prompt_suffix: "，中国水墨画风格，留白，墨色渲染，宣纸质感"
negative_prompt: "photorealistic, 3D render, modern"
cfg_scale: 1.0
steps: 8
```

```yaml
# audio/ancient_male.yaml
name: 古风男声
description: 沉稳古典男声旁白
voice: cixingnansheng
default_instruction: "语气沉稳，古韵悠长，适合讲古风故事"
speed: 0.9
volume: 1.0
```

### 6.3 插件应用时机

| Pipeline Step | 插件类型 | 作用方式               |
|---------------|---------|----------------------|
| Step 1 拆场景  | writing | 替换 system_prompt    |
| Step 2/3 图像  | visual  | 拼接 prompt_suffix    |
| Step 4 TTS    | audio   | 替换 voice/instruction|

---

## 七、多用户隔离

### 7.1 数据库模型

```python
# User
id, email, password_hash, role(user/admin), created_at

# Project
id, user_id(FK), title, source_text, style_writing,
style_visual, style_audio, status, created_at

# Scene
id, project_id(FK), seq, title, text, shot_type,
narration, edit_prompt, instruction, character

# Asset
id, project_id(FK), scene_id(FK nullable), type(image/audio/video),
file_path, file_size, created_at

# Task
id, project_id(FK), user_id(FK), status(pending/running/
done/failed), step, progress(0-100), error_msg, created_at
```

### 7.2 存储隔离

```
storage/
└── {user_id}/
    └── {project_id}/
        ├── ref_*.png
        ├── scene_*.png
        ├── scene_*.mp3
        ├── scene_data.json
        └── final.mp4
```

### 7.3 并发控制

```python
# Celery worker 配置
CELERY_WORKER_CONCURRENCY = 5      # 常态
CELERY_WORKER_MAX_CONCURRENCY = 20 # 峰值

# 速率限制 (FastAPI middleware)
RATE_LIMIT = "5/s/user"  # API 请求限流

# 队列优先级
CELERY_TASK_ROUTES = {
    'pipeline.split_scenes': {'queue': 'llm'},
    'pipeline.generate_images': {'queue': 'image'},
    'pipeline.generate_audio': {'queue': 'tts'},
    'pipeline.assemble_video': {'queue': 'video'},
}
```

### 7.4 认证

- JWT token (access + refresh)
- bcrypt 密码哈希
- FastAPI Depends 注入当前用户

---

## 八、项目目录结构

```
novel2Animatic/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # 配置 (env)
│   │   ├── database.py          # SQLAlchemy engine
│   │   ├── models/              # ORM 模型
│   │   │   ├── user.py
│   │   │   ├── project.py
│   │   │   ├── scene.py
│   │   │   ├── asset.py
│   │   │   └── task.py
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── routers/             # API 路由
│   │   │   ├── auth.py
│   │   │   ├── projects.py
│   │   │   ├── pipeline.py
│   │   │   └── styles.py
│   │   ├── services/            # 业务逻辑
│   │   │   ├── stepfun_client.py
│   │   │   ├── pipeline.py
│   │   │   ├── style_engine.py
│   │   │   └── storage.py
│   │   ├── tasks/               # Celery 任务
│   │   │   ├── split_scenes.py
│   │   │   ├── generate_images.py
│   │   │   ├── generate_audio.py
│   │   │   └── assemble_video.py
│   │   └── middleware/
│   │       ├── auth.py
│   │       └── rate_limit.py
│   ├── styles/                  # 风格插件
│   │   ├── writing/
│   │   ├── visual/
│   │   └── audio/
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── Login.tsx
│   │   │   ├── Dashboard.tsx
│   │   │   ├── CreateProject.tsx
│   │   │   ├── ProjectDetail.tsx
│   │   │   └── StyleManager.tsx
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── services/            # API 调用
│   │   └── stores/              # 状态管理
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml
├── ARCHITECTURE.md              # 本文件
└── PROTOTYPE_RESULTS.md
```

---

## 九、API 设计

### Auth
```
POST /api/auth/register     注册
POST /api/auth/login        登录 → JWT
POST /api/auth/refresh      刷新 token
```

### Projects
```
GET    /api/projects          列表 (分页)
POST   /api/projects          创建项目 (含 source_text + 风格选择)
GET    /api/projects/{id}     详情 (含场景 + 资产)
DELETE /api/projects/{id}     删除
```

### Pipeline
```
POST   /api/projects/{id}/run       启动 pipeline
GET    /api/projects/{id}/progress  SSE 进度推送
POST   /api/projects/{id}/cancel    取消
```

### Styles
```
GET    /api/styles?type=writing|visual|audio    列表
GET    /api/styles/{id}                         详情
POST   /api/styles                              创建自定义
PUT    /api/styles/{id}                         更新
DELETE /api/styles/{id}                         删除
```

### Assets
```
GET    /api/projects/{id}/assets/{scene_id}/{type}  下载资产
```

---

## 十、MVP 分阶段计划

### Phase 1 — 核心 Pipeline（最小可用）
- [x] StepFun API 客户端封装
- [ ] FastAPI 后端骨架 + JWT 认证
- [ ] PostgreSQL 模型 (User, Project, Scene, Asset)
- [ ] Celery 五步 pipeline (拆场景→参考图→场景图→TTS→视频)
- [ ] React 前端: 登录 + 创建项目 + 查看结果
- [ ] Docker Compose 一键启动

### Phase 2 — 风格插件
- [ ] 插件 YAML 加载引擎
- [ ] 内置文风: 古风/现代/武侠/玄幻
- [ ] 内置画风: 水墨/动漫/写实/赛博
- [ ] 内置音频风格: 古风男声/现代女声/热血少年
- [ ] 前端风格选择器
- [ ] 用户自定义插件上传

### Phase 3 — 生产化
- [ ] MinIO 对象存储
- [ ] 并发控制 (rate limit + queue priority)
- [ ] SSE 实时进度推送
- [ ] 错误恢复 + 重试
- [ ] 管理后台 (用户管理 + 任务监控)

---

## 十一、依赖清单

### 后端
```
fastapi>=0.110
uvicorn[standard]
sqlalchemy[asyncio]>=2.0
asyncpg
alembic
celery[redis]
redis
openai>=1.0          # StepFun 兼容 OpenAI SDK
pydantic>=2.0
python-jose[cryptography]
passlib[bcrypt]
python-multipart
minio
httpx
```

### 前端
```
react>=18
vite
antd
axios
react-router-dom
zustand
```

### 基础设施
```
PostgreSQL 16
Redis 7
MinIO (latest)
ffmpeg
Docker + Docker Compose
```

---

## 十二、成本估算 (per 短篇, 14 场景)

| 环节     | 模型                  | 单价              | 成本    |
|----------|----------------------|-------------------|---------|
| LLM 拆场景 | step-3.7-flash      | ~0.01 元/次       | ~0.01 元 |
| 图像生成  | step-image-edit-2    | 0.02 元/张 ×16    | ~0.32 元 |
| TTS      | stepaudio-2.5-tts    | 5.8 元/万字符 ×500 | ~0.29 元 |
| **合计**  |                      |                   | **~0.62 元** |
