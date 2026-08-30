# 帧语工坊：本地 AI 视频语义动画平台

一个面向中文口播视频的本地 AI 创作工具。上传 MP4 后，系统可以完成语音识别、文本纠错、语义规划、动态字幕与知识动画渲染，最终输出完整视频。

项目优先在本地处理视频和音频，适合用于学习、原型验证和本地内容创作。

## 核心功能

- 上传中文口播 MP4 视频
- 使用 FFmpeg 提取音频
- 使用 faster-whisper 进行本地语音识别
- 根据上下文纠正常见中文识别错误
- 根据字幕内容生成语义动画计划
- 自动生成动态字幕、关键词强调、知识卡片和信息图
- 使用 Remotion 渲染动画
- 使用 FFmpeg 合成并检查最终视频
- 支持素材检索、替换、关闭和重新渲染
- 支持标准工作流和 Agent 工作流
- 支持任务暂停、审批、恢复、取消和结果下载
- 提供中英文网页界面

## 处理流程

```text
上传 MP4
   ↓
视频检测与音频提取
   ↓
中文语音识别
   ↓
识别文本纠错
   ↓
语义动画规划
   ↓
计划校验与人工审批
   ↓
Remotion 动画渲染
   ↓
FFmpeg 视频合成与质量检查
   ↓
输出完整视频
```

## 技术栈

- 后端：FastAPI、Pydantic、SQLAlchemy、Alembic
- 前端：HTML、CSS、JavaScript
- 动画渲染：React、TypeScript、Remotion
- 视频处理：FFmpeg、ffprobe
- 语音识别：faster-whisper
- 数据存储：SQLite、本地文件系统
- 测试：pytest
- 可选语义规划：规则引擎、本地 LLM、DeepSeek

## 项目结构

```text
backend/app/          FastAPI 后端与视频处理服务
frontend/             浏览器网页界面
animation-renderer/   React/Remotion 动画模板
config/               中文识别纠错配置
assets/               本地知识素材
tests/                自动化测试
storage/              本地运行数据，不上传 GitHub
```

## 快速启动（Windows）

### 1. 安装运行环境

请先安装：

- Python 3.12
- Node.js 和 npm
- FFmpeg，并确保 `ffmpeg`、`ffprobe` 可以在命令行运行
- Git

### 2. 下载项目

```powershell
git clone https://github.com/betechleader/semantic-video-animation-agent.git
cd semantic-video-animation-agent
```

### 3. 创建 Python 环境

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 4. 安装动画渲染依赖

```powershell
cd animation-renderer
npm.cmd install
cd ..
```

### 5. 初始化数据库

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

### 6. 启动服务

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

浏览器打开：

http://127.0.0.1:8000

前端页面由 FastAPI 同时提供，不需要单独启动前端服务。

## 快速验证

第一次运行建议在上传页面选择 **Mock** 处理模式。

Mock 模式不需要 API Key，也不需要下载语音识别模型，适合快速检查：

- 视频上传
- 任务状态更新
- 字幕与语义计划生成
- Remotion 动画渲染
- FFmpeg 视频合成
- 结果预览与下载

真实语音识别模式使用本地 faster-whisper 模型。模型文件体积较大，因此不会上传到 GitHub，需要使用者自行准备。

## 工作流模式

### 标准模式

按照固定流程完成语音识别、语义规划、渲染和结果输出，适合稳定处理。

### Agent 模式

提供更完整的任务执行与校验流程，包括：

- 结构化语义计划
- 计划规则验证与有限次数修复
- 人工审批、编辑和拒绝
- 中断任务恢复
- 隐私安全的执行记录
- 防止重复审批触发多次渲染

## 本地知识库（P6）

P6 提供一个与视频任务目录分离、但仍位于项目 `storage/knowledge/` 内的受控知识库。它目前不接入 AnimationPlan 或 Agent planning；带引用的 RAG 规划属于后续 P7。

- 支持导入 UTF-8 编码的 `.txt`、`.md`、`.json`，单文件默认上限 5 MB。
- 文档和分块使用内容哈希生成稳定 ID；重复内容不会重复入库，索引版本变化时会原位重建分块。
- `keyword` 使用中文字符/双字词友好的 BM25，`vector` 使用本地向量余弦相似度，`hybrid` 合并两路分数并去重，可选词法重排。
- 默认 `local_hash` 向量后端完全离线、无需模型。可选 `bge_m3` 使用固定版本的 `sentence-transformers`，但只从本地缓存或本地路径加载，并强制 `local_files_only=True`、`trust_remote_code=False`；运行和测试都不会自动下载模型。
- 当前使用现有 SQLite 保存元数据、分块和向量。对于项目内小型知识库，这比增加常驻 Qdrant 服务更轻量且易恢复；如果语料规模显著增长，可以在保持 Provider 接口不变的前提下替换向量存储。

CLI 示例：

```powershell
.\.conda\python.exe -m alembic upgrade head
.\.conda\python.exe -m backend.app.knowledge_cli import assets\my-notes.md --metadata '{"topic":"demo"}'
.\.conda\python.exe -m backend.app.knowledge_cli list
.\.conda\python.exe -m backend.app.knowledge_cli search "需要检索的问题" --method hybrid --rerank
.\.conda\python.exe -m backend.app.knowledge_cli delete doc_0123456789abcdef01234567
```

API：

- `POST /api/knowledge/documents`：multipart 上传 `file`，可选 `metadata_json`。
- `GET /api/knowledge/documents`：列出来源、摘要、分块数、索引版本和 embedding 标识。
- `POST /api/knowledge/search`：提交 `query`、`keyword|vector|hybrid`、`limit` 和 `rerank`。
- `DELETE /api/knowledge/documents/{document_id}`：只删除知识库根目录内的指定文档及其分块。

若要启用预先放入本地缓存的 BGE-M3：

```powershell
$env:KNOWLEDGE_EMBEDDING_PROVIDER = 'bge_m3'
$env:KNOWLEDGE_EMBEDDING_MODEL = 'BAAI/bge-m3'
$env:KNOWLEDGE_EMBEDDING_LOCAL_FILES_ONLY = 'true'
```

## 带引用的 Agent 语义规划（P7）

P7 只把本地知识库接入 `agent` 工作流；`standard` 仍沿用原来的稳定规划与渲染链路，不要求知识库存在。

- planning 节点通过强类型 `retrieve_evidence` 工具对纠错后的转写分段执行有界混合检索，并把证据传给规则、本地 LLM 或 DeepSeek Planner。
- 需要事实支持的知识视觉会保存 `evidence_ids`、`confidence` 和 `selection_reason`，计划顶层保存来源、摘录、内容哈希和索引版本。没有支持证据时，事实视觉会降级为转写强调或明确的抽象视觉包装。
- validation、人工审批、正式 render 和审核重渲染都会重新解析当前知识索引。证据被删除、替换、改写，或计划摘录与当前 chunk 不一致时，旧计划会被判定为失效，不能继续渲染。
- `GET /api/videos/{task_id}/evidence` 返回审核用的来源、摘录、引用动画和 `valid|missing|stale` 状态；现有 Agent 审批区和完成页“知识证据”标签会展示这些真实数据。
- Agent Trace 记录查询哈希、查询长度、召回数量和采用的 evidence ID，不记录查询正文、转写正文、证据正文、绝对路径或内部思维链。
- 如果选择远程 DeepSeek Planner，纠错转写、导演指令、修复违规项以及检索到的证据摘录会发送到固定官方端点；本地 Mock、规则 Planner 和本地 LLM 不改变其既有网络边界。

离线评测新增 `evidence_retrieval_hit_rate` 和 `citation_correctness_rate`，使用自造知识片段与内存 Fake 检索，不读取用户 `storage` 内容，也不访问网络。

## 本地 MCP 工具服务（P9）

P9 使用官方 MCP Python SDK `2.1.1` 提供本地 `stdio` 服务，不增加 HTTP 监听端口，也不改变普通网页和 FastAPI API。启动命令：

```powershell
.\.conda\python.exe -m backend.app.mcp_server
```

MCP 工具包括 `create_video`、`get_video_status`、`get_agent_trace`、`search_asset`、`get_pending_approval`、`approve_plan`、`replace_asset`、`rerender_video` 和 `download_result`。资源模板包括任务状态、脱敏 Agent Trace 和完成视频：

- `video://tasks/{task_id}`
- `video://tasks/{task_id}/trace`
- `video://tasks/{task_id}/result`

工具参数和返回值由 Pydantic 生成明确 JSON Schema。只读查询与有副作用的创建、审批、素材搜索缓存、替换和重渲染在 MCP 注解中分开标记；注解只是客户端提示，真正的权限边界仍由服务端任务状态、原子审批更新、规划/证据/安全区校验和任务内素材清单保证。

`create_video` 只接受有大小上限的 base64 MP4，不接受客户端文件路径。`replace_asset` 只接受当前任务候选清单中的 `candidate_id`，不接受任意 URL。下载工具只返回 MCP 资源 URI，结果资源返回 `video/mp4` 字节，不公开 `storage` 绝对路径。所有写操作继续写入现有任务事件审计。本阶段没有增加 HTTP transport；如果后续增加，必须先加入认证并限制绑定地址。

SDK 版本选择依据：[MCP Python SDK 2.1.1](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.1.1) 和 [官方工具/Schema 文档](https://py.sdk.modelcontextprotocol.io/servers/tools/)。

## 持久 Worker 与部署（P10）

默认 `EXECUTION_MODE=local` 完整保留原来的单进程轻量运行方式。需要进程崩溃恢复时，可设置 `EXECUTION_MODE=worker`，分别启动 API 与本地持久 Worker：

```powershell
$env:EXECUTION_MODE = 'worker'
.\.conda\python.exe -m uvicorn backend.app.main:app --reload
# 另一个终端
$env:EXECUTION_MODE = 'worker'
.\.conda\python.exe -m backend.app.worker
```

Worker 使用现有 `storage/tasks.sqlite3` 保存执行任务、幂等键、有限尝试次数、租约和心跳。Worker 崩溃后，另一 Worker 会在租约过期后接管；Agent 继续使用节点 Checkpoint，standard/review 使用固定任务产物路径安全重试。当前项目是单机本地工具，因此没有把 Redis 设为默认依赖；如果未来扩展为多主机高并发，可在保持执行接口不变的前提下替换队列存储。

健康与本地指标端点：

- `GET /health/live`：进程存活。
- `GET /health/ready`：数据库可用；worker 模式还要求存在新鲜 Worker 心跳。
- `GET /metrics`：Prometheus 文本格式的任务/执行状态聚合，不包含任务 ID、转录、路径或用户内容。

Docker 开发/演示环境默认使用完全离线的 Mock Provider：

```powershell
docker compose up --build
```

Compose 只把 API 暴露到 `127.0.0.1:8000`，API 与 Worker 共享命名存储卷。CI 会运行 Python 测试、语法/格式/类型检查、数据库迁移、离线 Eval、Renderer build 和 Compose 配置校验。

## 测试

运行 Python 测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -vv
```

验证 Remotion 构建：

```powershell
cd animation-renderer
npm.cmd run build
```

当前项目测试基线为 167 项测试通过。

## 隐私与本地数据

以下运行数据保存在本地 `storage/` 目录，不会提交到 GitHub：

- 用户上传的视频
- 提取的音频
- 语音识别文本
- SQLite 数据库
- 动画中间文件
- 最终生成的视频
- 任务日志与本地模型

仓库不包含演示者的真实视频、私人邮箱、API Key 或历史任务数据。

## 外部素材说明

外部图片和视频素材仅用于原型验证。系统会记录素材来源、查询关键词和使用区间，但使用者仍需自行检查版权、人物肖像、商标和发布平台规则。

仓库中的书籍封面参考素材不代表已经取得商业使用授权，不建议直接用于商业发布。

## 当前状态

当前版本已经完成本地语义视频动画的基础工作流、Agent 审批流程、任务恢复、素材审核和中英文网页界面。

这是一个本地工程原型，不提供云端账户、在线同步、订阅或托管服务。
