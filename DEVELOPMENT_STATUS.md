# Development Status

- Current branch: `master`
- Current commit before this stage: `4fb1963 fix: load remotion props from task file`
- Current stage: Stage 10C, knowledge-talk external-media prototype - completed.

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
