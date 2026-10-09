"""Resume os últimos resultados do `adk eval`: o que falhou e por quê.

Uso:
    python evals/report.py      # ou: make eval-report
"""

from __future__ import annotations

import json
from pathlib import Path

HISTORY = Path(__file__).resolve().parents[1] / "agents" / "tutor" / ".adk" / "eval_history"


def _tool_calls(invocation: dict) -> list[str]:
    """Chamadas de tool de uma invocação (o ADK grava em dois formatos)."""
    data = invocation.get("intermediate_data") or {}
    calls = [f"{t['name']}({t.get('args') or {}})" for t in data.get("tool_uses") or []]
    for ev in data.get("invocation_events") or []:
        for part in (ev.get("content") or {}).get("parts") or []:
            if fc := part.get("function_call"):
                calls.append(f"{fc['name']}({fc.get('args') or {}})")
    return calls


def _text(invocation: dict) -> str:
    parts = (invocation.get("final_response") or {}).get("parts") or []
    return " ".join(p.get("text") or "" for p in parts).replace("\n", " ").strip()


def main() -> None:
    latest: dict[str, Path] = {}
    for f in sorted(HISTORY.glob("*.evalset_result.json"), key=lambda p: p.stat().st_mtime):
        latest[json.loads(f.read_text())["eval_set_id"]] = f  # o mais recente vence
    if not latest:
        print("nenhum resultado ainda; rode `make eval`")
        return
    for set_id, f in sorted(latest.items()):
        cases = json.loads(f.read_text()).get("eval_case_results", [])
        failed = [c for c in cases if c.get("final_eval_status") != 1]
        print(f"{set_id}: {len(cases) - len(failed)}/{len(cases)} passaram")
        for c in failed:
            print(f"  ✗ {c['eval_id']}")
            for n, inv in enumerate(c.get("eval_metric_result_per_invocation", []), 1):
                actual = inv.get("actual_invocation") or {}
                user = " ".join(p.get("text") or "" for p in actual["user_content"]["parts"])
                print(f"    turno {n}: {user[:80]!r}")
                print(f"      tools: {', '.join(_tool_calls(actual)) or '-'}")
                print(f"      resposta: {_text(actual)[:300]}")
                for mr in inv.get("eval_metric_results", []):
                    if mr.get("metric_name") == "tool_trajectory_avg_score" and (mr.get("score") or 0) < 1:
                        print("      trajetória diferente da esperada")
                    for rs in (mr.get("details") or {}).get("rubric_scores") or []:
                        if (rs.get("score") or 0) < 1:
                            print(f"      {rs.get('rubric_id')}: {(rs.get('rationale') or '')[:240]}")


if __name__ == "__main__":
    main()
