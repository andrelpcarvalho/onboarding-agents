---
titulo: Pipeline de deploy Salesforce
slug: pipeline_deploy
area_dona: CoE Salesforce
responsavel: coe.salesforce
versao: 1.0
vigente_ate: 2027-06-30
tipo: referencia
status: aprovado
simulado: true
papeis: [dev_salesforce, analista_negocios]
sistemas: [GitHub Actions, Salesforce]
---

# Pipeline de deploy Salesforce (SIMULAÇÃO — conteúdo fictício para a PoC do curso)

## Modelo de release branch
O desenvolvimento acontece em branches feature/*. Ao fim da sprint é criada uma
branch release/* a partir da main; as features aprovadas são mergeadas nela.
Todo PR roda o workflow de validação (ci-validate) com testes Apex.

## Deploy em UAT
O merge na release dispara o deploy automático em UAT. A homologação com a área de
negócio acontece em UAT e é conduzida pelo analista de negócios.

## GMUD
Toda ida para produção exige uma GMUD (gestão de mudança) aprovada. O workflow
gmud-gate bloqueia o deploy em PRD enquanto a GMUD não estiver aprovada. O analista
de negócios anexa a evidência de homologação na GMUD.

## Deploy em produção e rollback
Com a GMUD aprovada, o deploy-prd publica a release em produção. Depois desse deploy
em produção, as branches que ainda estão abertas recebem um aviso para fazer rebase.
Se houver problema em produção, o workflow rollback-prd reimplanta a última release
estável.
