PY := .venv/bin/python

.PHONY: setup test lint check chat curate approve gaps inbox buddy backup studio eval

setup:
	python3.11 -m venv .venv
	$(PY) -m pip install -U pip
	$(PY) -m pip install -e ".[dev]"
	$(PY) -m spacy download pt_core_news_sm
	@test -f .env || cp .env.example .env

test:
	.venv/bin/pytest -q

lint:
	.venv/bin/ruff check src scripts tests evals

check:
	$(PY) scripts/check_content.py

chat:
	$(PY) scripts/chat.py --user $(USER_ID)

curate:
	$(PY) scripts/curate_role.py $(ROLE)

approve:
	$(PY) scripts/approve.py list

gaps:
	$(PY) scripts/approve.py gaps

inbox:
	$(PY) scripts/inbox.py

buddy:
	$(PY) scripts/buddy.py $(ARGS)

backup:
	$(PY) scripts/backup.py

# LangGraph Studio (equivalente ao `adk web`); requer: pip install -e ".[studio]"
studio:
	.venv/bin/langgraph dev

# Evals com o modelo real (base de teste própria em evals/.fixture/)
eval:
	ONBOARDING_CATALOG_DB=evals/.fixture/catalog.db ONBOARDING_QUIZ_SEED=7 $(PY) evals/run_evals.py
