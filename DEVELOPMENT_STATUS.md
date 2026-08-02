# 开发状态

- 当前分支：`master`
- 当前提交：`cacfd04 feat: complete phase one video pipeline`
- 当前阶段：阶段 2（工程基础与任务模型）进行中。

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

阶段 2 已新增配置读取、Mock Provider 接口、StorageService、SQLAlchemy 2、Alembic 初始迁移、任务/事件持久化、状态转换、trace ID、JSON 日志、SSE 事件回放、取消请求与保留期清理服务。真实 ASR/Planner、复杂时间轴、其他动画模板、用户系统和云端部署仍未实现。

## 已知问题

- 当前渲染在上传 HTTP 请求中同步执行，长视频会长期占用请求。
- 因同步渲染，取消请求仅会在工作流边界生效；SSE 目前回放持久化事件而非实时进度流。
- `npm audit` 此前报告 Remotion 依赖树存在审计问题；未执行自动升级以避免未经评审的依赖变更。
