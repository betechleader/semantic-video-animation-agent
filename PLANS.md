# Stage Plan

| Stage | Status | Code evidence | Verification evidence | Missing items |
|---|---|---|---|---|
| 0 — Audit and baseline | COMPLETED | `AGENTS.md`, this plan, and current status document | Clean `master`, committed history inspected, pytest and renderer build pass | None for this baseline audit |
| 1 — Minimum vertical pipeline | COMPLETED | FastAPI upload/probe, Mock ASR/planner, KeywordPop, Remotion, FFmpeg, SQLite task lookup/download | 10 pytest tests, including actual render/composite E2E; Remotion bundle passes | No real ASR/LLM by design |
| 2 — Engineering foundation | PARTIAL | SQLite task table and basic task status exist | Phase-one tests pass | Configuration system, provider interfaces, SQLAlchemy 2, Alembic, event persistence, trace logging, SSE, cancellation, cleanup, unified errors |
| 3 — faster-whisper | NOT_STARTED | — | — | Local ASR provider, word timestamps, audio extraction, transcript editing |
| 4 — Subtitle system | NOT_STARTED | — | — | ASS generation, local fonts, burn-in, layout checks |
| 5 — Local LLM semantics | NOT_STARTED | — | — | Mock/Local LLM providers, prompts, semantic segments |
| 6 — Template library | PARTIAL | KeywordPop only | E2E renders KeywordPop | Remaining templates and preview tests |
| 7 — Semantic planning rules | NOT_STARTED | — | — | Timestamp binding, density/conflict validation |
| 8 — Review and editing UI | PARTIAL | Basic upload/result page | API/UI exercised in E2E | Progress, subtitle/plan review and edits, preview workflow |
| 9 — Quality and safe areas | NOT_STARTED | Output ffprobe validation only | E2E verifies output video stream | Decode/duration/audio/frame quality and safe-area checks |
| 10 — Evaluation/observability | NOT_STARTED | — | — | Metrics, trace IDs, privacy-aware logs |
| 11 — Optional RAG | NOT_STARTED | — | — | Deferred until core chain stabilizes |
| 12 — Optional MCP | NOT_STARTED | — | — | Deferred until services stabilize |
| 13 — LangGraph assessment | NOT_STARTED | — | — | Assess only when human resume/checkpoint complexity warrants it |
| 14 — Packaging/docs | PARTIAL | Basic README and Windows commands | Build/test commands validated | Architecture, local AI guide, evaluation/privacy/demo material |

## Current execution plan

The next implementation phase is **Stage 2 — Engineering foundation**. It should preserve the phase-one flow while introducing configuration, clear service boundaries, SQLAlchemy-backed persistence and migrations, task events/state transitions, structured errors/logging, progress reporting, cancellation, and cleanup. Do not begin it automatically.
