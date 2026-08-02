# Stage Plan

| Stage | Status | Code evidence | Verification evidence | Missing items |
|---|---|---|---|---|
| 0 Audit and baseline | COMPLETED | `AGENTS.md`, plan, and status documents | Repository audit and baseline tests | None |
| 1 Minimum vertical pipeline | COMPLETED | FastAPI upload/probe, Mock ASR/planner, Remotion, FFmpeg, SQLite | Render/composite end-to-end test | Real ASR/LLM intentionally deferred |
| 2 Engineering foundation | COMPLETED | Settings, storage, task/event persistence, SSE, cancellation | Unit/API tests and Alembic head | No process restart recovery |
| 3 faster-whisper | COMPLETED | Local CPU int8 transcription with word timings | Unit tests and one local Chinese sample | Recognition quality across speakers remains unmeasured |
| 4 Subtitle system | COMPLETED | ASS generation and FFmpeg libass burn-in | Subtitle tests and output probe | Font selection only uses installed fonts |
| 5 Local LLM semantics | COMPLETED | Loopback-only OpenAI-compatible local planner | Provider and invalid-output tests | No live local model quality validation |
| 6 Template library | COMPLETED | KeywordPop, QuoteCard, multi-animation overlay | E2E renders both templates; renderer build | Selection quality deferred to rules |
| 7 Semantic planning rules | COMPLETED | `planning_rules.py` validates grounding, duration, density, overlap, and IDs for both planners | Unit, API failure-path, and Mock E2E tests | Thresholds are deterministic safeguards, not learned editorial scoring |
| 8 Review and editing UI | COMPLETED | Browser preview, transcript/plan JSON review, review re-render API, SSE event cursor | API tests and actual review re-render E2E | Editing uses JSON rather than form-level controls |
| 9 Quality and safe areas | NOT_STARTED | Output ffprobe validation only | E2E verifies output video stream | Decode/duration/audio/frame and safe-area checks |
| 10 Evaluation/observability | NOT_STARTED | — | — | Metrics, trace IDs, privacy-aware logs |
| 11 Optional RAG | NOT_STARTED | — | — | Deferred until core chain stabilizes |
| 12 Optional MCP | NOT_STARTED | — | — | Deferred until services stabilize |
| 13 LangGraph assessment | NOT_STARTED | — | — | Assess when human resume/checkpoint complexity warrants it |
| 14 Packaging/docs | PARTIAL | Basic README and Windows commands | Build/test commands validated | Architecture, local AI guide, evaluation/privacy/demo material |

## Current execution plan

Stage 8 is complete. Mock mode remains the default. Stage 9 (quality and safe areas) is the next eligible development stage.
