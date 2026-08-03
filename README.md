# Chinese Talking-head Semantic Video Animation

This local Windows pipeline accepts an MP4, extracts speech, produces a time-grounded animation plan, renders a transparent Remotion overlay, burns ASS subtitles, and composites a downloadable MP4 with FFmpeg.

## Start

```powershell
D:\Projects\semantic-video-animation-agent\.conda\python.exe -m pip install -r requirements.txt
D:\Projects\semantic-video-animation-agent\.conda\python.exe -m alembic upgrade head
cd animation-renderer
npm.cmd install
cd ..
D:\Projects\semantic-video-animation-agent\.conda\python.exe -m uvicorn backend.app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000), upload an MP4 (up to 100 MB), and wait for processing to finish.

## Verification

```powershell
D:\Projects\semantic-video-animation-agent\.conda\python.exe -m pytest -vv
cd animation-renderer
npm.cmd run build
```

## Providers

`ASR_PROVIDER=mock` and `PLANNER_PROVIDER=mock` are the defaults, so the full local workflow is available without a model service. `ASR_PROVIDER=faster_whisper` uses a local CPU int8 model and word timestamps. Pair it with `PLANNER_PROVIDER=rule_based` for an offline planner that highlights text from real transcript segments at their real timestamps. `PLANNER_PROVIDER=local_llm` uses a local, OpenAI Chat Completions-compatible server for richer semantic selection; its base URL must resolve to a loopback host (`127.0.0.1`, `localhost`, or `::1`).

## Semantic planning safety rules

The Mock and local LLM planners use the same transcript-aware validation after planning. Every animation must fit completely inside one transcript word or segment, last 300–5000 ms, and use a unique ID. Plans may start at most two animations in any rolling 10-second window, and animation time ranges cannot overlap. Semantic segments must fit inside one transcript segment. Invalid plans fail before Remotion or FFmpeg rendering begins.

## Animation templates and API

`keyword_pop_v1` highlights a keyword; `quote_card_v1` shows an emphasized card; and `media_visual_v1` displays a topic visual during its transcript-grounded interval. The shared `AnimationOverlay` composition renders all validated animations on the timeline.

- `POST /api/videos` uploads an `.mp4` and returns `202 Accepted` plus a task ID.
- `GET /api/videos/{task_id}` returns metadata, transcript, plan, and status.
- `GET /api/videos/{task_id}/download` downloads `result.mp4` after completion.
- `GET /api/videos/{task_id}/events` streams task-state events with SSE.
- `POST /api/videos/{task_id}/cancel` requests cancellation.
- `PUT /api/videos/{task_id}/transcript` edits the transcript after processing completes.
- `POST /api/videos/{task_id}/review` accepts a completed task's `{transcript, plan}`, validates the plan against that transcript, saves both, and creates an updated result video.

After a task completes, the browser shows the generated video preview together with editable transcript and plan JSON. Saving those review edits starts a new render and the preview reloads when it completes. SSE clients may pass `after_event_id` to `/api/videos/{task_id}/events` to receive only newer task events.

Runtime data is under `storage/{task_id}/`, including `source.mp4`, `audio.wav`, `animation.mov`, `subtitles.ass`, and `result.mp4`. SQLite task records are stored in `storage/tasks.sqlite3`.

## Copyright-safe media visuals

The pipeline never downloads or automatically uses web images. When the semantic planner finds a book/topic mention (such as `《心理学与生活》`), it produces a generic, original task-local SVG book illustration instead of a recognisable cover. The visual is anchored to the matching real transcript interval and follows the same density and conflict rules as other animations. Each admitted asset is recorded in both the saved plan and `storage/{task_id}/media_assets.json` with its source URI, author/provider, licence, allowed transformations, acquisition time, relative local path, and SHA-256 checksum. See [MEDIA_ASSET_POLICY.md](MEDIA_ASSET_POLICY.md) for the acceptance policy and requirements for any future external source.

## Output quality and safe areas

Before rendering, keyword text is checked against an 8 percent horizontal safe margin and templates scale typography to the target video width. After each render, the pipeline uses `ffprobe` to check dimensions, duration, frame rate, frame count, and expected audio, then uses `ffmpeg` to decode every required stream. Successful tasks also contain `quality.json` with the measured output values.
