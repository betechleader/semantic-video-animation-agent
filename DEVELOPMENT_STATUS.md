# Development Status

- Current branch: `master`
- Current commit before this stage: `916d8dd 重构本地AI创作平台前端`
- Current stage: P1, recoverable Agent workflow foundation - completed after user acceptance.

## P1 delivered

- Added an additive upload field `workflow_mode=standard|agent`, defaulting to `standard`. The stable standard dispatcher, `processing_profile=configured|real|mock`, `media_provider`, public task API, Mock providers, review API, and render/download chain remain compatible.
- Added an explicit persistent state graph with the real nodes `upload_probe → audio_asr → correction → planning → validation → render → quality → complete`. It reuses the existing ASR, correction, planning-rule, media, face-safety, Remotion, FFmpeg, and quality services rather than cloning the standard pipeline.
- Uses `task_id` as the Agent thread/run ID and stores JSON state after every successful node in the separate `storage/agent_checkpoints.sqlite3` SQLite database. Checkpoint writes use transactions and compare-and-swap versions; state contains task-relative data and validated schemas rather than absolute artifact paths.
- FastAPI lifespan recovery scans only non-terminal Agent graph executions. Cancelled work converges to `cancelled`; completed nodes are skipped after restart; tasks currently in the existing manual review-render flow are not mistaken for an unfinished Agent graph.
- Added true `agent_node` events with `started`, `completed`, `failed`, and `resumed` payload states. Events contain node/thread/checkpoint metadata and error categories, with no fabricated percentage or internal reasoning.
- Added Alembic migration `0002_agent_workflow_persistence` for `workflow_mode`, `processing_profile`, `media_provider`, and task-local event deduplication. Existing 0001 rows are migrated to `standard/configured/mock`.
- Split reusable processing services so Agent render and quality are separately checkpointable while the original standard `render_and_composite` signature and metrics stages remain intact.

## P1 verification

- Targeted Agent/API/persistence regression: `D:\Projects\semantic-video-animation-agent\.conda\python.exe -m pytest -vv tests\test_agent_workflow.py tests\test_task_database.py tests\test_workflow_mode_api.py` → `14 passed in 6.21s`.
- Real Agent Mock render: `D:\Projects\semantic-video-animation-agent\.conda\python.exe -m pytest -vv tests\test_end_to_end.py::test_agent_mock_video_processing_pipeline` → `1 passed in 28.57s`.
- Full suite: `D:\Projects\semantic-video-animation-agent\.conda\python.exe -m pytest -vv` → `108 passed in 73.81s`.
- Standard renderer command `cd animation-renderer; npm.cmd run build` failed at the pre-existing locked `animation-renderer/build` directory with `EPERM`; that directory was not removed or overwritten.
- Equivalent isolated renderer validation `cd animation-renderer; npx.cmd remotion bundle src/index.ts --out-dir ..\storage\renderer_build_validation_20260812_p1` succeeded.
- `git diff --check` passed. The user-owned untracked file `how 提交哈希` remains untouched.

## P1 known limitations

- Recovery is designed for the current single-process local runtime. The in-memory active-task registry prevents duplicate runners within one process; distributed leases, persistent workers, heartbeats, and cross-process exactly-once execution remain P10 work.
- Checkpoints guarantee that successful nodes are not replayed. If a process dies while a node is executing but before its checkpoint commits, that current node can run again with at-least-once semantics; fixed task-local artifacts make the operation retry-safe, but an orphaned external process cannot be reclaimed after a hard OS crash.
- If a process dies after the terminal checkpoint and public task completion are durable but before `metrics.json` is finalized, the result remains safe and expensive nodes are not replayed, but that metrics attempt can temporarily remain `running`.
- Automatic plan repair/retry, director instructions, approval interrupts, Agent UI controls, and eval harness deliberately remain out of scope for P1. The existing manual review worker itself is not restart-recoverable; startup excludes it so an Agent terminal checkpoint cannot overwrite an interrupted review.
- No real local LLM, faster-whisper model, or external media provider was exercised in this phase. Automated Agent coverage is fully offline through Mock/Fake providers.

## Recommended P1 manual acceptance

1. Start FastAPI with the documented `.conda` interpreter and upload a short MP4 using multipart fields `workflow_mode=standard`, `processing_profile=mock`, and `media_provider=mock`; verify the existing result, review, events, and download behavior.
2. Upload the same MP4 with `workflow_mode=agent`, `processing_profile=mock`, and `media_provider=mock`; poll `GET /api/videos/{task_id}` until `completed`, then download and play `result.mp4`.
3. Open `GET /api/videos/{task_id}/events` during the Agent run; verify ordered real `agent_node` events for all eight nodes and no synthetic percentage in their payloads.
4. For a recovery check, stop the API after a completed node but before task completion, restart it, and verify the same task resumes from the next checkpoint rather than repeating earlier ASR/planning events.
5. Restart once more after completion and verify the completed task remains completed and downloadable without creating duplicate completed-node events.

P1 was explicitly accepted for commit. P2 has not been started.

## Stage 10G delivered

- Replaced the upload-form landing page with a restrained local AI creation App Shell: persistent desktop sidebar, mobile drawer, global page header, real local-runtime/privacy status, and `#/home`, `#/tools/semantic-video`, `#/tasks`, and `#/settings` routes.
- Added a data-driven tool catalog. Semantic video animation is the only enabled production module; two future extension positions are visibly disabled and marked planned rather than presented as working features.
- Added a creation home with a focused value statement, primary entry into semantic video, real browser-local recent-task continuation, and accurate local-processing/privacy explanations without accounts, paid plans, cloud sync, or fabricated statistics.
- Reorganized semantic video into progressive upload, processing, and review stages. Upload settings remain unchanged at the API boundary; processing now has a consistent progress/status system, event timeline, and cancel action; completed output prioritizes the responsive video and download action before advanced review.
- Moved transcript JSON, animation-plan JSON, B-roll search/manual candidate/enable-disable controls, and review re-render into accessible review tabs. Existing API paths and payload semantics remain unchanged.
- Preserved stable preview behavior by assigning `src` only when the task/render source key changes. Browser local storage remembers the language, current task ID, and recent real task IDs; refresh and history navigation restore the same task without rebuilding the view or reassigning the preview source.
- Split the build-free frontend into `index.html`, `styles.css`, and `app.js`. The design system defines shared colour, spacing, radius, shadow, focus, state, and motion tokens, includes keyboard tab navigation and reduced-motion support, and uses only system fonts and inline SVG icons.

## Stage 10G verification

- Full Python suite: `95 passed in 53.06s`. Frontend coverage now checks split static assets, complete Chinese/English keys, data-driven routes and tools, mobile drawer rules, responsive preview sizing, stable video source assignment, refresh/history persistence, and accessible review tabs while retaining all existing API/E2E coverage.
- In-app browser checks used 1440×900, 1024×768, and 390×844 viewports. The original 390 px page overflowed to 459 px; the redesigned Chinese and English screens had no over-wide controls or document overflow. Desktop used the fixed platform sidebar, 1024 px retained a two-column result layout, and mobile used a 306 px drawer plus naturally stacked forms, preview, summary, and review controls.
- Browser navigation covered the creation home → semantic-video workspace path, task recovery for the real completed 94.36 s / 540×960 task `fc606fb1-59b5-47ee-a6ad-bc9dd5d95b91`, transcript/plan/material review tabs, and browser back/forward with the same result and preview source key.
- A browser-uploaded 4.00 s / 360×640 local MP4 completed the actual Mock + local-original-media pipeline as task `01360a61-2d49-4f4e-b3a2-91b420ce15ab`. The browser showed live rendering at 76%, then loaded the completed preview, transcript, plan, and media review with a new completion-event source key.
- Standard `npm.cmd run build` reached the known locked `animation-renderer/build` directory and failed with `EPERM`; that directory was not removed or cleaned. `npx.cmd remotion bundle src/index.ts --out-dir ..\storage\renderer_build_validation_20260807_platform_ui` completed successfully.

## Stage 10G known limitations

- Recent-task indexing is intentionally browser-local because the backend does not expose a task-list endpoint. Existing tasks can be reopened by entering their task ID; authoritative status and content are still fetched from FastAPI/SQLite.
- Transcript and animation-plan editing remains JSON-based inside the advanced review tabs. A future module can add structured segment/word editing without changing the current API semantics.

## Stage 10F delivered

- Diagnosed the latest real task's two generic knowledge cards as two consecutive 20-second network timeouts: neither Open Library nor Wikimedia produced a candidate manifest, so the prior resilience path correctly but silently emitted `original_infographic` SVGs.
- Added deterministic local exact-entity assets for the user-confirmed `Psychology and Life` edition and an original Cinderella story illustration. `knowledge` mode now prefers these assets before network search and records their provider, query, rights note, hash, and usage interval in the normal task-local audit.
- Existing completed tasks no longer reuse an `original_infographic` when a matching curated entity asset is now available; a review re-render replaces the stale fallback automatically.
- Full-screen static B-roll now uses `object-fit: contain`, preserving the complete book cover or illustration instead of cropping the left and right edges.

## Stage 10F verification

- Full Python suite: `91 passed in 49.10s`, including exact book/Cinderella routing and stale-fallback replacement coverage.
- Both `openlibrary.org` and `commons.wikimedia.org` timed out with inherited proxy settings and with `requests.Session.trust_env = False`, confirming that search wording was not the failure cause in this local environment.
- Standard `npm.cmd run build` still encounters the pre-existing locked `animation-renderer/build` `EPERM`; the same renderer source bundled successfully to `storage/renderer_build_validation_20260807_stage10f`.

## Stage 10F known limitations

- The exact book cover is a user-provided prototype reference and still requires publication-rights review. Curated mappings currently cover only the confirmed book and Cinderella entities; unrecognized entities continue through provider search and then the authored concept-card fallback.

## Stage 10E delivered

- Replaced the 1.6-second dynamic-caption hard cut with complete short-phrase windows capped for a two-line portrait layout. The reference opening now keeps `对于自媒体博主来说` in one cue, so character-level ASR words no longer split `博/主` across consecutive screens; inter-word spacing is also tighter.
- Preview responses now use inline `video/mp4` delivery with byte-range support and no-store caching. The completion handler loads task data before assigning the source, and a task/event version key prevents duplicate assignments from resetting playback.
- Added the browser-recommended no-key `knowledge` provider. Planner-marked book queries resolve through Open Library Search/Covers with title/author provenance; other B-roll continues through Wikimedia Commons. Automatic selection now requires meaningful query terms to match candidate title/author metadata before portrait ratio or resolution can break ties.
- `心理学与生活` now searches the exact work and authors Richard J. Gerrig / Philip G. Zimbardo. The `灰姑娘` rewrite uses the entity query `Cinderella fairy tale illustration`; unrelated portrait candidates are rejected and exact-match failure falls back to the original task-local graphic.
- Split animation timing copy from display copy: `trigger_text` remains verbatim transcript text for grounding, while keyword, media-title, numbered-list, and comparison boxes receive concise context-aware labels such as `接触多元文化`, `着眼长远未来`, `设想一年后 / 只想明天`, and `思考行动带来的结果`.
- Extended reviewed ASR corrections for reference-video phrases including `对抑` → `可以`, `应有` → `拥有`, `更加好的创新性` → `更高的创新性`, and `你的拍的` → `你拍的`. Review re-renders apply the current dictionary before deciding whether to replan, so an older completed task can pick up these corrections safely.

## Stage 10E verification

- Full Python suite: `88 passed in 47.76s`, including actual FFmpeg/Remotion initial and review renders plus new subtitle, preview-range, provider-routing, relevance-ranking, correction, review-upgrade, and copy-summary coverage.
- Live no-key checks returned eight bibliographically matched Open Library candidates for `Psychology and Life` and selected a Gerrig/Zimbardo work cover. Wikimedia returned 18 Cinderella candidates and selected `Helen Stratton Cinderella.jpg`; the prior `David Rice Atchison` portrait is below the relevance threshold.
- In-app browser playback against a 94.362-second completed task remained `paused=false`, `ended=false`, `readyState=4`, and error-free while advancing from 25.795 s to 28.833 s over a three-second observation. The preview request returned `206 Partial Content`, `Content-Disposition: inline`, and `Accept-Ranges: bytes`.
- Standard `npm.cmd run build` still stops at the pre-existing locked `animation-renderer/build` directory with `EPERM`. The same source bundled successfully to `storage/renderer_build_validation_20260807_stage10e`.

## Stage 10E known limitations

- Open Library provides bibliographically matched covers but may not carry the exact Chinese edition shown in a reference image. Exact edition/cover approval remains a reviewer decision through the existing candidate/manual URL workflow.
- Display-copy summarization and ASR correction are deterministic, context-aware rules rather than a generative language model; additional domains need reviewed rules or a validated local LLM profile.

## Stage 10D delivered

- Added a configurable post-ASR Chinese correction layer backed by `config/asr_corrections.json`. Contextual replacements merge only existing word intervals and persist both an immutable `raw_asr` snapshot and timestamped correction records; no replacement creates a new time point.
- Corrected `会姑娘` to `灰姑娘` in story/rewriting context and `心理学有生活` to `心理学与生活` in book context. Subtitles, semantic segments, trigger text, titles, keywords, retrieval queries, and infographic content now consume the corrected transcript.
- Improved rule planning by stripping weak openings such as `然后`, `对于……来说`, `比如说`, and `而不是说`, limiting portrait keyword text to the renderer's three-line safe area, and merging at most two adjacent ASR fragments when a sentence split would otherwise create a residual phrase.
- Review saves now compare submitted and stored transcript content. A text change safely normalizes the edited segment onto its existing interval and automatically rebuilds the rule-based animation plan. Unchanged reviews retain reviewer animation/candidate decisions.
- The review API no longer trusts or requires the browser to synchronize `media_assets`, `face_regions`, or `media_placements`. It clears these derived fields before validation; media preparation then reloads only hash-valid task-local audits, reconciles enabled visuals and candidate selections, repeats placement analysis, and performs strict final validation. Missing or failed explicit candidates remain visible errors.
- The web preview is centred and responsive with `max-width`, viewport-relative `max-height`, and `object-fit: contain`; portrait preview sizing does not affect the 540×960 downloaded output.

## Stage 10D verification

- Full Python suite: `79 passed in 47.43s`, including actual FFmpeg/Remotion initial processing and a review re-render with a disabled media visual plus stale derived metadata.
- The original audit error was reproduced against task `482cabd9-9495-4edf-964d-4e2d038657d4` by disabling `animation_004` while retaining its audit metadata; the old entry raised `media asset audit metadata must exactly match media visual references` before rendering.
- Real source `D:\桌面\常用\自媒体创新性.mp4` completed as validation task `fc606fb1-59b5-47ee-a6ad-bc9dd5d95b91` with local `faster_whisper + rule_based`, Mock media, two recorded corrections, nine animations, and verified 94.362 s 540×960 audio/video output.
- The same real task accepted a review request that disabled `animation_004` while submitting two stale assets and placements. The review re-render completed and rebuilt the final plan to one enabled media visual, one audit, and one placement.
- Browser checks used 1440×900 and 390×844 viewports. Desktop preview max height resolved to 648 px; narrow preview max height resolved to 540.16 px, the review editor became one column, and document scroll width stayed equal to 390 px.
- Standard `npm.cmd run build` still fails because Windows denies removal of the locked `animation-renderer/build` directory (`EPERM`). `npx.cmd remotion bundle src/index.ts --out-dir ..\storage\renderer_build_validation_20260804_final` completed successfully.

## Stage 10D known limitations

- Phrase correction is deterministic and dictionary-driven rather than a general Chinese language model; new domains require reviewed dictionary/context entries.
- Reviewer editing remains JSON-based. Editing `segment.text` is supported and automatically reuses that segment's existing timing; there is no dedicated word-level correction form yet.
- Local LLM planning remains supported but was not live-model quality tested in this stage; the automatic review replan path intentionally uses the deterministic rule planner.

## Stage 10C delivered

- Added the `knowledge_talking_head_v1` visual language: phrase/word-timed Remotion captions, outlined emphasis words, oversized key-phrase pop motion, and retained task-local ASS as a non-visible export fallback.
- Added `knowledge_infographic_v1` for number lists, two-way comparison cards, and flow/relationship diagrams. The rule-based planner selects a transcript-grounded visual/query for book, factory, product, money, learning, people, and place mentions, otherwise derives a diagram or key phrase.
- Added `media_providers.py` with a replaceable Provider interface: offline `mock`, no-key `wikimedia_commons`, keyed `pexels`, and reviewer-driven `manual`. Pexels without `PEXELS_API_KEY` returns an actionable error.
- Each selected external asset is downloaded to the task and tracked in `media_assets.json` with Provider, query, source/download and source-page URLs, author/provider, declared licence text, MIME type, download time, SHA-256, local path, and exact use interval. Search candidates are persisted in `media_candidates.json`; Remotion only receives hash-verified task-local data URLs.
- The browser review page now displays applied assets, source/query/timing, lets a reviewer search images or videos, add a manual URL, select a replacement, or disable a visual before the existing review re-render.
- Default server `MEDIA_PROVIDER=mock` remains offline and produces a designed original concept graphic instead of a generic book placeholder. The browser's recommended upload profile explicitly selects real ASR/rule planning and Wikimedia per task; Mock remains selectable. External media is explicitly marked as a non-commercial effect-validation prototype; no licence, factual, likeness, trademark, or platform clearance is claimed.
- Face-safe corner analysis still protects the talking head and subtitle region for side cards. Full-screen B-roll is restricted to brief planned intervals and preserves the dynamic caption layer above it.

## Stage 10C verification

- Full Python suite: `69 passed in 46.32s` (includes actual initial and review FFmpeg/Remotion end-to-end renders).
- `npm.cmd run build` reached a pre-existing Windows `EPERM` lock on `animation-renderer/build`; no generated directory was deleted or overwritten. The equivalent `npx.cmd remotion bundle src/index.ts --out-dir ..\storage\renderer_build_validation` completed successfully in an isolated runtime directory.
- Unit tests cover Wikimedia response provenance parsing, missing Pexels-key error, selected external-media task-local download/hash/data-URL preparation, dynamic subtitle emphasis, and media review API candidate persistence.
- The rule planner now normalizes the unquoted ASR variant `心理学有生活`, creates numbered-method and comparison graphics, rejects incomplete comparison placeholders, and anchors visible effects to matching word/phrase timestamps rather than every segment start.
- Automatic Wikimedia search or download failures fall back to a task-local original infographic. Explicit reviewer selections and Pexels configuration errors remain strict and visible.
- A real no-key Wikimedia query/download succeeded for `supermarket product`; its source and SHA-256 were saved in the reference-validation task manifest. A locally cropped eight-second talking-head region from `D:\桌面\示例.mp4` rendered as a single output with correct Chinese dynamic captions, a large yellow key phrase, and full-screen supermarket B-roll overlaid by readable captions.
- The 94.36-second user source `D:\桌面\常用\自媒体创新性.mp4` was processed with real local `faster_whisper` and reviewed/re-rendered as task `482cabd9-9495-4edf-964d-4e2d038657d4`. The final task has 12 word/phrase-timed visual nodes, three visible full-screen B-roll/semantic inserts, three numbered-method cards, three comparison cards, continuous dynamic subtitles, and verified 540x960 audio/video output. One adopted Wikimedia psychology-research image has its URL, provider, acquisition time, use interval, and SHA-256 in the task-local manifest; two rate-limited searches fell back to authored concept graphics.
- Standard `npm.cmd run build` still encounters Windows `EPERM` while Remotion tries to remove the existing locked `animation-renderer/build` directory. The same final renderer source successfully bundled with `npx.cmd remotion bundle src/index.ts --out-dir ..\storage\renderer_build_validation_v2`.

## Stage 10C known limitations

- Wikimedia/Pexels candidate matching is deterministic metadata/orientation ranking, not learned editorial relevance scoring. Video B-roll depends on Chromium/Remotion support for the downloaded container; Pexels prioritizes MP4 candidates.
- This is deliberately **not** a commercial-publication workflow. A reviewer must check current source terms, licences, factual relevance, personalities, trademarks, and platform use before release.
- The local Haar detector remains a lightweight frontal-face safeguard rather than general person segmentation; full-screen cuts intentionally substitute the shot for a short interval.

## Stage 10 delivered

- Every accepted task now creates task-local `metrics.json`. It uses a SHA-256 fingerprint of the existing `trace_id` for correlation rather than copying a caller-provided trace header into the artifact.
- Metrics are grouped by attempt: the initial upload/probe plus processing attempt is retained, and every review re-render adds its own attempt instead of overwriting earlier timings.
- The initial attempt measures upload/probe, audio extraction, ASR, planning, media acquisition, local media-safety analysis, Remotion rendering, FFmpeg compositing, and quality checking. A review attempt measures the render-side phases it actually runs.
- Each attempt records terminal status, summed stage duration, controlled output technical quality (dimensions, duration, frame rate, frame count, audio presence), and a failure category without copying an exception message.
- `metrics.json` explicitly excludes frames, audio, transcript text, absolute paths, identity data, face coordinates, and exception messages. Mock mode remains local-only; an explicitly selected external-media Provider may contact its configured source but metrics itself never emits telemetry.
- Added `GET /api/videos/{task_id}/metrics`, a read-only JSON endpoint for the task-local report. It is available while a task is running and never creates or modifies artifacts.
- Failure, cancellation, and review-render failure paths finalize the relevant attempt with an accurate terminal status and category.
- Remotion input props are stored in task-local `remotion_props.json` and passed by filename, avoiding the Windows command-line length limit for long plans or embedded original SVG visuals.

## Stage 10 verification

- Unit and API tests cover privacy exclusions, hashed trace correlation, read-only metrics lookup, failed audio extraction, pre-start cancellation, and separate review attempts.
- The actual FFmpeg/Remotion end-to-end test verifies all eight initial stages, output technical quality, and a completed second review attempt.

## Stage 10B delivered

- Added `opencv-python-headless` and a local CPU-only OpenCV Haar face detector. It samples source frames at one-second intervals (up to 120 samples) and sends no frame, crop, identity, embedding, or detection result to a network service.
- Detected face boxes are expanded into protected talking-head/upper-body zones, so a topic visual avoids the face and likely key subject rather than merely avoiding the face rectangle.
- The layout engine reserves the ASS subtitle area, tries safe corners in deterministic order, progressively scales a media visual down to 50 percent, and suppresses it when no corner remains safe.
- Each render writes `face_safe_areas.json` beside the result with local detector details, sampled times, coordinates, protected zones, subtitle reservation, and selected placements. Derived regions and placements are also saved in the task plan returned by the API.
- Review re-renders repeat local analysis against `source.mp4`; client-supplied layout coordinates are not trusted as final placement.

## Stage 10B verification

- All repository tests under `tests/` pass: `51 passed`, including a real upload/FFmpeg/Remotion end-to-end render that invokes the local detector and checks its task-local report.
- `npm.cmd run build` passes for the Remotion renderer.
- Unit tests cover moving a visual away from a detected face, safe skip when no corner remains, protected-subject expansion, report persistence, and API review-plan validation.

## Known limitations

- The bundled Haar cascade is a fast local CPU safeguard for detectable frontal faces. It can miss profiles, very small or occluded faces, and non-human subjects; a future local person/subject-segmentation model can extend the same exclusion-zone interface.

## Stage 9 delivered

- Added a pre-render safe-area validator. It rejects keyword text that cannot fit within the renderer's 8 percent horizontal margin and rejects unsupported tiny video dimensions.
- Updated keyword and quote-card templates to size text from the target video width and wrap card text inside the safe width.
- Added a post-render quality gate. `ffprobe` verifies duration, dimensions, frame rate, frame count, and audio-stream expectations; `ffmpeg` decodes each required stream.
- Every successful render writes `quality.json` beside `result.mp4` with the measured output properties.

## Verification

- Full Python suite passes: `40 passed`.
- `npm.cmd run build` passes for the Remotion renderer.
- Quality unit tests cover safe-area and output metadata rejection paths.
- The end-to-end MP4 test checks `quality.json` for the initial render and the review re-render.

## Known limitations

- The quality gate is deterministic and technical. It does not yet score perceptual quality, speaker framing, or device-specific appearance.
- Stage 10 (evaluation and observability) is the next eligible stage.

## Offline content-aligned mode

- `ASR_PROVIDER=faster_whisper` and `PLANNER_PROVIDER=rule_based` run without a local LLM service. The planner selects readable highlights from real ASR segments and anchors every animation to that segment's real timestamps.
- On 2026-08-03, the local `small` faster-whisper model processed the available 94-second Chinese video into 27 segments and 283 word timestamps; the offline planner produced 13 validated highlights.
- `PLANNER_PROVIDER=local_llm` remains available for richer semantic selection after a loopback-compatible local LLM service is started.

## Stage 10A delivered

- Added `media_visual_v1`, a timeline-bound Remotion template for topic visuals, while retaining the shared planning density, grounding, conflict, safe-area, alpha, and output-quality checks.
- The pipeline does not download or place web images. Book/topic mentions use a generic task-local original SVG illustration rather than a specific or recognisable book cover.
- Every visual material is written to `media_assets.json` and the saved plan with source URI, provider, licence, permitted transformations, acquisition time, task-relative local path, SHA-256 digest, and asset kind. The renderer verifies that the local file remains inside the task directory and matches its digest.
- Mock mode now exercises the media template; `faster_whisper` plus `rule_based` produces the same safe fallback for real ASR segments that mention a book/topic.

## Stage 10A verification

- Full Python suite passes: `47 passed`, including the API and actual FFmpeg/Remotion end-to-end render path.
- `npm.cmd run build` passes for the Remotion renderer.
- Unit tests cover book-title selection, provenance manifest fields, local-file hash rejection, and duplicate audit metadata rejection.
- The end-to-end MP4 test confirms the generated original asset manifest is stored beside the rendered video.
- Rule-based planning tests cover title-visual priority over nearby keyword highlights, three-line keyword safe-area layout, and the observed `心理学有生活` ASR title variant.
