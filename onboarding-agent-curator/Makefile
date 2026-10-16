PY := .venv/bin/python

.PHONY: setup test lint sample import web a2a

setup:
	python3.11 -m venv .venv
	$(PY) -m pip install -U pip
	$(PY) -m pip install -e ".[dev]"
	@test -f .env || cp .env.example .env

test:
	.venv/bin/pytest -q

lint:
	.venv/bin/ruff check src scripts tests agents

sample:
	$(PY) scripts/make_sample_pdf.py

# make import PDF=examples/manual-qa.pdf ROLE_ID=analista_qa ROLE_TITLE="Analista de QA"
import:
	$(PY) scripts/import_pdf.py $(PDF) --role-id $(ROLE_ID) --role-title "$(ROLE_TITLE)"

web:
	.venv/bin/adk web agents

a2a:
	$(PY) scripts/serve_a2a.py
