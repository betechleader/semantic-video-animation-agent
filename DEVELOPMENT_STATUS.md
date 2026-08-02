# 开发状态

- 当前分支：`master`
- 当前提交：`8f248dd feat: add mock audio transcription workflow`
- 当前阶段：阶段 3（faster-whisper 本地 ASR）已完成；下一阶段为阶段 4（字幕系统）。

## 已完成功能

阶段一最小纵向链路已完成并经端到端测试验证：

- MP4 上传、大小/扩展名/视频流校验与 ffprobe 元数据读取。
- 固定中文 Mock ASR、严格 Pydantic `AnimationPlan`、Mock Planner。
- Remotion `KeywordPop`（text、color、position、start_ms、end_ms）。
- Remotion 渲染透明 ProRes 覆盖层，并通过 FFmpeg 合成为 `result.mp4`。
- SQLite 任务记录、任务查询、结果下载与同源上传页面。

## 基线验证（2026-08-02）

- 项目 Conda Python：`Python 3.12.13`。
- Python 测试：`10 passed`，包含实际 Remotion 渲染、FFmpeg 合成、ffprobe 验证和结果下载的端到端测试。
- Remotion 构建：`npm.cmd run build` 通过。普通受限沙箱无法重建已有 `animation-renderer/build`，经仅限该项目构建命令的提升权限验证通过。
- 裸 `python` 和 PowerShell 的裸 `npm` 在此 Windows 环境不可用；仓库约定的 `.conda\\python.exe` 和 `npm.cmd` 可用。

## 进行中与未开始

阶段 2 已新增配置读取、Mock Provider 接口、StorageService、SQLAlchemy 2、Alembic 初始迁移、任务/事件持久化、状态转换、trace ID、JSON 日志、后台工作器、实时 SSE、Windows 进程树取消和保留期清理服务。真实 ASR/Planner、复杂时间轴、其他动画模板、用户系统和云端部署仍未实现。

阶段 3 已新增 FFmpeg 16 kHz 单声道 WAV 提取、Mock ASR Provider、`FasterWhisperProvider`（CPU int8、本地模型与逐词时间戳转换）、转录保存和完成后转录编辑 API。`faster-whisper 1.1.1` 与默认 small 模型已安装在项目 D 盘；默认仍为 Mock 模式。真实本地验证已成功完成：一段 94 秒中文视频产生 27 个片段和 283 个逐词时间戳；时间戳在毫秒取整后会保留至少 1 ms 的有效区间。

## 已知问题

- 后台线程适合单机 MVP，但进程重启后不会自动恢复正在运行的任务。
- SSE 提供任务阶段事件，不提供 Remotion/FFmpeg 的逐帧百分比。
- 直连 PyPI 与 Hugging Face 下载均出现超时；已通过清华 PyPI 镜像安装依赖，并使用普通 Hugging Face 下载路径将模型保存到 D 盘。真实中文样本已验证流程可用，但尚未覆盖不同说话人、口音和音质条件下的识别质量。
- `npm audit` 此前报告 Remotion 依赖树存在审计问题；未执行自动升级以避免未经评审的依赖变更。
