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

当前项目测试基线为 125 项测试通过。

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
