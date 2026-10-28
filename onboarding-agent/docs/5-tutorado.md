# Guia do tutorado: seu onboarding com o Tutor

> **Em resumo:** converse com o Tutor usando sempre o mesmo login. Ele ensina os temas da sua
> função em partes curtas, faz um quiz de 3 perguntas por módulo e lembra onde você parou. Para
> assuntos pessoais, ele te conecta ao seu buddy.

Bem-vindo(a)! O **Tutor** é um assistente que conduz o seu onboarding. Ele mostra o que você
precisa aprender para a sua função, explica cada tema em partes curtas, faz perguntas rápidas para
checar o entendimento e **lembra onde você parou**. Para o que precisa de uma pessoa, ele te
conecta ao seu **buddy**.

> Isto é um **piloto**. O Tutor pode errar ou demorar. Sua opinião é o que vai melhorá-lo (seção 8).

---

## 1. Como acessar

Quem conduz o piloto vai te passar **uma** destas formas:

**Terminal:**

```bash
make chat USER_ID=seu.login
```

Digite e tecle Enter. Para sair, digite `sair`. Para voltar, rode o mesmo comando.

**Navegador:** um link como `http://<endereço>/dev-ui/?app=tutor&userId=seu.login`.
A tela tem detalhes técnicos na lateral (é uma tela de testes); converse pela caixa de mensagem.

**Use sempre o mesmo `seu.login`.** É por ele que o Tutor reconhece você, seu progresso e seu buddy.

---

## 2. Primeira conversa

1. Diga "oi". O Tutor mostra a trilha do seu papel, que é definida pelo responsável do onboarding.
   Se ele disser que você ainda não tem papel, peça ao responsável ou ao seu buddy.
2. Diga "vamos começar". Ele abre o primeiro módulo.

---

## 3. Como funciona um módulo

```
 abre o módulo ─▶ explica em partes curtas ─▶ "ficou claro?" ─▶ ... ─▶ quiz (3 perguntas) ─▶ nota
```

- **Partes curtas:** depois de cada parte, responda "sim", peça um exemplo ou faça uma pergunta.
- **Fontes:** quando fala de processo da empresa, o Tutor mostra de onde tirou, como
  `[pipeline_deploy.md#GMUD]`.
- **"Rascunho não revisado":** o conteúdo ainda não foi revisado por uma pessoa. Use com cuidado
  e anote o que parecer errado.
- **Ordem:** alguns módulos dependem de outros; se você pedir para pular, ele indica o que vem antes.

---

## 4. O quiz

- São **3 perguntas de múltipla escolha**, uma de cada vez, sobre o conteúdo do módulo. As
  perguntas foram **revisadas por uma pessoa da equipe** e são sorteadas: numa nova tentativa,
  algumas podem mudar.
- **Responda só com a letra:** A, B, C ou D.
- O Tutor diz se você acertou, qual era a resposta certa e por quê.
- **A nota é calculada automaticamente pelo sistema.** Nem você nem o Tutor conseguem alterá-la.
- Não é prova: abaixo de 70% de acertos, ele sugere revisar o módulo depois. Vale a sua melhor nota.
- Se parar no meio, o quiz continua da mesma pergunta quando você voltar.

### Missões práticas

- Uma **missão** é um roteiro em sistemas reais de **homologação** (ex.: originar uma proposta
  no SITE e localizá-la no ACOM). O Tutor pede uma coisa por vez: descrever a tela, avisar quando
  avançou, informar o número da proposta.
- **O sistema confere cada resposta**, não o Tutor. A missão só fecha quando a evidência bate
  (ex.: o número da proposta no ACOM é o mesmo do SITE).
- Precisa de um CPF que passe? Peça ao Tutor: ele entrega um da massa de teste de homologação.
  Nunca use CPF real, senha ou print.
- Sem o acesso necessário, a missão fica **pausada** e volta do mesmo ponto quando o acesso sair.

---

## 5. Seu buddy

O buddy é um colega definido pela empresa para te acompanhar. O Tutor sabe quem é e te indica
quando for o caso.

**Quando o Tutor te encaminha ao buddy:** assuntos pessoais ou que precisam de uma pessoa, como
salário, férias, saúde, questões jurídicas, conflitos ou **acesso bloqueado** que te impede de
trabalhar.

**Como funciona:**
1. O Tutor não responde o assunto, diz quem é o seu buddy e como falar com ele.
2. Ele **pergunta** se pode registrar um pedido para o buddy. Só registra se você disser que sim,
   com um resumo curto, sem detalhes.
3. O buddy vê o pedido numa lista que consulta periodicamente (**não é instantâneo**). Para algo
   urgente, chame o buddy direto no contato indicado.

---

## 6. O que o Tutor lembra (e o que não)

**Lembra, mesmo se você fechar e voltar outro dia:**
- sua função, os módulos concluídos, as notas e onde você parou (inclusive no meio de um quiz);
- trechos das conversas anteriores (ex.: que você teve dúvida sobre um tema).

**Não lembra:**
- se você entrar com outro login;
- nada fora destas conversas: ele não acessa seu e-mail, agenda ou sistemas.

**Quem mais vê seu progresso:** o seu buddy (módulos concluídos, notas, último acesso e os seus
pedidos) e o responsável pelo piloto.

---

## 7. Frases úteis

| Você quer... | Diga algo como... |
|---|---|
| Saber onde parou | "Onde eu parei?" |
| Continuar | "Vamos continuar" |
| Revisar um tema | "Quero revisar segurança da informação" |
| Um exemplo | "Me dá um exemplo prático?" |
| Explicação mais simples | "Explica de um jeito mais simples" |
| Tirar dúvida sobre a empresa | "Quem aprova a GMUD?" |
| Falar com seu buddy | "Preciso falar com meu buddy sobre..." |

**O que ele não faz:**
- **Não inventa.** Se a resposta não está na base oficial, ele diz que não sabe e registra a
  pergunta para o time de conteúdo. Isso é esperado e ajuda o projeto.
- **Não trata assuntos pessoais:** encaminha ao buddy (seção 5).
- **Não substitui as pessoas:** é um apoio para o básico.

---

## 8. Privacidade e feedback

- As conversas e notas ficam **gravadas** para o Tutor lembrar do seu progresso, para o seu buddy
  te acompanhar e para avaliar o piloto.
- **Não escreva dados pessoais** (CPF, dados de clientes, senhas, saúde). Como proteção extra,
  CPF, CNPJ, telefone, e-mail e cartão são trocados automaticamente por marcadores (ex.: `<CPF>`)
  antes de qualquer coisa ser gravada.
- Você pode pedir ao responsável para ver ou apagar seus dados.

**Ao terminar, conte para quem conduz o piloto:**
- Ele lembrou corretamente onde você parou?
- As explicações tinham o tamanho certo?
- O quiz testou o que importava?
- Ele afirmou algo errado ou inventado? O quê?
- Que pergunta ele não soube responder?

---

## 9. Se algo der errado

| Aconteceu | O que fazer |
|---|---|
| Demorou muito | Respostas levam alguns segundos; quando ele prepara material novo, até 1 minuto. Se travar, feche e abra de novo: seu progresso fica salvo. |
| "O quiz deste módulo ainda não está disponível" | As perguntas ainda estão em revisão pela equipe. Siga para o próximo módulo e volte depois. |
| Ele não lembra de você | Confira se usou o mesmo login de antes |
| Ele não sabe quem é seu buddy | Avise o responsável: seu buddy ainda não foi cadastrado |
| Resposta estranha | Anote a pergunta e a resposta e avise o responsável |
| Mensagem de erro | Tire um print e avise o responsável |
