# PRD: novel2Animatic × InkOS 设计借鉴优化

## Problem Statement

novel2Animatic 当前是一个「输入文本→输出视频」的单向 pipeline 工具。用户只能粘贴一段文本，系统自动拆分场景、生成图片和音频、拼接视频。存在以下痛点：

1. **场景来源单一**：只能从用户手动输入的文本拆分，无法利用 AI 创作能力生成高质量场景
2. **UI 体验粗糙**：ProjectDetail 单页 609 行，大量 !important CSS 覆盖 Ant Design，无主题切换
3. **模型配置不灵活**：StepFun API 硬编码，无法切换其他模型服务商
4. **无实时反馈**：靠 2s 轮询进度，无流式输出或 SSE
5. **场景质量不可控**：单次 LLM 调用生成场景，无审查-修订流程
6. **无场景编辑能力**：只能整体重跑 pipeline，无法编辑单个场景

## Solution

参考 InkOS 的短篇小说生成、开放世界 Play、Studio Chat 交互和模型配置设计，分三个大方向优化 novel2Animatic：

1. **AI 场景生成器**：集成 InkOS Short 的「写-审-改」三明治模式作为新的场景来源，同时支持 InkOS Play 的开放世界模式生成互动场景
2. **Chat-centric 工作台**：参考 InkOS Studio 的 UI 设计，将 Dashboard/ProjectDetail 重构为 Chat-centric 工作台
3. **可配置模型系统**：参考 InkOS 的服务预设+自定义端点架构，支持多服务商模型路由

## User Stories

### 场景来源扩展

1. As a 创作者, I want to 粘贴文本自动拆分场景（现有功能）, so that 快速从已有小说生成动画
2. As a 创作者, I want to 通过 AI 短篇小说生成器创建场景, so that 不需要自己写文本也能生成动画
3. As a 创作者, I want to 为短篇生成器指定创作方向（题材/风格/主题）, so that 生成内容符合我的需求
4. As a 创作者, I want to AI 自动审查并修订生成的场景描述, so that 场景质量有保障
5. As a 创作者, I want to 查看和编辑每个生成阶段的中间结果, so that 可以在不满意时调整方向
6. As a 创作者, I want to 通过开放世界互动模式创建场景, so that 可以用自然语言构建一个有角色、物品、关系的虚拟世界
7. As a 创作者, I want to 在开放世界中自由行动（look/say/move/do/wait）, so that 世界随互动推进并自动生成分镜场景
8. As a 创作者, I want to 查看世界状态面板（角色/关系/物品/证据）, so that 理解当前世界状态
9. As a 创作者, I want to 选择系统建议的动作或自由输入, so that 在引导和自由间平衡
10. As a 创作者, I want to AI 生成的场景自动进入 pipeline 生成动画, so that 从创作到动画无缝衔接
11. As a 创作者, I want to 将 InkOS 已有的短篇小说直接导入为场景, so that 复用已有创作内容
12. As a 创作者, I want to 将 InkOS Play 的开放世界回合结果导入为场景, so that 互动内容变成动画

### UI/UX 优化

13. As a 用户, I want to Chat-centric 的工作台界面, so that 通过自然语言控制所有操作
14. As a 用户, I want to 左侧导航栏展示项目列表和快捷操作, so that 快速切换项目
15. As a 用户, I want to 聊天消息区分 thinking/text/tool 三种类型, so that 清晰看到 AI 的推理过程
16. As a 用户, I want to 工具执行结果内联显示在聊天流中, so that 看到 pipeline 每步的进度和产出
17. As a 用户, I want to 暗色/亮色主题切换, so that 适应不同环境
18. As a 用户, I want to 右侧上下文面板显示场景列表和媒体预览, so that 快速浏览和切换场景
19. As a 用户, I want to 场景可单独编辑和重新生成, so that 不需要重跑整个 pipeline
20. As a 用户, I want to 确认卡片控制重操作（如重新生成/删除）, so that 避免误操作
21. As a 用户, I want to 快捷操作按钮（重跑/导出/分享）, so that 常用操作一键完成

### 模型配置

22. As a 管理员, I want to 配置多个模型服务商（StepFun/OpenAI/自定义）, so that 不同任务使用不同模型
23. As a 管理员, I want to 为不同 pipeline 步骤指定不同模型, so that 场景拆分用便宜模型，图片生成用高质量模型
24. As a 管理员, I want to 服务连接自动探测（API格式/流式/基础URL）, so that 减少手动配置
25. As a 管理员, I want to 测试服务连接并查看可用模型列表, so that 确认配置正确
26. As a 管理员, I want to 模型选择器集成在聊天输入区, so that 随时切换当前使用的模型

## Implementation Decisions

### 模块 1：AI 场景生成器

**新增后端模块：**
- `backend/app/services/scene_generator.py` — 场景生成器核心（三明治模式）
- `backend/app/services/world_engine.py` — 开放世界引擎（图数据库+Reducer）
- `backend/app/models/world.py` — 世界实体/边/状态槽/事件数据模型
- `backend/app/routers/generator.py` — 场景生成 API 路由
- `backend/app/services/text_parser.py` — === TAG === 格式解析器

**设计决策：**
1. **场景生成 pipeline 采用 InkOS Short 的 6 阶段模式**：方向→大纲→审纲→改纲→正文→审稿→改稿→包装。每阶段用 StepFun step-3.7-flash，温度参数参照 InkOS 设计。
2. **输出格式采用 === TAG === 而非 JSON**：对 LLM 输出更宽容，支持 fallback 到 Markdown 标题。
3. **开放世界采用 SQLite 本地存储**：entities/edges/state_slots/events 表，参考 InkOS 的 play-db 设计。
4. **4 步回合 pipeline**：Action Interpreter → World Mutator → Scene Renderer → Scene Reconciler，职责单一。
5. **Fail-open 容错**：每一层都有 fallback，畸形数据跳过不崩溃。
6. **世界契约/视觉契约**：用户可定义世界规则和视觉风格，优先级高于默认设定。
7. **先渲染后提交**：场景渲染完成前不更新世界状态，保证 all-or-nothing 语义。
8. **短篇小说和 Play 的场景可直接进入已有的 animatic pipeline**：场景结构 (title, text, shot_type, narration, edit_prompt, instruction, character) 与现有 Scene 模型兼容。

**数据模型变更：**
- Scene 新增 `source_type` 字段：`text_split` / `short_fiction` / `play_world`
- 新增 World 模型：id, title, premise, world_contract, visual_contract, mode, language
- 新增 WorldRun 模型：world_id, turn, status, state_snapshot

### 模块 2：Chat-centric 工作台

**重构前端模块：**
- `frontend/src/pages/ChatPage.jsx` — 新 Chat 页面（取代 Dashboard + ProjectDetail）
- `frontend/src/components/ChatSidebar.jsx` — 左侧项目/会话导航
- `frontend/src/components/ContextPanel.jsx` — 右侧上下文面板（场景/媒体预览）
- `frontend/src/components/ChatMessage.jsx` — 消息组件（支持 thinking/text/tool parts）
- `frontend/src/components/ToolExecutionCard.jsx` — 工具执行卡片
- `frontend/src/components/ConfirmDialog.jsx` — 确认卡片
- `frontend/src/components/QuickActions.jsx` — 快捷操作栏
- `frontend/src/hooks/useSSE.js` — SSE 钩子（替代轮询）
- `frontend/src/hooks/useTheme.js` — 主题钩子
- `frontend/src/store/chat.js` — Zustand 聊天状态管理

**设计决策：**
1. **三栏布局**：左侧 Sidebar (260px) + 中间聊天区 + 右侧 Context Panel（可折叠）
2. **Hash 路由**：沿用 React Router，但增加 chat/project/:id 路由
3. **消息 parts 模型**：Assistant 消息包含 thinking/text/tool 三种 parts
4. **SSE 实时推送**：后端新增 `/api/projects/{id}/events` SSE 端点，替代 2s 轮询
5. **CSS 变量主题**：替换 !important 覆盖，使用 CSS 变量 + Ant Design ConfigProvider
6. **场景可单独编辑**：Context Panel 支持场景编辑和单场景重新生成
7. **快捷操作**：写入聊天区的输入框上方，如 [重新生成场景] [导出视频] [查看世界]
8. **模型选择器**：集成在聊天输入框旁

### 模块 3：可配置模型系统

**新增后端模块：**
- `backend/app/services/model_registry.py` — 模型服务注册中心
- `backend/app/services/model_resolver.py` — 模型路由解析器
- `backend/app/models/service.py` — 服务配置数据模型
- `backend/app/routers/services.py` — 服务管理 API
- `backend/app/services/probe.py` — 服务连接探测

**设计决策：**
1. **服务预设 + 自定义端点双轨制**：预设覆盖 StepFun/OpenAI/Anthropic 等主流服务，同时支持自定义 OpenAI-compatible 端点
2. **分组管理**：海外/国产/聚合/自定义四组
3. **自动探测**：输入 API Key 后自动探测 API 格式、流式支持、可用模型列表
4. **Pipeline 步骤路由**：scene_split / image_gen / tts 分别配置不同模型
5. **服务配置存储在数据库**：新增 services 表，存储 name/group/base_url/api_key(加密)/model_id/config

## Testing Decisions

### 测试原则
- 只测试外部可观察行为，不测实现细节
- 后端通过 pytest + httpx.AsyncClient 测试 API 端点
- 前端通过 Vitest + React Testing Library 测试组件交互
- E2E 通过浏览器测试完整流程

### 测试模块
- **场景生成器测试**：test_scene_generator.py — 测试三明治 pipeline 的输入输出
- **世界引擎测试**：test_world_engine.py — 测试 Reducer、实体 CRUD、状态变更
- **TAG 解析器测试**：test_tag_parser.py — 测试 === TAG === 解析和 fallback
- **SSE 测试**：test_sse.py — 测试实时事件推送
- **模型配置测试**：test_model_config.py — 测试服务注册、路由、探测
- **前端组件测试**：ChatMessage.test.jsx, ToolExecutionCard.test.jsx 等

### 测试优先级
1. TAG 解析器（基础能力，最先测试）
2. 场景生成 pipeline（核心功能）
3. 世界引擎 Reducer（核心功能）
4. 模型路由解析（配置能力）
5. SSE 推送（实时性）
6. UI 组件（体验优化）

## Out of Scope

- 多用户协作/项目分享
- 对象存储（S3/OSS）迁移
- Docker Compose 部署配置
- 国际化 (i18n)
- 移动端适配
- InkOS TUI/CLI 集成
- InkOS 长篇连载功能
- Celery/ARQ 任务队列（保持 asyncio.create_task）
- Rate limiting

## Further Notes

### 实施顺序建议
1. Phase 1: 基础设施（TAG 解析器 + 模型配置系统 + SSE 推送）
2. Phase 2: AI 场景生成器（短篇小说三明治模式）
3. Phase 3: 开放世界引擎（Play 的图数据库+Reducer）
4. Phase 4: Chat-centric UI 工作台
5. Phase 5: 场景可编辑 + 单场景重新生成

### 风险点
- StepFun API 对长文本多轮对话的稳定性（InkOS 也遇到了弱模型格式不稳的问题）
- 开放世界引擎的 SQLite 并发写入（asyncio 环境下需要 careful）
- Chat-centric UI 重构范围大，需要保持向后兼容

### InkOS 分析报告
- 短篇小说 + 开放世界分析：/private/tmp/inkos-analysis-report.md
- Studio UI/UX 分析：已记录在子任务摘要中
- novel2Animatic 现状分析：已记录在子任务摘要中
