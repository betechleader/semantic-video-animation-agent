# Agent Eval Harness

This directory is an independent, fully offline planning evaluation suite. It does not read `storage/`, call a model, download media, or render video. The default dataset contains only self-authored Chinese transcript snippets.

Run it from the repository root:

```powershell
.\.conda\python.exe -m evals.agent.cli --output-dir storage\agent_evals\latest
```

The command writes `agent_eval_report.json` for automation and `agent_eval_report.md` for review. It exits with code `1` when any bound in `default_thresholds.json` fails.

## Structure

- `data/chinese_cases.json`: versioned, self-authored offline cases and deterministic repair scenarios.
- `harness.py`: loads typed cases, runs the same deterministic Mock planning Provider through standard and Agent boundaries, captures stable run/node/tool IDs, and aggregates metrics.
- `reporting.py`: applies min/max regression gates and renders JSON/Markdown reports.
- `cli.py`: command-line entry point with explicit dataset, threshold, and output-directory overrides.

## Metric definitions

- `animation_plan_schema_pass_rate`: share of runs whose final candidate parses as `AnimationPlan`.
- `transcript_grounding_precision`: share of animation triggers and semantic-segment texts found in the case transcript.
- `time_interval_valid_rate`: share of animation/semantic intervals inside transcript timing; animation durations must also meet planning limits.
- `overlap_violation_rate`: overlapping adjacent animation pairs divided by the number of evaluated animations.
- `tool_call_success_rate`: successful planning and validation boundaries divided by all such calls.
- `auto_repair_success_rate`: cases that became valid after a retry divided by cases that needed repair.
- `average_retry_count`: repair calls per run.
- `human_intervention_rate`: runs that exhaust repair and enter `awaiting_human` divided by all runs.
- `task_success_rate`: completed runs divided by all runs.
- `stage_latency_ms`: nearest-rank P50/P95 for planning and validation calls. Latency is observational and may vary; semantic outcomes and counts are deterministic.

The report deliberately excludes transcript text, absolute paths, user task content, model prompts, and internal reasoning. OpenTelemetry export is not enabled in P5; local JSON/Markdown remain the only default outputs.
