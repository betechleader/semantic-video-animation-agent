# Stage Plan

| Stage | Status | Code evidence | Verification evidence | Missing items |
|---|---|---|---|---|
| 0 — Audit and baseline | COMPLETED | `AGENTS.md`, this plan, and current status document | Clean `master`, committed history inspected, pytest and renderer build pass | None for this baseline audit |
| 1 — Minimum vertical pipeline | COMPLETED | FastAPI upload/probe, Mock ASR/planner, KeywordPop, Remotion, FFmpeg, SQLite task lookup/download | 10 pytest tests, including actual render/composite E2E; Remotion bundle passes | No real ASR/LLM by design |
| 2 — Engineering foundation | COMPLETED | Settings, mock Provider protocols, StorageService, renderer workflow, SQLAlchemy/Alembic task/event tables, trace IDs, JSON logs, live SSE, process-tree cancellation and cleanup service | 17 pytest tests, Alembic head, asynchronous phase-one E2E and renderer bundle pass | SSE is task-stage progress rather than frame-level percentage; cleanup is an explicit service, not a scheduler |
| 3 — faster-whisper | COMPLETED | AudioService, Mock ASR Provider, FasterWhisperProvider (CPU int8, local-only), transcript persistence and edit API | 21 pytest tests; CPU int8 local small model transcribed a 94-second Chinese video with 27 segments and 283 word timestamps | One real sample validates the pipeline, not recognition quality across speakers or recording conditions |
| 4 — Subtitle system | COMPLETED | `backend/app/subtitles.py`, ASS task artifact, FFmpeg libass burn-in, deterministic safe-area wrapping | Subtitle unit tests, full pytest suite, renderer build, end-to-end MP4 burn-in probe | Font selection uses installed local fonts; no font download |
| 5 — Local LLM semantics | COMPLETED | Mock/local OpenAI-compatible planner providers, loopback-only endpoint guard, Chinese JSON prompt, Pydantic semantic segments | 27 pytest tests including local-provider response, endpoint, and invalid-output checks | No local LLM service was running during validation; real model quality remains unvalidated |
| 6 — Template library | COMPLETED | KeywordPop, QuoteCard, and multi-animation `AnimationOverlay` Remotion compositions | 27 pytest tests; E2E renders both templates; Remotion bundle passes | Template selection quality is deferred to semantic-planning rules |
| 7 — Semantic planning rules | NOT_STARTED | — | — | Timestamp binding, density/conflict validation |
| 8 — Review and editing UI | PARTIAL | Basic upload/result page | API/UI exercised in E2E | Progress, subtitle/plan review and edits, preview workflow |
| 9 — Quality and safe areas | NOT_STARTED | Output ffprobe validation only | E2E verifies output video stream | Decode/duration/audio/frame quality and safe-area checks |
| 10 — Evaluation/observability | NOT_STARTED | — | — | Metrics, trace IDs, privacy-aware logs |
| 11 — Optional RAG | NOT_STARTED | — | — | Deferred until core chain stabilizes |
| 12 — Optional MCP | NOT_STARTED | — | — | Deferred until services stabilize |
| 13 — LangGraph assessment | NOT_STARTED | — | — | Assess only when human resume/checkpoint complexity warrants it |
| 14 — Packaging/docs | PARTIAL | Basic README and Windows commands | Build/test commands validated | Architecture, local AI guide, evaluation/privacy/demo material |

## Current execution plan

Stage 6 is complete. Mock mode remains the default. Stage 7 (semantic planning rules) is the next eligible development stage.
