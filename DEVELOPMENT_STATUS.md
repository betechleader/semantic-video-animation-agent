# Development Status

- Current branch: `master`
- Current commit before this stage: `2be3a6b feat: add copyright-safe media visuals`
- Current stage: Stage 10B, local face-safe media placement - completed.

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
