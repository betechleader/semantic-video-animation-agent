# Development Status

- Current branch: `master`
- Current commit before this stage: `8839a8a feat: add review and editing workflow`
- Current stage: Stage 9, quality and safe areas - completed.

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
