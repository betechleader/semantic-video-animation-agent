# Stage Plan

| Stage | Status | Code evidence | Verification evidence | Missing items |
|---|---|---|---|---|
| 0 Audit and baseline | COMPLETED | `AGENTS.md`, plan, and status documents | Repository audit and baseline tests | None |
| 1 Minimum vertical pipeline | COMPLETED | FastAPI upload/probe, Mock ASR/planner, Remotion, FFmpeg, SQLite | Render/composite end-to-end test | Real ASR/LLM intentionally deferred |
| 2 Engineering foundation | COMPLETED | Settings, storage, task/event persistence, SSE, cancellation | Unit/API tests and Alembic head | No process restart recovery |
| 3 faster-whisper | COMPLETED | Local CPU int8 transcription with word timings | Unit tests and one local Chinese sample | Recognition quality across speakers remains unmeasured |
| 4 Subtitle system | COMPLETED | ASS generation and FFmpeg libass burn-in | Subtitle tests and output probe | Font selection only uses installed fonts |
| 5 Local semantics | COMPLETED | Loopback-only local LLM planner plus offline transcript-grounded rule-based planner | Provider tests and real local ASR/plan validation | No live local LLM quality validation |
| 6 Template library | COMPLETED | KeywordPop, QuoteCard, multi-animation overlay | E2E renders both templates; renderer build | Selection quality deferred to rules |
| 7 Semantic planning rules | COMPLETED | `planning_rules.py` validates grounding, duration, density, overlap, and IDs for both planners | Unit, API failure-path, and Mock E2E tests | Thresholds are deterministic safeguards, not learned editorial scoring |
| 8 Review and editing UI | COMPLETED | Browser preview, transcript/plan JSON review, review re-render API, SSE event cursor | API tests and actual review re-render E2E | Editing uses JSON rather than form-level controls |
| 9 Quality and safe areas | COMPLETED | Responsive template layout, safe-area validation, decode/metadata quality gate, `quality.json` artifact | Unit checks and two-pass render E2E; renderer build | No visual-perceptual scoring or device-specific review |
| 10A Copyright-compliant media visuals | COMPLETED | Task-local original SVG fallback, audit manifest/hash validation, transcript-grounded `media_visual_v1` Remotion template | Unit, API/pipeline E2E, renderer build | External licensed-source provider intentionally deferred until licence verification is implemented |
| 10B Local face-safe media placement | COMPLETED | Local CPU OpenCV Haar sampling, protected talking-head exclusion zones, deterministic corner/shrink/skip media layouts | Unit, API, actual FFmpeg/Remotion E2E, renderer build | Haar detection is limited to detectable frontal faces; it is not general-purpose subject segmentation |
| 10 Evaluation/observability | COMPLETED | Task-local privacy-safe `metrics.json`, hashed trace correlation, per-attempt stage timings, output technical quality, failure categories, and read-only API | Unit/API tests plus actual FFmpeg/Remotion initial and review re-render E2E | No perceptual/editorial scoring yet |
| 11 Optional RAG | NOT_STARTED | — | — | Deferred until core chain stabilizes |
| 12 Optional MCP | NOT_STARTED | — | — | Deferred until services stabilize |
| 13 LangGraph assessment | NOT_STARTED | — | — | Assess when human resume/checkpoint complexity warrants it |
| 14 Packaging/docs | PARTIAL | Basic README and Windows commands | Build/test commands validated | Architecture, local AI guide, evaluation/privacy/demo material |

## Current execution plan

Stages 10A, 10B, and 10 are complete. Mock mode remains the default. Stage 11 is optional and remains deferred while the local core chain stabilizes.
