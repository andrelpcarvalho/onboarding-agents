"""Entrypoint do Tutor para `adk web agents` / `adk run agents/tutor`.

O `adk web` carrega `app` (com os plugins de guardrail) antes de `root_agent`.
"""

from google.adk.apps import App

from onboarding_core.agents import build_tutor
from onboarding_core.guardrails import default_plugins

root_agent = build_tutor()
app = App(name="tutor", root_agent=root_agent, plugins=default_plugins())
