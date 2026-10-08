---
fase: 04-testes
modulo: eval/perguntas.json, eval/avaliar.py
unidade_curso: "C04 — Unidade 4 (Testes, refatoração e documentação)"
data: 2026-10-08
ferramenta: Claude Code
modelo: Claude Sonnet 5.5 (claude-sonnet-5-5)
autoria: prompt escrito e executado pela IA, sob direção e revisão de Rodrigo Kobayashi
artefato_gerado: eval/perguntas.json, eval/avaliar.py, tests/test_avaliar.py
---

# Prompt 04.1 — Conjunto de avaliação e script `avaliar.py`

## Prompt (CO-STAR)

### C — Contexto

Projeto `rag-normas` com núcleo completo (150 testes unitários, todos com modelo simulado). Os testes unitários
provam que o código está certo, mas não dizem se o **sistema** responde bem: o teste com o Ollama real já mostrou
respostas com citação correta e conteúdo errado ou incompleto (`qwen2.5:3b`). A Fase 4 é o foco da ementa
(testes) e exige: conjunto de avaliação com gabarito, métricas (RF09; CA03 a CA05, CA08, CA09), calibração do
limiar de recusa (provisório em 0,52), do `k` e do `k` do RRF, e comparação 3b × 7b.

Medições da máquina (CPU, sem GPU, 16 GB com ~3 GB livres): 3b responde em 16 a 21 s; 7b leva ~3,5 min por
pergunta com `k = 4` (a leitura do prompt, ~3.000 tokens, é o gargalo). A recuperação (busca) não usa o modelo de
chat, então pode ser avaliada e calibrada sem as chamadas lentas.

O conjunto de 21 perguntas foi montado com o autor (16 dentro do corpus, em 4 grupos: fatos pontuais, listas,
combinações de normas e perguntas difíceis; mais 5 fora do corpus), em `eval/perguntas.json`. Cada pergunta traz: artigos esperados e itens que a resposta deve conter
(expressões regulares sem acento, qualquer uma casa).

### O — Objetivo

Testes primeiro (`tests/test_avaliar.py`), depois `eval/avaliar.py`:

- carregar e **validar** o conjunto (ids únicos, grupos e tipos válidos, regex compiláveis, artigos esperados
  existentes no corpus);
- métricas por pergunta: recuperação (fração dos artigos esperados entre os *k* recuperados), citação (fração dos
  esperados citados), conteúdo (fração dos itens presentes, ignorando o que está dentro de `[Fonte: ...]`), citações
  inexistentes, recusa, similaridade máxima e tempo;
- comando `retrieval` (sem modelo de chat): taxa de recuperação por *k* e por grupo, e varredura do limiar de
  recusa (recusas indevidas × respostas indevidas), para calibrar;
- comando `answers --model M`: roda as perguntas com o chat, grava **uma linha JSON por pergunta, na hora**
  (`--resume` retoma uma rodada interrompida) e gera o relatório em Markdown por grupo;
- nenhum caminho absoluto nas saídas.

### S — Estilo

Python 3.14, PEP 8, *type hints*, *docstrings* no formato Google, identificadores em inglês, textos em português.
Só biblioteca padrão. Funções puras testáveis; o relógio e as funções `embed`/`chat` entram por parâmetro.

### T — Tom

Relatório objetivo, com números e sem adjetivos.

### A — Audiência

O autor (programador iniciante em Python) e o avaliador do mini-projeto, que lerá o relatório no repositório.

### R — Resposta

Dois arquivos novos (o script e os testes) e o conjunto de perguntas já gravado. Testes falham antes e passam
depois; depois, teste de mutação.

## Resultado

Gerados `eval/avaliar.py` e `tests/test_avaliar.py` (60 testes; 210 no total, em ~3 s) e gravado o conjunto
`eval/perguntas.json` (21 perguntas). Ciclo TDD: vermelho (módulo inexistente), verde na primeira execução.
**Teste de mutação:** 50 alterações propositais; na primeira rodada, 47 de 49 aplicadas foram detectadas. Os dois
sobreviventes viraram testes: a fronteira exata do limiar (`>=` contra `>` nas respostas indevidas) e o
`item_score` de pergunta sem itens. Um mutante não foi aplicado por erro no meu padrão de busca e foi refeito.
Pequena mudança no código existente: `generate._article_key` passou a ser pública (`article_key`), porque o avaliador
compara citações pelo artigo, do mesmo jeito que a verificação de citações.

**Primeira avaliação real, só da busca (`python -m eval.avaliar retrieval`, 21 perguntas, ~20 s, sem o chat):**

| k | Fatos | Listas | Combinação | Difíceis | Total |
|---:|---:|---:|---:|---:|---:|
| 4 | 100% | 80% | 50% | 100% | **84%** |
| 5 | 100% | 80% | 83% | 100% | **91%** |
| 8 | 100% | 100% | 83% | 100% | **97%** |

Com k = 4 faltam artigos esperados em três perguntas: Q01 (Decreto, art. 1º), Q04 (IN, art. 8º, artigo curto de
478 caracteres) e Q12 (pergunta informal sobre vender o imóvel: não recuperou o art. 12, que é o que responde).

**Limiar de recusa (varredura de 0,40 a 0,70):** o valor provisório 0,52 deixa passar uma das cinco perguntas fora
do corpus (Q20, a armadilha da penhora, com similaridade máxima 0,535). Não há erro algum entre **0,54 e 0,58**: a
pergunta recusável mais parecida com o corpus fica em 0,535 e a pergunta respondível menos parecida (Q12) em 0,584.
A folga é de apenas 0,05 e vem de 21 perguntas; o limiar de 0,56 (meio da faixa) é o candidato, a confirmar com mais
perguntas.

**Revisão do plano:** a calibração do limiar e a medição do k não precisam do modelo de chat, então rodam em
segundos; só a comparação 3b × 7b é demorada.

## Revisão humana

- [ ] As perguntas e os gabaritos (itens) refletem situações reais de uso?
- [ ] A definição de "resposta correta" (conteúdo completo + artigos citados + sem citação inexistente) é razoável?

_Alterações feitas após a revisão:_ (preencher)
