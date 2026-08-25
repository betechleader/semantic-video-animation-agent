# 项目规格

本项目是本地运行的中文口播视频语义动画 Agent：上传视频后，确定性程序负责视频/音频处理、时间戳、路径、安全校验、渲染和质量检查；模型只负责转录、语义理解和结构化 `AnimationPlan`。

## 当前基线：阶段一

已实现本地 MP4 上传、ffprobe 元数据读取、固定中文 Mock ASR、严格的 KeywordPop 动画计划、Remotion 渲染、FFmpeg 合成、结果查询下载和简单网页。阶段二已提供后台任务、SQLite/SQLAlchemy 持久化、Alembic、SSE、取消和清理基础。它不包含真实 ASR/LLM、其他动画模板、认证、分布式队列或云端部署。

阶段三已完成：除 Mock 模式外，项目已用本地 CPU int8 `small` faster-whisper 模型成功转录一段 94 秒中文视频，并生成经 Pydantic 校验的逐词时间戳。真实 Provider 仍可选，默认保持 Mock 模式。

## 后续范围

后续按 `PLANS.md` 依次实施工程任务模型、faster-whisper、字幕系统、本地 LLM 语义分析、完整模板库、规则校验、审核 UI、质量检查、评测与可观测性。RAG、MCP 和 LangGraph 为后期可选项，不能阻塞核心链路。
