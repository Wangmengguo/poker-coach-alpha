.PHONY: help install run test lint format check ci clean

PY ?= python3
VENV ?= .venv
PIP := $(VENV)/bin/pip
PYBIN := $(VENV)/bin/python

help:
	@echo "Common tasks:"
	@echo "  make install   # create venv and install deps (incl. dev)"
	@echo "  make run       # start uvicorn with reload"
	@echo "  make test      # run pytest"
	@echo "  make lint      # ruff check"
	@echo "  make format    # black format + ruff import sort"
	@echo "  make check     # black --check + ruff"
	@echo "  make ci        # lint+test (for CI)"

$(VENV):
	$(PY) -m venv $(VENV)

install: $(VENV)
	. $(VENV)/bin/activate && $(PIP) install -r requirements.txt
	. $(VENV)/bin/activate && $(PIP) install -U pytest ruff black

run: $(VENV)
	. $(VENV)/bin/activate && uvicorn app.main:app --reload

test: $(VENV)
	. $(VENV)/bin/activate && pytest -q

lint: $(VENV)
	. $(VENV)/bin/activate && ruff check .

format: $(VENV)
	. $(VENV)/bin/activate && ruff check . --select I --fix
	. $(VENV)/bin/activate && black .

check: $(VENV)
	. $(VENV)/bin/activate && black --check .
	. $(VENV)/bin/activate && ruff check .

ci: check test

clean:
	rm -rf $(VENV)

