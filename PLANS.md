# Stage Plan

| Stage | Status | Code evidence | Verification evidence | Missing items |
|---|---|---|---|---|
| 0 Audit and baseline | COMPLETED | `AGENTS.md`, plan, and status documents | Repository audit and baseline tests | None |
| 1 Minimum vertical pipeline | COMPLETED | FastAPI upload/probe, Mock ASR/planner, Remotion, FFmpeg, SQLite | Render/composite end-to-end test | Real ASR/LLM intentionally deferred |
| 2 Engineering foundation | COMPLETED | Settings, storage, task/event persistence, SSE, cancellation | Unit/API tests and Alembic head | No process restart recovery |
| 3 faster-whisper | COMPLETED | Local CPU int8 transcription with word timings | Unit tests and one local Chinese sample | Recognition quality across speakers remains unmeasured |
| 4 Subtitle system | COMPLETED | ASS generation and FFmpeg libass burn-in | Subtitle tests and output probe | Font selection only uses installed fonts |
| 5 Local semantics | COMPLETED | Loopback-only local LLM, optional fixed-official-endpoint DeepSeek, and offline transcript-grounded rule-based planners | Offline Provider/security tests and real local ASR/plan validation | No live local-LLM or DeepSeek quality validation |
| 6 Template library | COMPLETED | KeywordPop, QuoteCard, multi-animation overlay | E2E renders both templates; renderer build | Selection quality deferred to rules |
| 7 Semantic planning rules | COMPLETED | `planning_rules.py` validates grounding, duration, density, overlap, and IDs for both planners | Unit, API failure-path, and Mock E2E tests | Thresholds are deterministic safeguards, not learned editorial scoring |
| 8 Review and editing UI | COMPLETED | Browser preview, transcript/plan JSON review, review re-render API, SSE event cursor | API tests and actual review re-render E2E | Editing uses JSON rather than form-level controls |
| 9 Quality and safe areas | COMPLETED | Responsive template layout, safe-area validation, decode/metadata quality gate, `quality.json` artifact | Unit checks and two-pass render E2E; renderer build | No visual-perceptual scoring or device-specific review |
| 10A Local original-media fallback | COMPLETED | Task-local original concept graphic and audit/hash validation | Unit and initial pipeline E2E | Superseded as the only allowed source by 10C |
| 10B Local face-safe media placement | COMPLETED | Local CPU OpenCV Haar sampling, protected talking-head exclusion zones, deterministic corner/shrink/skip media layouts | Unit, API, actual FFmpeg/Remotion E2E, renderer build | Haar detection is limited to detectable frontal faces; it is not general-purpose subject segmentation |
| 10 Evaluation/observability | COMPLETED | Task-local privacy-safe `metrics.json`, hashed trace correlation, per-attempt stage timings, output technical quality, failure categories, and read-only API | Unit/API tests plus actual FFmpeg/Remotion initial and review re-render E2E | No perceptual/editorial scoring yet |
| 10C Knowledge-talk visual prototype | COMPLETED | Word/phrase dynamic captions, `knowledge_infographic_v1`, full/side B-roll, no-key Wikimedia/Pexels/manual Provider interface, task-local candidate and provenance manifests, review UI/API | Provider/unit/API tests, actual FFmpeg/Remotion initial and review re-render E2E, renderer build | No learned visual ranking, no commercial rights or factual validation, limited subject segmentation |
| 10D Transcript correction and review robustness | COMPLETED | Configurable contextual ASR correction with raw/corrected provenance, corrected-text planning, adjacent-fragment merge, automatic review replanning, server-owned media audit/placement rebuilding, responsive preview | Unit/API/E2E tests, real 94.36 s faster-whisper render and stale-media review re-render, desktop/narrow browser checks, isolated renderer bundle | Dictionary remains curated and deterministic; JSON transcript editing is not a word-level form UI |
| 10E Caption, preview, media relevance, and display-copy quality | COMPLETED | Complete short-phrase caption windows, stable inline range preview, Open Library + Wikimedia knowledge provider, metadata relevance gate, entity-specific queries, context-aware animation summaries | 88 Python tests, live Open Library/Commons query checks, in-app browser continuous-play validation, isolated renderer bundle | Exact external edition/cover still requires reviewer confirmation; summaries remain deterministic rules |
| 10F Deterministic exact-entity visual fallback | COMPLETED | Curated exact book/Cinderella assets, audited local selection before network search, stale fallback replacement, uncropped full-screen static media | 91 Python tests, local timeout diagnosis, isolated renderer bundle | Curated entity set is intentionally small; book-cover publication rights still need review |
| 10G Local AI creation platform UI | COMPLETED | Data-driven App Shell and tool catalog, `#/home`/tool/tasks/settings routing, progressive semantic-video workspace, recent-task recovery, responsive desktop/mobile navigation, bilingual design system | 95 Python tests, actual 4 s browser Mock workflow, completed 94.36 s task recovery, 1440×900/1024×768/390×844 browser checks, isolated renderer bundle | Recent-task discovery is browser-local unless a task ID is restored; advanced transcript/plan editing remains JSON-based |
| 11 Optional RAG | NOT_STARTED | — | — | Deferred until core chain stabilizes |
| 12 Optional MCP | NOT_STARTED | — | — | Deferred until services stabilize |
| 13 LangGraph assessment | NOT_STARTED | — | — | Assess when human resume/checkpoint complexity warrants it |
| 14 Packaging/docs | PARTIAL | Basic README and Windows commands | Build/test commands validated | Architecture, local AI guide, evaluation/privacy/demo material |

## Current execution plan

Stages 10, 10A, 10B, 10C, 10D, 10E, 10F, and 10G are complete. The site now opens as a local AI creation platform with a data-driven tool catalog; semantic video animation is its first production-ready module. Mock remains the offline server/test default, while the semantic-video workspace recommends real local ASR/rule planning and the `knowledge` media profile. The configured profile can optionally select DeepSeek through its fixed official endpoint; the key is read only from `DEEPSEEK_API_KEY`, and the remote transcript/direction privacy boundary is disclosed. The confirmed book and Cinderella entities use audited local exact assets before attempting no-key web search, so blocked providers cannot replace them with unrelated or generic visuals. Corrected transcript text is the sole input to subtitles and semantic planning; visible animation copy is separately summarized without changing grounded trigger timing. Review renders rebuild renderer-derived media state. External-source mode is explicitly a non-commercial effect-validation prototype. Stage 11 is optional and remains deferred while the core chain stabilizes.

## Portfolio Agent Upgrade Roadmap

| Phase | Status |
|---|---|
| P1 Recoverable Agent workflow foundation | COMPLETED |
| P2 Director instruction, typed tools, and plan auto-repair | COMPLETED |
| P3 Human-in-the-loop approval and resume | COMPLETED |
| P4 Agent mode in the existing page | COMPLETED |
| P5 Agent eval harness and observability | COMPLETED |
| P6 Local knowledge base and hybrid retrieval | COMPLETED |
| P7 Citation-grounded RAG semantic planning | COMPLETED |
| P8 Natural-language edits and visual timeline | COMPLETED |
| P9 MCP tool service | COMPLETED |
| P10 Production task execution and deployment | NOT_STARTED |
| P11 Evidence-based multi-Agent experiment | NOT_STARTED |
