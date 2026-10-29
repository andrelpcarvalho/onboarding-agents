PY := .venv/bin/python
ADK := .venv/bin/adk
SERVICES := --session_service_uri sqlite:///.adk/sessions.db --memory_service_uri sqlite:///.adk/memory.db

.PHONY: setup test lint web chat curate approve gaps backup check new-role inbox buddy eval eval-stable eval-trajectory eval-behavior eval-report eval-history

setup:
	python3.11 -m venv .venv
	$(PY) -m pip install -U pip
	$(PY) -m pip install -e ".[dev]"
	$(PY) -m spacy download pt_core_news_sm
	@test -f .env || cp .env.example .env

test:
	.venv/bin/pytest -q

lint:
	.venv/bin/ruff check src scripts tests agents

web:
	$(ADK) web agents $(SERVICES)

chat:
	$(PY) scripts/chat.py --user $(USER_ID)

curate:
	$(PY) scripts/curate_role.py $(ROLE)

approve:
	$(PY) scripts/approve.py list

gaps:
	$(PY) scripts/approve.py gaps

backup:
	$(PY) scripts/backup.py

check:
	$(PY) scripts/check_content.py

new-role:
	$(PY) scripts/new_role.py $(ID) "$(TITLE)" $(if $(FROM),--from $(FROM),)

inbox:
	$(PY) scripts/inbox.py $(ARGS)

buddy:
	$(PY) scripts/buddy.py $(ARGS)

# ---- evals (chamam o modelo de verdade: custam alguns centavos e levam alguns minutos)
EVAL_ENV := ONBOARDING_CATALOG_DB=evals/.fixture/catalog.db ONBOARDING_SESSIONS_DB=evals/.fixture/sessions.db ONBOARDING_MEMORY_DB=evals/.fixture/memory.db ONBOARDING_QUIZ_SEED=7

eval-fixture:
	$(EVAL_ENV) $(PY) evals/fixture.py

# `adk eval` sai com código 0 mesmo com casos reprovados: o grep final transforma
# "Tests failed: N>0" em erro, para o make (e um CI) falhar de verdade.
eval-trajectory: eval-fixture
	@mkdir -p evals/.fixture
	$(EVAL_ENV) $(ADK) eval agents/tutor evals/tutor_trajectory.evalset.json --config_file_path evals/trajectory_config.json $(EVAL_FLAGS) 2>&1 | tee evals/.fixture/trajectory.log | grep -A3 "Eval Run Summary"
	@! grep -q "Tests failed: [1-9]" evals/.fixture/trajectory.log

eval-behavior: eval-fixture
	@mkdir -p evals/.fixture
	$(EVAL_ENV) $(ADK) eval agents/tutor evals/tutor_behavior.evalset.json --config_file_path evals/behavior_config.json $(EVAL_FLAGS) 2>&1 | tee evals/.fixture/behavior.log | grep -A3 "Eval Run Summary"
	@! grep -q "Tests failed: [1-9]" evals/.fixture/behavior.log

eval-report:
	$(PY) evals/report.py

eval-history:
	$(PY) evals/report.py --history

# Roda os dois conjuntos mesmo se o primeiro falhar (antes, uma falha de trajetória
# impedia o de comportamento e o eval-report mostrava o resultado ANTIGO dele).
eval:
	@$(MAKE) --no-print-directory eval-trajectory; t=$$?; \
	$(MAKE) --no-print-directory eval-behavior; b=$$?; \
	$(PY) evals/report.py; exit $$(( t || b ))

# Duas rodadas seguidas: critério de estabilidade antes de abrir PR que mexe no prompt.
eval-stable:
	@$(MAKE) --no-print-directory eval; r1=$$?; echo '--- 2ª rodada ---'; \
	$(MAKE) --no-print-directory eval; r2=$$?; exit $$(( r1 || r2 ))
