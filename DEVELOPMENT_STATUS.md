# Development Status

- Current branch: `master`
- Current commit before this work: `4059a45 增加本地知识库与混合检索`
- Current stage: P7, Citation-grounded RAG semantic planning - implementation, automated verification, and browser acceptance complete; explicitly accepted for commit.

## P7 delivered

- Added Agent-only retrieval inside the existing planning node through the Pydantic-typed `RetrieveEvidenceInput`/`RetrieveEvidenceOutput` boundary. Corrected transcript segments become at most six bounded local queries; P6 keyword/vector/hybrid search remains the only index implementation and standard workflow does not call it.
- Extended `AnimationPlan` with versioned evidence references and per-animation `evidence_ids`, `confidence`, and `selection_reason`. The deterministic grounding adapter attaches only retrieved IDs whose current excerpts lexically support the visual claim. Unsupported factual media or knowledge graphics are downgraded to transcript emphasis; non-factual B-roll is normalized to explicit abstract concept packaging.
- Added a live evidence trust boundary. Agent validation, approval/edit, render, and Agent review re-render resolve cited chunks from the current P6 index and compare document ID, source, content SHA-256, index version, and the exact stored excerpt. Deleted, reindexed, changed, missing, unused, forged, or unsupported citations cannot proceed.
- Upgraded recoverable Agent checkpoint state to schema version 3 with evidence/query summaries while keeping schema 1 and 2 checkpoints readable. Planning repairs reuse the same retrieved evidence, and render performs a final live citation check before starting expensive media/render work.
- Upgraded Agent planning metadata to `agent-planning-v2-rag` and `animation-plan-v2-evidence`. Local/DeepSeek prompts receive only the bounded evidence catalog and must cite supplied IDs; the deterministic post-processor remains authoritative even when a model ignores the instruction.
- Agent Trace records `retrieve_evidence` as a real planning tool call with query IDs, SHA-256 query fingerprints, character counts, recall count, safe error categories, retrieved IDs, and adopted IDs. It does not persist query/transcript/evidence text, absolute paths, raw exceptions, or chain of thought.
- Added `GET /api/videos/{task_id}/evidence` and minimal evidence views inside the existing approval panel and completed Agent review tabs. Reviewers see local source names, excerpts, citing animation IDs, and live `valid|missing|stale` status without a new home card or site redesign.
- Extended the P5 offline harness to `agent-eval-v2-rag` with five self-authored evidence cases, an in-memory Fake retriever plus distractor, retrieval P50/P95 latency, `evidence_retrieval_hit_rate`, and `citation_correctness_rate`. No user storage, model, embedding download, or network service is used.
- No database column/table changed in P7: evidence and query summaries use the existing JSON plan/checkpoint/trace persistence, so no Alembic migration is required.

## P7 code structure and learning notes

- `rag_tools.py` owns typed retrieval, transcript-query construction, deterministic evidence attachment/safe downgrade, factual-visual classification, current-index validation, and reviewer-facing citation status. It reuses `KnowledgeBaseService` rather than implementing a second retriever.
- `agent_workflow.py` treats evidence retrieval as a tool inside the existing planning node, not as a fabricated graph node. Retrieval output is checkpointed with planning, repair reuses it, and the node/event sequence remains compatible with P1-P4 UI and recovery tests.
- Evidence references are an audit snapshot, not an authority. The current knowledge row is authoritative; a stored excerpt must match the current chunk prefix and content digest before it can support rendering.
- Keyword/quote emphasis remains transcript-grounded and may operate without project evidence. Fact-bearing info graphics and entity/topic visuals need supporting evidence; otherwise deterministic fallback removes the factual visual claim.

## P7 verification

- Modification baseline: `.\.conda\python.exe -m pytest -vv` → `150 passed in 91.66s`.
- Final focused Agent/RAG/knowledge/frontend/Eval and Agent Mock render regression: `.\.conda\python.exe -m pytest -q tests\test_rag_planning.py tests\test_agent_workflow.py tests\test_agent_plan_repair.py tests\test_agent_approval.py tests\test_agent_eval.py tests\test_frontend_i18n.py tests\test_knowledge_base.py tests\test_mock_pipeline.py tests\test_end_to_end.py::test_agent_mock_video_processing_pipeline` → `52 passed in 42.19s`.
- Final focused RAG/Eval/approval/review regression: `.\.conda\python.exe -m pytest -q tests\test_rag_planning.py tests\test_agent_eval.py tests\test_agent_approval.py tests\test_review_api.py` → `25 passed in 10.48s`.
- Full suite: `.\.conda\python.exe -m pytest -vv` → `154 passed in 94.91s`, including the existing standard Mock and Agent Mock real FFmpeg/Remotion end-to-end pipelines.
- Offline Eval: `.\.conda\python.exe -m evals.agent.cli --output-dir storage\agent_evals\p7_final` → exit code `0`, `Agent eval PASS`; Agent retrieval hit rate `1.0`, citation correctness `1.0`, task success `0.916667`, and tool-call success `0.864865`.
- `node.exe --check frontend\app.js` passed. Standard `npm.cmd run build` failed at the documented locked `animation-renderer/build` directory with `EPERM`; no existing directory was removed or overwritten. Equivalent isolated bundle `npx.cmd remotion bundle src/index.ts --out-dir ..\storage\renderer_build_validation_20260829_p7` succeeded.
- Browser acceptance on `http://127.0.0.1:8000` created an Agent Mock task with `approval_policy=always`. The task paused after validation with five completed pre-render nodes and zero retries, resumed after approval without repeating those nodes, completed all eight nodes, passed quality checks, and produced a 4.00-second 360x640 result. The Evidence tab showed the expected zero-citation safe downgrade, the 375 px viewport had no horizontal overflow, and the browser console had no errors.

## P7 known limitations

- Citation support uses deterministic lexical overlap plus exact current-chunk identity, not a learned natural-language entailment model. It prevents missing/forged citations and obvious unsupported mappings but does not prove that every nuanced claim logically follows from its source.
- Retrieval queries are corrected transcript segments rather than model-authored query decomposition. The six-query/three-result bounds favor predictable local execution; long or highly compositional talks may need later query planning and reranking improvements.
- Existing completed Agent videos remain downloadable after cited knowledge is deleted, because deleting knowledge does not erase an already-rendered artifact. Their evidence API reports `missing`, and approval/re-render paths reject the stale plan until it is safely replanned.
- The evidence UI is deliberately review-only and text-first. Natural-language plan patches, evidence replacement controls, and a visual timeline remain P8 scope.
- No real BGE-M3, local LLM, DeepSeek, external media provider, or user content was exercised in P7 automated verification.

## Recommended P7 manual acceptance

1. Upgrade/start the existing service, import a small UTF-8 knowledge file about a named book or topic, then upload a short `agent + mock` or `agent + configured` task. Confirm standard uploads still finish without any knowledge dependency.
2. For an Agent task whose transcript matches the imported file, open the approval panel (use `approval_policy=always`) or the completed “知识证据 / Evidence” tab. Confirm it shows a real `chunk_...` ID, source, excerpt, citing animation ID, confidence/reason in the plan, and `valid` status.
3. Open `GET /api/videos/{task_id}/agent-trace`. Confirm the `retrieve_evidence` tool call includes query hashes/lengths, recall count, retrieved IDs, and adopted IDs, while the query text, transcript, evidence excerpt, and absolute project path are absent.
4. Delete the cited knowledge document through the P6 API/CLI. Reload `GET /api/videos/{task_id}/evidence`; expect `valid=false` and `status=missing`. Try approval or review re-render with the old plan; expect HTTP 422 and no new render.
5. Run an Agent task with an empty knowledge base and a factual/book cue. Confirm it still completes offline and the unsupported factual visual becomes transcript emphasis or abstract packaging instead of inventing a citation.
6. Run `.\.conda\python.exe -m evals.agent.cli --output-dir storage\agent_evals\manual_p7`; expect exit code 0 and both evidence metrics at `1.0` in JSON/Markdown.

P7 was explicitly accepted and approved for commit. P8 has not been started.

## P6 delivered

- Added a project-controlled knowledge base under `storage/knowledge/`, separate from UUID video-task directories. It imports UTF-8 `txt`, `md`, and `json` only, enforces a configurable 5 MB default limit, rejects path-bearing upload names, and stores source copies only beneath the knowledge root.
- Added Alembic revision `0005_local_knowledge_base` with durable `knowledge_documents` and `knowledge_chunks` tables. Content hashes produce stable document IDs; document/ordinal/chunk hashes produce stable chunk IDs. The stored contract includes source metadata, deterministic summaries, content digests, chunk ordinals, token counts, embedding/model identifiers, and `knowledge-index-v1`.
- Reimporting identical content is idempotent and does not recompute embeddings. If the index version or embedding model changes, the same document ID is reindexed in place and retains stable chunk IDs whenever chunk content and order remain unchanged.
- Added Chinese-aware BM25 tokenization using Latin terms plus individual and adjacent Han characters. Added vector cosine search, weighted hybrid fusion, chunk-ID deduplication, and an optional bounded lexical coverage rerank. Every hit returns `chunk_id`, source, content, summary, score, component scores, retrieval method, metadata, and index version.
- Added a zero-download `local_hash` embedding Provider as the offline default and a replaceable Provider protocol used by Fake Embedding tests. Added optional BGE-M3 through pinned `sentence-transformers==6.0.0`; the loader requires `local_files_only=True`, sets `trust_remote_code=False`, uses the project model cache, and converts cache/package failures to fixed errors without attempting model downloads.
- Kept SQLite as the vector store for the current small project corpus. This avoids a new Qdrant process and preserves the project's single-file local recovery model while leaving embedding and retrieval boundaries replaceable if corpus scale later warrants Qdrant local mode.
- Added `POST/GET /api/knowledge/documents`, `DELETE /api/knowledge/documents/{document_id}`, and `POST /api/knowledge/search`. CPU/model indexing runs outside the async event loop. Added matching `python -m backend.app.knowledge_cli import|list|search|delete` commands; CLI imports are restricted to paths inside the project.
- P6 remains isolated from AnimationPlan, Agent planning, the semantic-video frontend, and existing video APIs. Evidence retrieval in planning and citation fields are deliberately deferred to P7.

## P6 code structure and learning notes

- `knowledge_base.py` owns parsing, deterministic chunking, IDs, embeddings, BM25/vector/hybrid scoring, storage-path validation, CRUD, and the Provider boundary. The service receives an embedding Provider, so tests never need a model or network.
- `KnowledgeDocument` is the source-level audit row; `KnowledgeChunk` is the retrieval unit. Deleting through the ORM cascades chunk deletion, while the source file path is resolved and verified against `storage/knowledge` before any unlink.
- `local_hash` is a transparent character/token feature vector, not a learned semantic model. Its role is deterministic zero-download vector retrieval. The configured BGE-M3 backend is the semantic option when the operator has installed dependencies and pre-populated the local cache.
- `json` imports are flattened deterministically with sorted object keys and a nesting bound. Markdown is indexed as text in P6; heading-aware structural parsing and PDF extraction were intentionally omitted to keep this phase scoped.
- Retrieval is read-only with respect to the index. Optional reranking changes only result order/score and does not mutate stored chunks.

## P6 verification

- Baseline before implementation: `.\.conda\python.exe -m pytest -vv` → `139 passed in 89.03s`.
- Final focused P6 suite: `.\.conda\python.exe -m pytest -q tests\test_knowledge_base.py` → `11 passed in 2.81s`.
- Broader knowledge/migration/storage/Provider regression: `.\.conda\python.exe -m pytest -vv tests\test_knowledge_base.py tests\test_task_database.py tests\test_storage_and_providers.py` → `24 passed in 4.20s` before the final API thread-pool hardening; the final focused and full suites passed afterward.
- Final full suite: `.\.conda\python.exe -m pytest -vv` → `150 passed in 92.35s`, including the existing standard Mock and Agent Mock real FFmpeg/Remotion end-to-end pipelines.
- `.\.conda\python.exe -m compileall -q backend\app alembic\versions` completed successfully. `.\.conda\python.exe -m alembic heads` reported the single head `0005_local_knowledge_base`.
- `git diff --check` is part of final verification. P6 changes no TypeScript, Remotion source, renderer props, or `AnimationPlan`, so a renderer build is not required.

## P6 user acceptance verification

- The project database upgraded successfully and `.\.conda\python.exe -m alembic current` reported `0005_local_knowledge_base (head)`.
- A real offline CLI run imported the project `README.md` as eight chunks with `local-char-feature-hash-v1`. Reimport returned the same document ID with `created=false` and `reindexed=false`.
- Real keyword, vector, and hybrid-plus-rerank queries all returned source, stable chunk IDs, component scores, retrieval method, metadata, and `knowledge-index-v1` without a network or model download.
- The acceptance document was deleted through the CLI. A subsequent list returned no documents and `storage/knowledge/sources` was empty, so the temporary acceptance content was not left behind.
- Final acceptance-focused suite: `.\.conda\python.exe -m pytest -q tests\test_knowledge_base.py` → `11 passed in 2.85s`.
- Final acceptance full suite: `.\.conda\python.exe -m pytest -vv` → `150 passed in 91.81s`, including existing standard Mock and Agent Mock real FFmpeg/Remotion end-to-end pipelines.

## P6 known limitations

- The default feature-hash vectors provide local vector similarity but are not a substitute for a learned multilingual semantic model. BGE-M3 must already exist in the configured local model cache; no model was downloaded, and no real BGE-M3 quality/performance run was claimed in this phase.
- SQLite performs exact in-process cosine scans, which is appropriate for a small project knowledge base but not a large multi-user corpus. Qdrant local mode remains a replaceable scaling option rather than a runtime prerequisite.
- JSON is flattened and Markdown is treated as text. PDF, OCR, heading-aware chunking, learned rerankers, document update/version history, and background bulk indexing are not included.
- P6 exposes backend API/CLI only and does not add a knowledge-management page. It does not alter AnimationPlan or use retrieved text in planning; those citation and RAG trust-boundary changes belong to P7.
- Source-file persistence and database writes are durable but not yet coordinated by a cross-process import lease. Concurrent duplicate imports are constrained by unique content hashes, but production distributed-worker behavior belongs to P10.

## Recommended P6 manual acceptance

1. Run `.\.conda\python.exe -m alembic upgrade head`, then start FastAPI. Confirm the migration reports head `0005_local_knowledge_base` and an existing standard/Agent video task is still readable.
2. Create one small UTF-8 `.md` or `.txt` inside the project, run `.\.conda\python.exe -m backend.app.knowledge_cli import <path> --metadata '{"topic":"manual"}'`, and confirm the response contains `doc_...`, a positive `chunk_count`, `knowledge-index-v1`, and a source copy under `storage/knowledge/sources/`.
3. Import the same bytes again. Confirm `created=false`, `reindexed=false`, the same document/chunk IDs, and no duplicate in the `list` command.
4. Search a phrase with `--method keyword`, `--method vector`, and `--method hybrid --rerank`. Confirm each hit includes chunk ID, source, method, scores, summary, and index version; repeat with network disabled and confirm the default `local_hash` path still works.
5. Exercise the same import/list/search endpoints through FastAPI, then delete the returned document ID. Confirm the list and search no longer return it and an invalid/path-like ID cannot remove anything outside `storage/knowledge`.
6. Optionally pre-populate a local BGE-M3 cache, set `KNOWLEDGE_EMBEDDING_PROVIDER=bge_m3`, keep `KNOWLEDGE_EMBEDDING_LOCAL_FILES_ONLY=true`, restart, and import a new document. If no local model exists, expect a fixed local-cache error and no network download.

P6 was explicitly accepted and approved for commit. P7 has not been started.

## P5 delivered

- Added an independent `evals/agent/` offline evaluation package and CLI. It reads a versioned dataset, executes both standard and Agent planning paths with the same deterministic Mock planning Provider, applies regression thresholds, and writes machine-readable JSON plus human-readable Markdown under project `storage/` only.
- Added 12 small self-authored Chinese transcript cases. No video, transcript, or artifact from user `storage/` is part of the dataset. Two deterministic scenarios fail once and repair successfully; one persistently overlaps and stops for human intervention after the bounded repair limit.
- Implemented AnimationPlan schema pass rate, transcript grounding precision, legal timing rate, overlap violation rate, tool-call success rate, automatic repair success rate, average retry count, human-intervention rate, task success rate, and per-stage nearest-rank P50/P95 latency.
- Added an explicit standard-versus-Agent comparison with metric deltas. The report excludes transcript text, absolute paths, user task content, prompts, model content, and internal reasoning.
- Added versioned min/max regression gates in `default_thresholds.json`. The CLI returns exit code 1 when a gate fails and returns 0 only when all configured gates pass.
- Upgraded production Agent Trace to `agent-trace-v2`. Every entry has a stable run ID and node-run ID; planning/model/validation calls also have stable tool names and tool-call IDs. All eight graph nodes now record started/completed/failed lifecycle entries with measured duration. Existing v1 trace JSON is upgraded in memory and remains readable.
- Added focused documentation describing the package structure, CLI, metric definitions, privacy boundary, and the deliberate choice to keep OpenTelemetry disabled in P5.

## P5 code structure and learning notes

- `evals/agent/data/chinese_cases.json` is data, not executable test logic. Its schema version and typed Pydantic loader make malformed cases fail early.
- `evals/agent/harness.py` separates per-run observation from aggregation. Standard and Agent use the same Provider input; only their orchestration boundary differs. This makes the comparison attributable to workflow behavior instead of different model output.
- `invoke_planning_tool` and `invoke_validation_tool` are reused directly. The repair loop is bounded by the production `MAX_PLAN_REPAIR_ATTEMPTS`, so the eval does not create a second definition of retry behavior.
- Metric numerators and denominators are retained in run observations and converted to ratios only during aggregation. Empty denominators become JSON `null` rather than a misleading zero.
- `evals/agent/reporting.py` keeps regression policy separate from measurement. A stricter threshold file can therefore change CI acceptance without changing evaluator code.
- `backend/app/agent_trace.py` treats run → node → tool as identifiers rather than nested mutable objects. This keeps append-only audit entries easy to stream, compare, and migrate while avoiding chain-of-thought storage.

## P5 verification

- Baseline before implementation: `.\.conda\python.exe -m pytest -vv` → `134 passed in 98.91s`.
- User-acceptance targeted eval/Trace/Agent/metrics suite: `.\.conda\python.exe -m pytest -q tests\test_agent_eval.py tests\test_agent_plan_repair.py tests\test_agent_workflow.py tests\test_metrics.py` → `17 passed in 9.34s`.
- User-acceptance full suite: `.\.conda\python.exe -m pytest -vv` → `139 passed in 87.65s`, including the real FFmpeg/Remotion standard Mock and Agent Mock end-to-end pipelines.
- Final CLI: `.\.conda\python.exe -m evals.agent.cli --output-dir storage\agent_evals\p5_final` → exit code `0`, `Agent eval PASS`; it wrote `agent_eval_report.json` and `agent_eval_report.md`.
- Final default-dataset results: standard task success `1.000000`; Agent task success `0.916667`; Agent tool-call success `0.843750`; auto-repair success `0.666667`; average retries `0.333333`; human intervention `0.083333`; transcript grounding precision `1.000000`; overlap violation rate `0.040000`.
- Manual acceptance reran the default CLI and verified 24 unique run IDs, 56 stable run/node/tool call records, privacy exclusions, and absence of transcript text or the project absolute path. A deliberately strict Agent task-success threshold returned exit code `1`, wrote `Agent eval FAIL`, and identified the expected `0.916667 < 1.0` failed gate.
- `.\.conda\python.exe -m compileall -q backend\app evals\agent tests\test_agent_eval.py` completed successfully. `git diff --check` passed; only existing line-ending warnings were emitted.
- Renderer build was not required because P5 changes no TypeScript, Remotion source, renderer contract, or `AnimationPlan` schema.

## P5 known limitations

- The initial corpus is a deliberately small smoke/regression set, not a statistically representative editorial-quality benchmark. It uses the deterministic Mock Provider and synthetic fault scenarios; no real local LLM, DeepSeek, faster-whisper model, network Provider, or user content was evaluated.
- Grounding precision is lexical/timing based. It does not yet score factual correctness, visual aesthetics, evidence citation, or human preference; evidence metrics belong after P6/P7.
- Sub-millisecond local Mock latencies primarily validate instrumentation and percentile calculation, not production capacity. Real-provider latency baselines must be collected separately without weakening offline CI.
- OpenTelemetry export is intentionally not implemented. The default remains local JSON/Markdown with no telemetry dependency or outbound connection.

## Recommended P5 manual acceptance

1. Run `.\.conda\python.exe -m evals.agent.cli --output-dir storage\agent_evals\manual_acceptance` with network access disabled; expect exit code 0 and `Agent eval PASS`.
2. Open the generated JSON and Markdown. Confirm both standard and Agent columns contain all nine quality/outcome metrics plus planning/validation P50/P95 latency, and the report has 24 stable `eval:<mode>:<case>` runs with node/tool call IDs.
3. Inspect `evals/agent/data/chinese_cases.json`; confirm there are 12 `self_authored` Chinese cases, two one-repair scenarios, one persistent-overlap scenario, and no user task/video/transcript paths.
4. Copy `default_thresholds.json` under `storage/`, change Agent `task_success_rate.min` to `1.0`, rerun with `--thresholds <copy>` and a new storage output directory; expect exit code 1, `Agent eval FAIL`, and a failed gate in both reports.
5. Run one short `agent + mock` task through the existing API/UI, then open its Agent Trace. Confirm schema `agent-trace-v2`, one run ID, node lifecycle records for all eight graph nodes, and named planning/validation tool-call IDs without transcript/director text or absolute paths.
6. Run a standard Mock task and confirm its upload, render, preview, download, and existing metrics behavior remain unchanged.

P5 was explicitly accepted and approved for commit. P6 has not been started.

## DeepSeek Planner Provider delivered

- Added `PLANNER_PROVIDER=deepseek` without changing `standard|agent` workflow selection, the `mock` and `real` processing profiles, or the existing loopback-only `local_llm` Provider. The configured profile resolves DeepSeek through the same standard and Agent planning boundaries.
- Fixed the remote endpoint to the official `https://api.deepseek.com/chat/completions`; no environment variable, constructor parameter, upload field, or request data can override the host. `DEEPSEEK_MODEL` is a non-secret model selector and defaults to `deepseek-v4-flash`.
- The credential is read only from `DEEPSEEK_API_KEY` immediately before a request. It is not part of the `Settings` dataclass, Provider state, request JSON, model/planner identifiers, task data, metrics, or Agent Trace.
- Reused the existing structured planning prompt, schema, transcript grounding, and bounded repair flow. DeepSeek requests explicitly ask for a JSON object and standard planning still performs the independent trust-boundary validation before rendering.
- Added safe failure normalization: upstream request details and untrusted response bodies are discarded before raising application errors. Planner tool violations, persisted task failures, logs, formatted tracebacks, and `agent_trace.json` receive only bounded categories or fixed messages.
- Safe request failures retain only actionable categories such as `http_401`, `timeout`, `proxy_error`, or `client_unicodeencodeerror`; response bodies, URLs, headers, exception messages, and credentials remain excluded. This diagnosed a malformed PowerShell-session key without exposing its value.
- Updated the bilingual upload privacy note and README to disclose that selecting a configured remote planner sends corrected transcript data and, for Agent tasks, the optional director instruction and repair violations to DeepSeek.
- Corrected the Chinese locale override to use the existing `zh-CN` key. A regression test now prevents an invalid locale property from stopping navigation and click-handler initialization.

## DeepSeek verification

- Targeted provider/local-LLM/Agent regression suite: `20 passed in 7.83s`.
- Final full Python suite: `134 passed in 82.35s`, including real FFmpeg/Remotion standard Mock and Agent Mock end-to-end pipelines.
- Eight DeepSeek tests are fully offline: the HTTP call is mocked and they cover the fixed official endpoint, `DEEPSEEK_API_KEY` exclusivity, missing-key no-network behavior, safe HTTP/transport/client error categories, JSON request/response handling, existing profile compatibility, Agent repair metadata, and absence of a sentinel secret from Provider/Settings state, request JSON, exceptions, formatted traceback, logs, typed tool output, and Agent Trace.
- Frontend syntax validation passed; the 12-test frontend suite includes the locale-key/navigation regression.
- Standard `npm.cmd run build` reached the already documented Windows lock on `animation-renderer/build` (`EPERM`). The equivalent isolated bundle command completed successfully at `storage/renderer_build_validation_deepseek_commit` without deleting or overwriting the locked directory.
- A minimal authenticated request and the complete structured Planner request both returned HTTP 200 against the fixed official endpoint. Configured DeepSeek planning then completed a real 94.36-second standard task and produced a verified 17.7 MB result; no credential was printed or persisted.

## DeepSeek known limitations

- DeepSeek transport and one end-to-end configured task were live-tested, but semantic quality across real ASR transcripts, latency distributions, quota behavior, and model comparisons remain unevaluated. Runtime use requires network access and a valid account key.
- Selecting DeepSeek changes the semantic-planning privacy boundary from local to remote. Video/audio/rendering remain local, but corrected transcript and optional Agent direction are sent to DeepSeek as documented.

## P4 delivered

- Extended the existing semantic-video upload settings rather than adding a home card or redesigning the site. `workflow_mode` defaults to `standard`; selecting `agent` reveals the optional 2,000-character director instruction and `never|on_risk|always` approval policy. Standard submits do not send either Agent-only field.
- Preserved the existing standard progress UI and behavior. Agent tasks hide its estimated percentage and four broad stages, then render `upload_probe → audio_asr → correction → planning → validation → render → quality → complete` from real `agent_node` SSE payloads, including started, resumed, completed, failed, checkpoint version, and safe error-category state.
- Added a durable approval panel driven by `GET /approval`. It shows structured reason codes and the server-owned candidate plan, then calls the existing approve/edit/reject endpoints. Edit parses JSON locally for immediate feedback, while authoritative schema, transcript grounding, planning rules, and renderer safe-area validation remain on the server.
- Added a completed-result Agent Trace tab backed by `GET /agent-trace`. It exposes privacy-safe planner identity, retry count, node/tool status, durations, and structured violation codes without rendering transcript/director content, plan bodies, absolute paths, raw exceptions, or chain of thought.
- Added refresh/restore handling for `awaiting_approval`, `rejected`, active, and completed Agent tasks. Terminal Agent task event history is replayed through the existing SSE endpoint so a refreshed result reconstructs real node states rather than a fabricated progress snapshot.
- Preserved bilingual translation parity, keyboard-accessible tabs and buttons, visible alert/status regions, reduced-motion behavior, and mobile stacking for node and approval controls.

## P4 verification

- Modification baseline: `D:\Projects\semantic-video-animation-agent\.conda\python.exe -m pytest -vv` → `122 passed in 100.24s`.
- Targeted frontend/workflow/approval/recovery tests: `D:\Projects\semantic-video-animation-agent\.conda\python.exe -m pytest -vv tests\test_frontend_i18n.py tests\test_workflow_mode_api.py tests\test_agent_approval.py tests\test_agent_workflow.py` → `29 passed in 11.24s`.
- Final full suite: `D:\Projects\semantic-video-animation-agent\.conda\python.exe -m pytest -vv` → `125 passed in 82.74s`, including both real FFmpeg/Remotion standard Mock and Agent Mock end-to-end pipelines.
- Live local API/UI-contract task `6a441123-c948-495d-89b5-0ba057db98e2` used `agent + mock + approval_policy=always` with a director instruction. It paused durably at approval after validation, returned the candidate plan and redacted Trace, accepted one approval, emitted one `resumed` event, then executed only render/quality/complete and produced a verified 4.0 s 360×640 result (82,006 bytes). Its event history contains all eight node completions and no repeated ASR/planning after approval.
- The result preview returned HTTP `206 Partial Content`, `Content-Disposition: inline`, and a 32-byte requested range, confirming the existing stable preview contract.
- `node.exe --check frontend\app.js` passed. P4 changes no TypeScript, Remotion source, renderer contract, or `AnimationPlan` schema, so the renderer build was not required by the stage verification rule.
- The Browser skill could not start because the desktop runtime rejected its installed internal Browser service path as outside the configured trusted code path. No alternate browser automation was used; interactive viewport/click validation remains a manual acceptance item.

## P4 known limitations

- Browser-driven clicking and computed 390 px overflow measurement were not completed in this window because the required Browser skill failed its runtime trust-path bootstrap. Static responsive/accessibility tests pass, but desktop and mobile visual QA still needs the manual acceptance below.
- Agent node status is deliberately event/checkpoint state, not a percentage or ETA. The Agent Trace currently has detailed tool/model calls for planning and validation; other nodes expose their real lifecycle through task SSE rather than inventing per-node internals.
- Director instructions are interpreted only by the configured loopback local-LLM planner. Mock/rule planning remains deterministic and carries the instruction without claiming semantic interpretation.
- The current single-process recovery and execution guarantees remain unchanged; distributed workers and cross-process leases are P10 scope.

## Recommended P4 manual acceptance

1. Start FastAPI with the documented `.conda` interpreter, open `#/tools/semantic-video`, and confirm `standard` is selected by default; upload a short Mock/local-original task and verify the original four-stage progress, result preview, download, and advanced review still work.
2. Start a new task, choose `agent`, confirm the director and approval controls appear, then select Mock processing, Mock media, `always`, enter a short instruction, and upload. Verify the percentage disappears and the eight node cards advance only when SSE node events arrive.
3. At `awaiting_approval`, refresh the page. Confirm the same task, completed node states, structured reasons, candidate plan, and approve/edit/reject buttons return. Submit invalid JSON or an invalid plan with Edit and verify the panel remains actionable with an error.
4. Approve a valid plan. Verify the approval panel closes, `render` reports resumed/running, the task completes, and the result includes the Agent Trace tab with retry count, planner, durations, and no transcript/director text or absolute paths.
5. Create another `always` Agent task and reject it. Verify the task shows the rejected terminal state, produces no download, and a repeated decision is not accepted.
6. Repeat the upload/approval/result checks in Chinese and English at desktop width and around 390 px. Confirm keyboard tab navigation works, focus is visible, reduced-motion remains honored, and the page has no horizontal overflow.

P4 was explicitly accepted for commit after the verification above. P5 has not been started.

- Current branch: `master`
- Current commit before this stage: `79e4aec 实现导演指令与计划自动修复`
- Current stage: P3, Human-in-the-loop approval and resume - completed after user acceptance.

## P3 delivered

- Added Agent-only `approval_policy=never|on_risk|always`, defaulting to `never`. Standard uploads ignore the field and preserve the original dispatcher/API behavior.
- Added durable `awaiting_approval` and `rejected` task states plus a one-row-per-task `agent_approvals` audit record through Alembic migration `0004_agent_approval`.
- The explicit persistent graph now pauses after validation for `always`, for `on_risk` external-media relevance/source-rights review, and when bounded plan repair is exhausted. The checkpoint remains at `render`, so approval never repeats ASR, correction, planning, or validation.
- Added `GET /api/videos/{task_id}/approval` and atomic approve/edit/reject APIs. Approval revalidates the stored plan; edit must pass the Pydantic `AnimationPlan` schema, existing transcript-grounded planning rules, and deterministic renderer safe-area validation before the decision is consumed; invalid edits leave the approval pending.
- Approval decisions use a conditional database update, so duplicate or concurrent decisions have exactly one winner. The persisted decision is recoverable if FastAPI stops before a resume runner starts.
- Approve/edit resumes at `render`; reject becomes an auditable terminal state; pending approval can still use the existing cancellation API. Ordinary transcript editing is blocked while approval is pending so it cannot bypass the checkpoint contract.
- Added true SSE/task events for `awaiting_approval`, `approved`, `edited`, `rejected`, and `resumed`. Agent Trace records the structured decision and non-terminal `awaiting_approval` status without storing internal reasoning or absolute paths.

## P3 verification

- Baseline before implementation: `D:\Projects\semantic-video-animation-agent\.conda\python.exe -m pytest -vv` → `114 passed in 77.55s`.
- Final targeted P3/Agent/API/database/safe-area tests: `D:\Projects\semantic-video-animation-agent\.conda\python.exe -m pytest -q tests\test_agent_approval.py tests\test_agent_plan_repair.py tests\test_agent_workflow.py tests\test_workflow_mode_api.py tests\test_task_database.py tests\test_quality.py` → `30 passed in 13.86s`.
- Final full suite after manual-acceptance hardening: `D:\Projects\semantic-video-animation-agent\.conda\python.exe -m pytest -vv` → `122 passed in 82.36s`, including the existing standard and Agent Mock FFmpeg/Remotion end-to-end renders.
- A live API acceptance task `671c5354-1e23-4176-bc88-7ef2fe6cbce9` paused under `approval_policy=always`, returned a durable pending approval, resumed after approve, completed with each graph node exactly once, and produced a verified 4.0 s, 360×640 H.264/AAC result (83,234 bytes). Repeated approve returned HTTP 409.
- Live API checks also confirmed a planning-rule-invalid edit returns HTTP 422 and remains pending, reject becomes terminal with download HTTP 404, and standard mode completes while ignoring `approval_policy=always`.
- Manual testing exposed an approval-boundary gap: a schema/rule-valid edit could still violate the renderer safe area and fail at render. The API now runs the existing `validate_animation_safe_areas` before consuming approve/edit; live retest task `60a94d7e-0d39-4726-beff-c409d2e76f48` returned HTTP 422, remained pending at decision version 0, and never entered render.
- `D:\Projects\semantic-video-animation-agent\.conda\python.exe -m alembic heads` → single head `0004_agent_approval`.
- Renderer build was not required: P3 changes no TypeScript, Remotion source, renderer contract, or `AnimationPlan` schema.
- `git diff --check` passed. The user-owned untracked file `how 提交哈希` remains untouched.

## P3 known limitations

- P3 remains API-only by design. The existing page does not yet expose workflow/policy controls or an approval panel; that is exclusively P4 scope.
- `on_risk` currently treats enabled visuals under external-media profiles as requiring both relevance and source/rights review. It does not yet calculate a learned numeric relevance threshold because candidate acquisition occurs later in the render service; richer per-candidate risk scoring belongs with later retrieval/eval stages.
- Recovery and active-run mutual exclusion retain the current single-process local-runtime guarantee. Distributed leases, workers, and cross-process exactly-once execution remain P10 scope.
- No real local LLM, faster-whisper model, or external media service was exercised. Approval and recovery tests are fully offline with deterministic Fake/Scripted services.

## Recommended P3 manual acceptance

1. Run `D:\Projects\semantic-video-animation-agent\.conda\python.exe -m alembic upgrade head`, start FastAPI, and upload a short MP4 with `workflow_mode=agent`, `processing_profile=mock`, `media_provider=mock`, and `approval_policy=always`.
2. Poll `GET /api/videos/{task_id}` until `status=awaiting_approval`; open `GET /api/videos/{task_id}/approval` and confirm `policy=always`, `status=pending`, reason `policy_always`, and a candidate plan.
3. Restart FastAPI while the task is paused. Confirm it stays `awaiting_approval`, then call `POST /api/videos/{task_id}/approval/approve`; verify the task resumes and completes, and the event stream contains `awaiting_approval`, `approved`, and `resumed` without a second ASR/planning completion event.
4. Create another `always` task and submit an invalid plan to `POST /api/videos/{task_id}/approval/edit`; expect HTTP 422 and a still-pending approval. Submit a valid grounded plan; expect HTTP 202 and completion from render.
5. Create a third `always` task, call `/approval/reject`, and verify terminal `status=rejected`, no result render, a `rejected` event, and HTTP 409 from a repeated approve/edit/reject decision.
6. Upload with `workflow_mode=standard` while supplying `approval_policy=always`; verify the standard task does not pause and its public `approval_policy` remains `null`.

P3 was explicitly accepted for commit. P4 has not been started.

- Current branch: `master`
- Current commit before this stage: `c0108ba 实现可恢复 Agent 工作流基础`
- Current stage: P2, director instruction, typed tools, and plan auto-repair - completed after user acceptance.

## P2 delivered

- Added the optional Agent-only multipart field `director_instruction`, trimmed and bounded to 2,000 characters. It is persisted in SQLite and the recoverable Agent checkpoint; standard uploads discard it and retain the original dispatcher signature and behavior.
- Added Pydantic typed planning and validation tool envelopes. Planner candidates must first pass `AnimationPlan` schema validation and then the existing transcript-grounded `planning_rules` before render.
- Added bounded automatic repair: structured schema/rule violations are returned to the planner for at most two repair calls. A valid repair continues to render; exhaustion stops with `plan_repair_exhausted`, retry count, and violation codes rather than looping.
- Extended the loopback local-LLM prompt with optional director instructions and structured repair violations while preserving the original `plan()` API for standard workflows. Offline Mock/rule planners remain deterministic; they carry the instruction in Agent state but do not claim to interpret free-form direction.
- Added task-local atomic `agent_trace.json` plus `GET /api/videos/{task_id}/agent-trace`. The trace records tool/model call type, node, status, durations, structured violations, retries, `prompt_version`, plan schema version, planner ID, and model ID. It stores only counts/lengths for transcript and director input and excludes their text, plan bodies, absolute paths, media data, and raw exception messages.
- Added Alembic migration `0003_agent_director_instruction`; P1 checkpoint schema version 1 remains readable and is upgraded in memory when resumed.

## P2 verification

- Baseline before implementation: `D:\Projects\semantic-video-animation-agent\.conda\python.exe -m pytest -vv` → `108 passed in 74.01s`.
- Final targeted P2/Agent/API/migration/provider tests: `D:\Projects\semantic-video-animation-agent\.conda\python.exe -m pytest -vv tests\test_agent_plan_repair.py tests\test_agent_workflow.py tests\test_workflow_mode_api.py tests\test_local_llm_planner.py tests\test_task_database.py` → `24 passed in 8.34s`.
- Final full suite: `D:\Projects\semantic-video-animation-agent\.conda\python.exe -m pytest -vv` → `114 passed in 75.97s`, including the standard and Agent Mock FFmpeg/Remotion end-to-end pipelines.
- Alembic reports the single head `0003_agent_director_instruction`.
- Renderer build was not required: P2 changes no TypeScript, Remotion source, renderer contract, or `AnimationPlan` schema.
- `git diff --check` is part of the final verification. The user-owned untracked file `how 提交哈希` remains untouched.

## P2 known limitations

- The deterministic Mock and rule-based planners cannot semantically interpret arbitrary natural-language director instructions. The instruction remains persisted/auditable Agent input, while actual free-form interpretation requires the supported loopback local-LLM provider or a scripted test planner.
- No real local LLM, faster-whisper model, or external media service is exercised by P2 automated tests. Repair behavior is covered fully offline with Scripted/Fake planners.
- Agent Trace is task-local JSON with atomic replacement for the current single-process runtime. Cross-process trace append coordination and distributed execution remain P10 concerns.

## Recommended P2 manual acceptance

1. Run `D:\Projects\semantic-video-animation-agent\.conda\python.exe -m alembic upgrade head`, start FastAPI, and upload a short MP4 with `workflow_mode=standard`, Mock processing/media, plus an intentionally supplied `director_instruction`; verify the standard task completes and `director_instruction` is `null` in `GET /api/videos/{task_id}`.
2. Upload the same file with `workflow_mode=agent`, Mock processing/media, and a short `director_instruction`; verify the task completes, the instruction is returned only for this Agent task, and the existing result downloads/plays.
3. Open `GET /api/videos/{task_id}/agent-trace`; verify `prompt_version`, `plan_schema_version`, planner identity, tool-call entries, and retry count are present, while the instruction text, transcript text, plan body, and absolute paths are absent.
4. Submit an Agent upload with more than 2,000 instruction characters; verify HTTP 422 and that no task directory/row is created. Submit the same oversized field in standard mode; verify it is ignored and the stable standard flow still starts.
5. Run `D:\Projects\semantic-video-animation-agent\.conda\python.exe -m pytest -vv tests\test_agent_plan_repair.py`; inspect the two scripted cases: invalid-first/valid-second completes with one retry, while persistent rule violations stop after exactly two repairs without rendering.

P2 was explicitly accepted for commit. At that acceptance point, P3 had not been started.

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

P1 was explicitly accepted and committed before P2 began.

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
