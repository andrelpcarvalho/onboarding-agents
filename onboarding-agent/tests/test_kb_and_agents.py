from google.adk.agents import LlmAgent, SequentialAgent

from onboarding_core.agents import build_curator, build_tutor
from onboarding_core.roles import load_roles
from onboarding_core.tools import search_sources


def test_kb_retorna_fonte_citavel():
    r = search_sources("o que é GMUD?")
    assert r["found"]
    assert r["results"][0]["source"].startswith("pipeline_deploy.md#")


def test_kb_tags_dos_papeis_tem_cobertura():
    """Toda tag de módulo deve achar algo na KB, senão o Curador não tem base."""
    for role in load_roles().values():
        for m in role.modules:
            assert search_sources(" ".join(m.kb_tags))["found"], (role.id, m.id)


def test_agentes_montam_sem_chamar_llm():
    tutor = build_tutor()
    curator = build_curator()
    assert isinstance(tutor, LlmAgent) and isinstance(curator, SequentialAgent)
    assert [a.name for a in curator.sub_agents] == [
        "syllabus_planner", "material_writer", "review_loop", "quiz_writer", "material_publisher"
    ]
