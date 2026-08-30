# Agent Guide

## Project goal

Build a local Chinese talking-head video semantic-animation pipeline. The current completed baseline is the phase-one Mock workflow; later phases add engineering services, local ASR, semantic planning, and additional templates.

## Layout

- `backend/app/`: FastAPI API, models, persistence, and processing services.
- `animation-renderer/`: React/TypeScript Remotion templates.
- `frontend/`: same-origin static upload UI.
- `tests/`: pytest unit, API, and end-to-end tests.
- `storage/`: ignored runtime task files and SQLite database.

## Commands (Windows)

- Test: `.\.conda\python.exe -m pytest -vv`
- Backend: `.\.conda\python.exe -m uvicorn backend.app.main:app --reload`
- Renderer build: `cd animation-renderer; npm.cmd run build`

## Standards and safety

- Use the project `.conda\python.exe`, `npm.cmd`, `npx.cmd`, `ffmpeg`, and `ffprobe`.
- Keep external commands as argument arrays with timeouts; never concatenate untrusted input or use `shell=True`.
- Keep task paths under `storage/`; do not modify files outside this repository.
- Preserve user changes; do not reset, clean, stash, commit, or push without explicit approval.

## Done definition

Run the relevant Python tests and renderer build, update planning/status documents, and report actual results without claiming unavailable local-model capabilities.
