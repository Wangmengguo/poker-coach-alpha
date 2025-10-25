# Poker Coach Alpha

Simple, understandable scaffold for a Texas Hold’em MVP using FastAPI + WebSocket and pokerkit.

## Quickstart

- Python 3.10+

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://localhost:8000 to load the minimal client.

## Layout

- app/ — FastAPI app (REST + WebSocket)
- poker/ — pokerkit wrapper and bots
- ws/ — protocol schemas (messages, validation)
- public/ — static client (index.html, app.js, style.css)
- tests/ — basic tests
- PLAN.md — roadmap and technical plan

## Next

We will implement the TableService around pokerkit, bots, and the WS protocol per PLAN.md.