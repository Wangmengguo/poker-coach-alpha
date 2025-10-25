# Repository Guidelines

## Project Structure & Module Organization
- `app/` — FastAPI app (REST + WebSocket entrypoint `app.main:app`).
- `poker/` — table state, bots, and domain logic (`poker.table`).
- `ws/` — message/protocol schemas for WS payloads.
- `public/` — static client (`index.html`, `app.js`, `style.css`).
- `tests/` — lightweight tests (pytest‑style).
- `PLAN.md` — roadmap; `requirements.txt` — runtime deps; `.venv` — local env.

## Build, Test, and Development Commands
- Create venv: `python -m venv .venv && source .venv/bin/activate`.
- Install deps: `pip install -r requirements.txt`.
- Dev tools (optional): `pip install -U pytest ruff black`.
- Run server (reload): `uvicorn app.main:app --reload` then open `http://localhost:8000`.
- Run tests: `pytest -q`.
- Lint/format: `ruff check . && black .` (use `black --check .` in CI).

## Coding Style & Naming Conventions
- Python 3.10+, PEP 8, 4‑space indent; add type hints in new/changed code.
- Modules/files `snake_case.py`; classes `PascalCase`; functions/vars `snake_case`.
- Keep side effects at edges (FastAPI layer); keep poker logic pure/testable.
- Prefer `dataclasses`/Pydantic models at boundaries; validate WS payloads in `ws/`.

## Testing Guidelines
- Framework: `pytest`; place tests in `tests/` named `test_*.py`.
- Fast unit tests first; avoid external I/O. Target 80%+ coverage for new modules.
- Use `fastapi.testclient.TestClient` for REST; JSON round‑trip for WS stubs.
- Example: `pytest -q` or a single test `pytest tests/test_smoke.py -q`.

## Commit & Pull Request Guidelines
- Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`, `test:`.
- Imperative, present‑tense subject; ~72‑char limit; reference issues (`Fixes #123`).
- One focused change per PR; include description and any `public/` UI screenshots.
- Before opening: `pytest -q && ruff check . && black --check .` should pass.

## Security & Configuration Tips
- CORS is permissive for local dev; restrict `allow_origins` before deploying.
- Never commit secrets; use environment variables and keep `.env` out of git.
- In production, serve `public/` via CDN/proxy and terminate TLS at the edge.

