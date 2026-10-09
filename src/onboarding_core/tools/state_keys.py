"""Chaves de estado da sessão.

Prefixo `user:` => persiste entre sessões do mesmo user_id (é a "memória de
progresso" do colaborador). Prefixo `temp:` => vale só para a invocação atual.
"""

ROLE_ID = "user:role_id"
PROGRESS = "user:progress"  # dict[module_id, ModuleProgress.model_dump()]
CURRENT_MODULE = "user:current_module"
QUIZ = "user:quiz"  # quiz em andamento (inclui gabarito: nunca devolver ao modelo)
MATERIAL_LOADED = "user:material_loaded"  # módulo cujo material já foi carregado (pré-requisito do quiz)
