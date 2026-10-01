# Thin wrapper over run.py (the real entry point; `make` is not on every machine).
.PHONY: all test install check paper

install:
	uv sync

all:
	uv run python run.py all

test:
	uv run --group dev pytest -q

# every number and claim in the paper, against the result files
check:
	uv run python run.py checknums claims

paper:
	cd paper && tectonic paper.tex
