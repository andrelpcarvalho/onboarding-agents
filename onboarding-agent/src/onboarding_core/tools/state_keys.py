"""Chaves de estado da sessão.

Prefixo `user:` => persiste entre sessões do mesmo user_id (é a "memória de
progresso" do colaborador). Prefixo `temp:` => vale só para a invocação atual.
"""

ROLE_ID = "user:role_id"
PROGRESS = "user:progress"  # dict[module_id, ModuleProgress.model_dump()]
CURRENT_MODULE = "user:current_module"
QUIZ = "user:quiz"  # quiz em andamento (inclui gabarito: nunca devolver ao modelo)
MATERIAL_LOADED = "user:material_loaded"  # módulo cujo material já foi carregado (pré-requisito do quiz)
MISSIONS = "user:missions"  # dict[mission_id, progresso + evidências da missão]
ACTIVE_MISSION = "user:active_mission"  # id da missão em andamento (no máximo uma)
MISSION_CHECK = "temp:mission_check"  # conferência automática da mensagem atual (só nesta invocação)
PENDING_ESCALATION = "user:pending_escalation"  # pedido ao buddy aguardando o "sim" do colaborador
