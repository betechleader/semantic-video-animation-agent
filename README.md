# 中文口播视频语义动画（阶段一）

上传 MP4 后，服务会读取元数据并立即创建后台任务；该任务生成固定中文 Mock 转录与 `KeywordPop` 动画计划，使用 Remotion 渲染关键词动画，再通过 FFmpeg 合成为可下载的 MP4。

## Windows 启动

在仓库根目录执行：

```powershell
D:\Projects\semantic-video-animation-agent\.conda\python.exe -m pip install -r requirements.txt
D:\Projects\semantic-video-animation-agent\.conda\python.exe -m alembic upgrade head
cd animation-renderer
npm.cmd install
cd ..
D:\Projects\semantic-video-animation-agent\.conda\python.exe -m uvicorn backend.app.main:app --reload
```

打开 http://127.0.0.1:8000 ，选择 MP4 并等待处理完成。上传上限为 100 MB。

## 验证

```powershell
D:\Projects\semantic-video-animation-agent\.conda\python.exe -m pytest -vv
cd animation-renderer
npm.cmd run build
```

端到端测试会使用 FFmpeg 临时生成一个两秒视频，并实际执行 Remotion 渲染与 FFmpeg 合成，通常需要约一分钟。

## API

- `POST /api/videos`：上传 `.mp4`，返回 `202 Accepted` 和 `task_id`。
- `GET /api/videos/{task_id}`：读取元数据、Mock 转录、动画计划和状态。
- `GET /api/videos/{task_id}/download`：下载 `result.mp4`。
- `GET /api/videos/{task_id}/events`：以 SSE 格式持续推送任务状态事件，任务结束后关闭连接。
- `POST /api/videos/{task_id}/cancel`：请求取消任务，并终止正在运行的 FFmpeg/Remotion Windows 进程树。

运行数据保存在 `storage/{task_id}/`，其中包含 `source.mp4`、`animation.mov` 和 `result.mp4`。SQLite 任务记录位于 `storage/tasks.sqlite3`。

阶段二基础设施使用 SQLAlchemy 2 和 Alembic 管理 `video_tasks` 与 `task_events`；每个请求都会返回 `X-Trace-ID`。视频渲染由后台线程执行，SSE 提供任务级实时状态事件；它不是帧级渲染百分比。

## ASR 模式

默认 `ASR_PROVIDER=mock`，因此不需要模型也能运行完整视频链路。任务会通过 FFmpeg 提取 16 kHz 单声道 WAV，并保存转录；完成后的转录可通过 `PUT /api/videos/{task_id}/transcript` 编辑。

本地 ASR 使用 `ASR_PROVIDER=faster_whisper` 与 `ASR_MODEL=small`。默认 `ASR_LOCAL_FILES_ONLY=true`，只使用 `storage/models` 的本地模型，不会在处理视频时联网下载。若模型不存在，Provider 会返回明确错误；模型下载前应先确认本地磁盘空间。
