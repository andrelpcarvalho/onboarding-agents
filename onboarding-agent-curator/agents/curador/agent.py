"""Entrypoint para `adk web agents`."""

from curator_agent.agent import build_agent

root_agent = build_agent()
