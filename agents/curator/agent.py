"""Entrypoint do Curador para `adk web agents` / `adk run agents/curator`."""

from onboarding_core.agents import build_curator

root_agent = build_curator()
