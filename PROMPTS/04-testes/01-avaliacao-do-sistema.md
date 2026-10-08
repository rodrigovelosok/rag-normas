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

**Calibração da constante do RRF:** a varredura (1 a 100) mostrou que o valor da literatura (60) é ruim para este
corpus: com 5, a recuperação em k = 4 vai de 84% para **97%** (só a Q01 ainda perde o Decreto). O limiar não muda: a
faixa sem erros segue em 0,54 a 0,58. Novos padrões do produto: `rrf_k = 5` e `min_similarity = 0,56` (meio da
faixa). Foram acrescentados `RAG_RRF_K` e `--rrf-k` (testes e mutação 17/17 nessa mudança). Cautela: a escolha foi
feita sobre as mesmas 21 perguntas, então pode estar otimista para perguntas novas.

**Rodadas completas com o `qwen2.5:3b` (21 perguntas, máquina ociosa, resultados em `eval/relatorios/`):**

| | Antes (RRF 60, limiar 0,52) | Depois (RRF 5, limiar 0,56) |
|---|---:|---:|
| Respostas corretas | 10 de 21 | **12 de 21** |
| Busca (artigos esperados recuperados) | 84% | **97%** |
| Citação (artigos esperados citados) | 77% | **86%** |
| Itens do gabarito presentes | 69% | **73%** |
| Respostas indevidas (fora do corpus) | 1 (Q20, penhora) | **0** |
| Recusas indevidas | 0 | 0 |
| Citações inexistentes | 0 | **0** |
| Tempo médio das respondidas | 89,8 s | 60,5 s |

Por grupo, no "depois": fatos pontuais 4 de 5, listas 3 de 5, combinações de normas 0 de 3, difíceis 0 de 3, fora do
corpus 5 de 5. O que sobra de erro é **conteúdo incompleto do modelo pequeno**: citações inexistentes nunca
ocorreram, e a busca já traz os artigos certos em 97% dos casos. Exemplos: Q01 (diz os dois valores mas não que são
cumulativos), Q06 (lista só parte das hipóteses de cancelamento), Q14 (cônjuge: omite a regra da união estável), Q15
(omite a responsabilidade subsidiária).

**Tempo:** a meta de 60 s (RNF04/CA08) ficou no limite (60,5 s) e a variação é enorme (7 a 106 s no "depois"). Parte
da variação é cache de prefixo do Ollama (perguntas seguidas que recuperam os mesmos artigos ficam rápidas). Além
disso, a velocidade da máquina caiu ao longo do dia: o mesmo prompt de 3.039 tokens levava ~16 s na noite anterior e
levou 94 s depois das rodadas (leitura do prompt: ~190 contra 45 tokens/s), com a máquina ociosa e a memória livre
baixa (2 a 4 GB). Os tempos devem ser lidos com essa ressalva; a causa (limitação de energia/temperatura ou pressão
de memória) não foi isolada.

**Experimento offline, teto de caracteres no contexto:** limitar o texto entregue ao modelo a 10.000 caracteres mantém
a recuperação em 97% (k = 4) e reduz o prompt médio em 17% (9.412 para 7.776 caracteres) e o máximo em 26%; tetos
menores (8.000 ou menos) perdem busca. Ganho modesto; não implementado por enquanto.

**Rodada completa com o `qwen2.5:7b` e comparação (CA09)** — mesmas 21 perguntas, configuração calibrada, máquina
ociosa; resultados em `eval/relatorios/comparacao.md`:

| | 3b antes | 3b depois | 7b depois |
|---|---:|---:|---:|
| Respostas corretas | 10 de 21 | 12 de 21 | 12 de 21 |
| Itens do gabarito presentes | 69% | 73% | 77% |
| Citações dos artigos esperados | 77% | 86% | 90% |
| Busca | 84% | 97% | 97% |
| Citações inexistentes | 0 | 0 | 0 |
| Tempo médio das respondidas | 89,8 s | 60,5 s | **161,6 s** |

O 7b acerta o mesmo número de perguntas, mas **não as mesmas**: acerta Q06 e Q12 (o 3b não), e erra Q02 e Q03 (o 3b
acerta). Ele é um pouco mais completo nas perguntas difíceis (65% dos itens contra 43%), mas **2,7 vezes mais
lento** e, nas listas, tende a resumir (nas Q02 e Q03 omitiu itens que o 3b trouxe). Hipótese, não testada: o pedido
"em poucas frases" do prompt pesa mais no 7b, que o obedece melhor. Conclusão provisória: o ganho de qualidade do 7b
não compensa o custo de tempo nesta máquina; o padrão continua sendo o 3b.

**Auditoria do gabarito (lição desta etapa).** Li todas as respostas em que algum item foi marcado como ausente: de
todos os itens, 4 eram falhas das minhas expressões regulares, todas no 7b (ele escreveu "extintos" e "garantidos", e
"ambos assinem" e "não precisa atingir os limites", e o gabarito só reconhecia "extinção", "garantia da execução",
"assinad…" e "enquadr…"). Corrigi o gabarito e criei o comando `rescore`, que reavalia respostas já gravadas sem
rodar o modelo de novo; reavaliei as três rodadas. Sem a auditoria, a métrica "Itens" subestimaria o 7b. Teste de
mutação do `rescore` e do `compare`: 23 de 24 detectadas; o sobrevivente é equivalente (o texto de recusa não casa
com nenhum item).

**Limites da métrica (honestidade).** "Itens" mede **presença**, não **correção**: uma resposta pode conter todos os
itens e afirmar algo errado ao lado. Exemplos vistos: o 3b respondeu, na Q16, que o devedor principal *precisa*
atingir os limites (o contrário do art. 15, § 5º), e, na Q15, atribuiu à responsabilidade subsidiária uma regra da
solidariedade. Nenhuma métrica atual pega isso; seria preciso um conjunto de "afirmações proibidas" por pergunta ou
revisão humana. Os 12 acertos de cada modelo valem como "completo e citado", não como "juridicamente correto".

**Experimento de prompt para completude (resultado negativo).** Hipótese: o pedido "em poucas frases" (no
`SYSTEM_PROMPT` e no `REMINDER`) faz o 3b omitir itens de listas. Variante testada, mudando **só o texto do prompt**
(mesmo modelo, mesmos parâmetros, mesmas 21 perguntas): "em poucas frases" saiu; entrou o pedido de trazer todos os
itens da lista, sem resumir. Resultados em `eval/relatorios/comparacao-prompt.md`:

| | 3b depois (prompt original) | 3b completo (variante) |
|---|---:|---:|
| Respostas corretas | 12 de 21 | 10 de 21 |
| Itens do gabarito presentes | 73% | 68% |
| Citações dos artigos esperados | 86% | 80% |
| Citações inexistentes | 0 | 0 |
| Tempo médio das respondidas | 60,5 s | 80,0 s |
| Tamanho médio da resposta | 544 caracteres | 522 caracteres |

A variante **não ajudou**: as respostas não ficaram mais longas, e as duas perguntas que pioraram (Q03 e Q11) foram
cortes em pontos diferentes (o modelo copia os fragmentos e para onde quer), não efeito do pedido. A hipótese estava
errada: o limite de tamanho não vem de "em poucas frases". Com temperatura 0, mudar qualquer palavra do prompt muda o
caminho da geração; uma diferença de 2 perguntas em 21 está dentro desse ruído, então **não afirmo que a variante é
pior**, só que não há evidência de melhora. Decisão: prompt original mantido (a variante foi desfeita, nada a
reverter no produto). O tempo maior (80 s) não é comparável: a máquina varia entre rodadas e o cache de prefixo do
Ollama muda os tempos. Intercorrência: a Q16 estourou o limite de 300 s na primeira tentativa (o Ollama continuou
vivo); a rodada foi retomada com `--resume` e `RAG_TIMEOUT=600`, e a Q16 levou 15 s na segunda tentativa, o que
indica travamento pontual e não pergunta lenta. Limite do experimento: uma única variante e uma única rodada por
variante.

**Revisão do plano:** a calibração do limiar e a medição do k não precisam do modelo de chat, então rodam em
segundos; só a comparação 3b × 7b é demorada.

## Revisão humana

- [ ] As perguntas e os gabaritos (itens) refletem situações reais de uso?
- [ ] A definição de "resposta correta" (conteúdo completo + artigos citados + sem citação inexistente) é razoável?

_Alterações feitas após a revisão:_ (preencher)
