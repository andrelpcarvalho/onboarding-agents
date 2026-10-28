# SITE Solar e ACOM (EXEMPLO — substituir pelo manual oficial do time Solar)

## Pré-análise
A pré-análise é a primeira tela do simulador solar. Ela faz uma avaliação inicial dos
dados informados para saber se é possível seguir com a proposta. Se a pré-análise não
passar, o fluxo não avança para a simulação.

## Simulação
Na simulação o colaborador informa valor, prazo e condições do financiamento solar e o
sistema calcula as parcelas. A simulação ainda não cria proposta: ela só mostra as
condições para o cliente escolher.

## Dados da proposta
Nesta tela entram os dados do proponente. Ao confirmar, o SITE exibe o número da
proposta. A gravação da proposta nos sistemas de retaguarda é assíncrona: o número
aparece na hora, mas a proposta pode levar alguns minutos para ficar visível no ACOM.

## O que é o ACOM
O ACOM é o sistema de acompanhamento de propostas usado pela operação. Nele o operador
consulta propostas originadas nos canais, acompanha o status e trata pendências.

## Perfis do ACOM
Para consultar propostas do Solar é preciso o perfil de operador solar. O perfil
logado aparece no topo da tela inicial. Sem esse perfil, a consulta de propostas do
Solar não fica disponível e o acesso deve ser solicitado pelo canal de acessos do papel.

## Proposta não encontrada no ACOM
Se a proposta não aparecer na consulta por CPF, aguarde alguns minutos, porque a
gravação é assíncrona. Persistindo, confira nos logs da captura se a proposta foi
recebida e se houve erro de integração, conforme o manual de logs da captura.
