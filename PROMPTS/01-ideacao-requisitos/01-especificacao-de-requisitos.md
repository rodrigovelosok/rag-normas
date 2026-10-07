---
fase: 01-ideacao-requisitos
unidade_curso: "C04 — Unidade 2.1 (Seleção do mini-projeto)"
data: 2026-10-07
ferramenta: Claude Code
modelo: Claude Opus 5.5 (claude-opus-5-5)
autoria: prompt escrito e executado pela IA, sob direção e revisão de Rodrigo Kobayashi
artefato_gerado: docs/requisitos.md
---

# Prompt 01 — Especificação de requisitos do `rag-normas`

## Prompt (CO-STAR)

### C — Contexto

Projeto final do Laboratório Introdutório (C04) da especialização em Engenharia de Software com IA
Generativa (UFG). O produto escolhido, a partir da Tabela 2 do material da Unidade 2, é um **chatbot RAG**
(Retrieval-Augmented Generation) que responde perguntas sobre a **legislação federal de arrolamento de
bens e direitos**: IN RFB nº 2.091/2022 (texto consolidado) e Lei nº 9.532/1997, arts. 64 e 64-A.

Decisões já tomadas em sessão de planejamento:

- Execução 100% local: Python 3.14 sem framework de orquestração (sem LangChain), Ollama com `bge-m3`
  para embeddings e `qwen2.5:3b` para geração (modelo trocável).
- Fragmentação estrutural: um artigo da norma por fragmento, com seus parágrafos e incisos.
- Busca híbrida: similaridade vetorial + BM25, fundidas por Reciprocal Rank Fusion; índice em JSON.
- Interface de linha de comando na v1.0.
- Repositório público no GitHub; só textos normativos de domínio público, nenhum dado de contribuinte.
- Foco do curso na etapa de **testes**: testes unitários com o modelo simulado (mock) e um conjunto de
  avaliação com perguntas e artigo esperado.
- Prazo de ~30 h de trabalho, até 18/10/2026.

### O — Objetivo

Produzir a especificação de requisitos da versão 1.0: requisitos funcionais, requisitos não funcionais,
critérios de aceitação **verificáveis por teste automatizado** e o que fica explicitamente fora de escopo.
Cada critério de aceitação deve poder ser checado na Fase 4 (testes) sem julgamento subjetivo.

### S — Estilo

Documento Markdown em português. Requisitos numerados (`RF01`, `RNF01`, `CA01`) para permitir
rastreabilidade a partir de testes e commits. Frases curtas no padrão "O sistema deve…". Metas
numéricas onde houver medição. Sem jargão sem explicação.

### T — Tom

Técnico e objetivo, de especificação; sem linguagem promocional.

### A — Audiência

Dois leitores: (1) o próprio autor, programador iniciante em Python, que vai usar o
documento como guia durante a implementação; (2) o avaliador do curso, que lê o repositório para verificar
escopo e rastreabilidade.

### R — Resposta

Um arquivo `docs/requisitos.md` com as seções: visão do produto e usuário-alvo, requisitos funcionais,
requisitos não funcionais, regras de segurança da resposta (guardrails), critérios de aceitação com a meta
e a forma de verificar, fora de escopo, glossário curto. Ao final, uma tabela de rastreabilidade
requisito → critério de aceitação.

## Resultado

Gerado `docs/requisitos.md`: 10 requisitos funcionais, 7 não funcionais, 3 guardrails e 9 critérios de
aceitação com meta e forma de verificação. A IA acrescentou um requisito que não estava nas decisões do
planejamento, o **RF10 (verificação automática de citações)**: depois da geração, conferir se todo artigo
citado na resposta existe no índice. Esse requisito transforma o guardrail "sempre cita o artigo" num
critério testável. As metas numéricas dos critérios (≥ 80% de recuperação etc.) são estimativas iniciais,
a recalibrar com os primeiros dados da Fase 4.

## Revisão humana

- [x] As perguntas-exemplo da seção 1 refletem dúvidas reais do trabalho de arrolamento?
- [x] O corpus da v1 está completo (alguma norma alteradora além da IN RFB 2.122/2022)?
- [x] As metas dos critérios de aceitação são razoáveis?
- [x] Algo do "fora de escopo" deveria entrar na v1?

_Alterações feitas após a revisão:_ nenhuma. Especificação aprovada pelo autor sem mudanças em
07/10/2026. A conferência do texto consolidado da IN fica para a Fase 2.
