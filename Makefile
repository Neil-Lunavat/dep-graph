# Thin wrapper over run.py (the real entry point; `make` is not on every machine).
.PHONY: all test install

install:
	uv sync

all:
	uv run python run.py all

test:
	uv run --group dev pytest -q
