.PHONY: help install smoke quick run clean

help:
	@echo "Graylayer Fuzz — make targets"
	@echo "  install   create .venv and install requirements"
	@echo "  smoke     fast sanity check (no network)"
	@echo "  quick     run with 20 examples per op (fast)"
	@echo "  run       full run (default 75 examples per op)"
	@echo "  clean     remove results/ and caches"

install:
	python3 -m venv .venv
	./.venv/bin/pip install --upgrade pip
	./.venv/bin/pip install -r requirements.txt

smoke:
	python scripts/smoke.py

quick:
	./scripts/run_all.sh --quick

run:
	./scripts/run_all.sh

clean:
	rm -rf results .pytest_cache .hypothesis
	mkdir -p results
