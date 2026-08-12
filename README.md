# Local AI Video & Content Creation Studio

面向本地 Windows 的 AI 视频与内容创作平台。当前正式模块是“语义视频动画”：上传 MP4、抽取语音、生成时间对齐语义计划、渲染动态字幕与知识口播包装，再用 FFmpeg 输出成片。输出是单一完整成片，不会保留参考视频中的“原片/成片”对照或剪辑台。平台外壳、功能目录和 hash 路由已经独立于该模块，后续工具可以复用同一导航、任务和设置结构。

## Start

```powershell
D:\Projects\semantic-video-animation-agent\.conda\python.exe -m pip install -r requirements.txt
D:\Projects\semantic-video-animation-agent\.conda\python.exe -m alembic upgrade head
cd animation-renderer
npm.cmd install
cd ..
D:\Projects\semantic-video-animation-agent\.conda\python.exe -m uvicorn backend.app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The site opens on a local creation home rather than an upload form. Enter **Semantic Video Animation** from the tool catalog, upload an MP4 (up to 100 MB), then review the generated video, transcript, plan, and B-roll choices. The workspace defaults to **real local `faster_whisper` + rule-based semantic planning** and a knowledge-media profile: confirmed exact entities use audited local assets first, marked unknown books use Open Library, and other B-roll uses Wikimedia Commons. Choose Mock explicitly only for a fast engineering smoke test. Use the global language selector to switch the complete platform and workflow between Chinese and English; the browser remembers the selection after refresh.

The generated-video preview is display-only and responsive: portrait output is centred with `max-width: 100%`, a viewport-relative `max-height`, and `object-fit: contain`. Preview requests are served inline with byte-range support, and the page changes the video source only once per completed render. This does not resize or recompress the downloadable result.

## Local creation platform UI

The frontend remains a build-free same-origin static app, split into `frontend/index.html`, `frontend/styles.css`, and `frontend/app.js`:

- `#/home` provides the creation home, real recent-task continuation, the data-driven tool catalog, and local/privacy explanations.
- `#/tools/semantic-video` contains the complete upload, processing, result, transcript/plan, media-review, cancel, and review re-render workflow.
- `#/tasks` lists only task IDs created or explicitly restored in this browser. A task can be recovered by its local ID; no sample tasks or fake statistics are generated.
- `#/settings` exposes the real interface-language and local-storage behavior without accounts, cloud sync, subscriptions, or other unavailable features.

The current task ID and recent-task index are stored in browser local storage, while authoritative task content remains in the FastAPI/SQLite backend. Refresh, hash navigation, and browser back/forward restore the same task without repeatedly assigning the video preview source. The responsive shell uses a persistent desktop sidebar and a mobile drawer, accessible review tabs, visible focus states, and reduced-motion support.

## Post-ASR correction

Real and Mock transcripts pass through a configurable Chinese phrase-correction layer before semantic planning. Rules live in `config/asr_corrections.json` (override with `ASR_CORRECTION_DICTIONARY`) and may require nearby context. A replacement reuses the matched ASR word interval; it never invents a timestamp. The task transcript exposes corrected `full_text`/`segments`, an immutable `raw_asr` snapshot, and timestamped `corrections` for review. The baseline dictionary covers `会姑娘` → `灰姑娘` in story context, `心理学有生活` → `心理学与生活` in book context, and reviewed phrases observed in the reference talk such as `对抑` → `可以`, `应有` → `拥有`, and weak comparative wording. Review re-renders apply the current dictionary before deciding whether a deterministic replan is needed.

## Visual style

`knowledge_talking_head_v1` is rendered by the shared Remotion overlay:

- short, transcript-derived readable captions stay at the bottom; a complete short phrase remains in one caption window instead of being split by a fixed timer, while matching phrase/word timing changes colour, scale, outline, and pop motion for important wording;
- `keyword_pop_v1` makes a key phrase large with strong outline/shadow rather than showing one uniform subtitle style;
- `media_visual_v1` presents an image/video as a face-safe side card or a brief full-screen B-roll cut while captions remain on top;
- `knowledge_infographic_v1` supports transcript-grounded numbered lists, comparison cards, and flow/relationship diagrams;
- local Haar face-safe analysis reserves the caption area and moves/shrinks/skips side cards. Full-screen B-roll is intentional short substitution, not a talking-head overlay.

The rule-based planner keeps transcript-grounded trigger text for timing but separately generates concise visible labels for cards and information graphics. It derives entity-specific retrieval queries for books and stories plus compact queries for factories, products, money, learning, people, places, and concepts. It keeps the shared grounding, overlap, and density rules: no more than two semantic visuals start in a 10-second window.

## Providers and external-media warning

> **External-material prototype, not suitable for direct commercial publication.**

`ASR_PROVIDER=mock` and `PLANNER_PROVIDER=mock` remain the server/configuration defaults, so tests and the baseline work without a model service or network. The browser overrides those defaults per upload with its recommended real profile. `ASR_PROVIDER=faster_whisper` plus `PLANNER_PROVIDER=rule_based` uses local CPU ASR with real word timings; emphasized phrases are anchored to the matching word span instead of the beginning of the containing ASR segment. `PLANNER_PROVIDER=local_llm` is restricted to a loopback OpenAI-compatible endpoint.

External B-roll is optional and never becomes a factual source:

```powershell
# Default: no network; use original task-local concept graphics.
$env:MEDIA_PROVIDER = 'mock'

# Actual no-key image/video candidate search through Wikimedia Commons.
$env:MEDIA_PROVIDER = 'wikimedia_commons'

# Recommended no-key profile: Open Library for marked books, Commons otherwise.
$env:MEDIA_PROVIDER = 'knowledge'

# Optional Pexels image/video search.
$env:MEDIA_PROVIDER = 'pexels'
$env:PEXELS_API_KEY = '...'
```

`MEDIA_PROVIDER=manual` disables automatic search and asks the reviewer to add an explicit `http(s)` URL. Missing `PEXELS_API_KEY` returns a clear API error. Network access to Open Library, Wikimedia/Pexels, and the downloaded source must be permitted by the environment. Automatic selection first requires candidate title/author metadata to match meaningful query terms; portrait shape is only a tie-breaker. If an exact entity cannot be matched, the pipeline uses the task-local original card rather than a plausible-looking unrelated image. The reviewer must still inspect source, licence/terms, edition accuracy, people/trademark rights, and platform suitability before publishing; the application neither claims copyright clearance nor waives human review. See [MEDIA_ASSET_POLICY.md](MEDIA_ASSET_POLICY.md).

`knowledge` mode includes deterministic local mappings for the user-confirmed `Psychology and Life` cover and an original Cinderella illustration. These are copied into each task and audited like other media before any network lookup, so those two exact concepts remain correct when Open Library or Wikimedia is blocked. Full-screen static media uses `object-fit: contain` to keep the complete cover/illustration visible. The supplied book-cover reference remains prototype material and requires publication-rights review.

Automatic Wikimedia search/download timeouts or rate limits fall back to the authored task-local knowledge graphic so a long render is not lost. An explicitly reviewer-selected candidate remains strict: a failed download is shown as an error rather than silently replaced.

## Review workflow and API

After a result is ready, the advanced review tabs expose the transcript and plan JSON editors, material review, and task events without putting large editors in the initial upload view. The B-roll panel shows automatic selections, provider, source URL, query, and timing; it searches images or videos, allows a manual URL, selects a replacement for a visual, or disables it. Click **Save edits and re-render** to download a selected candidate into the task and render the new result. If transcript segment text changed, the backend automatically rebuilds the animation plan from the edited transcript. Media audit metadata, face regions, and placements are renderer-derived: the review endpoint discards stale client copies, materializes enabled visuals, repeats local placement analysis, and then performs strict final validation. An explicitly selected missing or failed candidate remains an error.

- `POST /api/videos` uploads an MP4 and returns `202` plus a task ID. Multipart field `workflow_mode=standard|agent` defaults to `standard`; `processing_profile=configured|real|mock` and `media_provider=mock|manual|knowledge|wikimedia_commons|pexels` keep their existing task-local meanings.
- Agent uploads may also include `director_instruction` (maximum 2,000 characters). Standard uploads discard this Agent-only field and keep their original behavior.
- `GET /api/videos/{task_id}` returns metadata, transcript, plan, and status.
- `GET /api/videos/{task_id}/media` returns adopted assets, use intervals, and stored candidates.
- `POST /api/videos/{task_id}/media/search` searches the configured provider with `{query, asset_kind}`.
- `POST /api/videos/{task_id}/media/candidates` adds a manual candidate URL.
- `GET /api/videos/{task_id}/metrics` returns the privacy-safe metrics report.
- `GET /api/videos/{task_id}/agent-trace` returns the Agent-only, privacy-safe planning/validation audit with planner identifiers, retry count, structured violations, and call durations.
- `GET /api/videos/{task_id}/download` downloads completed `result.mp4`.
- `GET /api/videos/{task_id}/events` streams status events; `POST /api/videos/{task_id}/cancel` cancels an active task.
- `PUT /api/videos/{task_id}/transcript` edits the transcript; `POST /api/videos/{task_id}/review` validates and re-renders the transcript/plan.

Runtime files live under `storage/{task_id}/`: source/audio, `remotion_props.json`, `animation.mov`, ASS fallback subtitles, `result.mp4`, `quality.json`, `face_safe_areas.json`, `media_candidates.json`, `media_assets.json`, and `metrics.json`. Props stay in the task-local file, so no complete plan or base64 media is placed on the Windows command line.

In Agent mode, planning and validation run behind Pydantic typed tool envelopes. Every candidate is validated first as `AnimationPlan` and then with the transcript-grounded `planning_rules`. Structured violations are returned to a repair-capable planner for at most two repair calls. Exhaustion produces a terminal, auditable failure; there is no unbounded retry loop. The task-local `agent_trace.json` records only call metadata and bounded summaries—it excludes transcript/director text, plan bodies, absolute paths, media content, and exception messages. Deterministic Mock/rule planners remain offline; only the configured loopback local-LLM planner interprets free-form director instructions.

`workflow_mode=agent` is the API-only recoverable path introduced in P1; the existing page continues to use the stable `standard` path. The Agent executes `upload_probe → audio_asr → correction → planning → validation → render → quality → complete`, emits real `agent_node` SSE events, and uses the task ID as its thread/run ID. JSON checkpoints are transactionally stored in the separate `storage/agent_checkpoints.sqlite3` database after each successful node. On a single-process FastAPI restart, unfinished Agent tasks resume at their next checkpointed node; already completed nodes are not replayed. A node interrupted before its checkpoint is committed can run again with at-least-once semantics.

## Provenance, safety, and quality

Every adopted asset is downloaded into `media-assets/`; the plan and `media_assets.json` record the provider, search query, download/source-page URLs, acquisition time, SHA-256 digest, MIME type, and exact use interval. Remotion receives only a hash-verified task-local data URI. When no candidate is available, it uses a designed original concept graphic rather than a simple book SVG placeholder.

Successful output is checked with `ffprobe` and FFmpeg decode. `metrics.json` records only a SHA-256 trace fingerprint, stage durations (including media acquisition and local safety analysis), terminal category, and technical output facts—never transcript text, media bytes, absolute paths, identity data, face coordinates, or exception messages.

## Verification

Current P2 verification: `114 passed`, including standard and `agent+mock` FFmpeg/Remotion pipelines, checkpoint restart coverage, typed planning/validation tools, bounded repair, director-instruction isolation, and privacy-safe Agent Trace coverage. P2 did not change TypeScript, Remotion source, the renderer contract, or the `AnimationPlan` schema, so no new renderer build was required.

```powershell
D:\Projects\semantic-video-animation-agent\.conda\python.exe -m pytest -vv
cd animation-renderer
npm.cmd run build
```
