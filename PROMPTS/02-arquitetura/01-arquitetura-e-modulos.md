---
fase: 02-arquitetura
unidade_curso: "C04 — Unidade 2.2 (Arquitetura mínima: módulos, dependências, fluxo de dados)"
data: 2026-10-07
ferramenta: Claude Code
modelo: Claude Sonnet 5.5 (claude-sonnet-5-5)
autoria: prompt escrito e executado pela IA, sob direção e revisão de Rodrigo Kobayashi
artefato_gerado: docs/arquitetura.md
---

# Prompt 02 — Arquitetura mínima e módulos do `rag-normas`

## Prompt (CO-STAR)

### C — Contexto

Projeto `rag-normas` v1.0: chatbot RAG de linha de comando sobre a legislação de arrolamento de bens
(IN RFB 2.091/2022 consolidada, 27 artigos; Lei 9.532/1997, arts. 64 e 64-A). A especificação está em
`docs/requisitos.md` (RF01–RF10, RNF01–RNF07, G1–G3, CA01–CA09). Restrições já decididas:

- Python 3.14 sem framework de orquestração; única dependência de execução é a biblioteca `ollama`
  (0.6.3, verificada no Python 3.14); `pytest` só para desenvolvimento.
- Ollama local: `bge-m3` (embeddings de 1024 dimensões) e `qwen2.5:3b` (chat).
- O foco do curso é a etapa de **testes**: a arquitetura precisa permitir testar tudo sem Ollama.
- Medições feitas nesta máquina (CPU, 16 GB, sem GPU dedicada): primeira chamada de chat 16 s (carga do
  modelo), seguintes ~8 s com contexto curto; primeira chamada de embedding 6 s.
- O corpus é pequeno (tamanho do maior artigo: ~4.100 caracteres), então busca em memória basta.

### O — Objetivo

Projetar a arquitetura mínima da v1.0: módulos e responsabilidades, fluxo de dados dos comandos `index` e
`ask`, formato do índice em JSON, estratégia de injeção do modelo para permitir testes com mock, e uma lista
de decisões de projeto com a alternativa descartada e o motivo. Apontar as decisões que ficam em aberto.

### S — Estilo

Markdown em português. Diagramas em **Mermaid** (renderiza no GitHub). Nomes de módulos, funções e campos
em inglês, coerentes com o RNF05. Cada módulo com uma frase de responsabilidade única (princípio da
responsabilidade única) e a lista de requisitos que atende.

### T — Tom

Técnico, direto e didático: o leitor está aprendendo a projetar software.

### A — Audiência

O autor (programador iniciante em Python) e o avaliador do curso. Evitar abstrações que o autor não
consiga escrever e explicar sozinho.

### R — Resposta

Um arquivo `docs/arquitetura.md` com: visão geral e diagrama de componentes; tabela de módulos; diagrama de
sequência de `ask`; formato do índice; estratégia de testes; decisões de projeto; decisões em aberto.

## Resultado

Gerado `docs/arquitetura.md`: 7 módulos, 2 diagramas Mermaid, 8 decisões de projeto e 3 decisões em aberto.
Pontos em que a IA foi além do pedido ou corrigiu o planejamento:

- **Layout plano em vez de `src/`.** O plano de 07/10 previa `src/rag_normas/`; a IA trocou por
  `rag_normas/` na raiz porque `python -m rag_normas` funciona sem instalar o pacote, o que simplifica a
  instalação e o README para um iniciante.
- **Único módulo que fala com o Ollama** (`llm.py`). Embedding e chat entram nos outros módulos como funções
  recebidas por parâmetro (*injeção de dependência*), e é isso que permite testar sem Ollama (RNF03).
- **Formato de citação estruturado** `[Fonte: <norma>, art. N]`, para que a verificação do RF10 olhe só as
  citações do assistente e não confunda com artigos de outras leis que a norma menciona no próprio texto.
- **Aviso de risco encontrado ao reler o corpus:** a Lei 9.532, art. 64, § 7º, fala em R$ 500 mil, mas a IN
  2.091, art. 2º, II, usa R$ 2 milhões, porque o Decreto nº 7.573/2011 elevou o limite. O Decreto não está
  no corpus. Vira caso do conjunto de avaliação (ver decisões em aberto).

## Revisão humana

- [ ] Os módulos e o fluxo fazem sentido para quem vai implementar e explicar no fórum?
- [ ] A confusão R$ 500 mil × R$ 2 milhões está descrita corretamente? Convém incluir o Decreto 7.573/2011?
- [ ] O formato de citação `[Fonte: …, art. N]` é aceitável?
- [ ] Alguma decisão de projeto deveria ser outra?

_Alterações feitas após a revisão:_ (preencher)
