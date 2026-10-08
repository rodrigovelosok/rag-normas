---
fase: 03-implementacao-nucleo
modulo: rag_normas/search.py
unidade_curso: "C04 — Unidade 3 (Implementação do núcleo)"
data: 2026-10-08
ferramenta: Claude Code
modelo: Claude Sonnet 5.5 (claude-sonnet-5-5)
autoria: prompt escrito e executado pela IA, sob direção e revisão de Rodrigo Kobayashi
artefato_gerado: rag_normas/search.py, tests/test_search.py
---

# Prompt 03.2 — `search.py`: busca híbrida (BM25 + vetor + RRF)

## Prompt (CO-STAR)

### C — Contexto

Projeto `rag-normas`. `ingest.py` já entrega 31 `Chunk` (um por artigo; campos `norm`, `article`, `section`,
`text`). Em `docs/arquitetura.md`, o `search.py` recebe a pergunta e devolve os *k* artigos mais relevantes
(RF04). Decisões já tomadas: Python puro, sem NumPy (D3); o Ollama fica isolado em `llm.py` (D4), então o
`search.py` **recebe `embed` como parâmetro** (D5) e nunca importa `ollama`; BM25 recalculado a cada pergunta (D8).

Dados de entrada: lista de `Chunk` e uma lista de vetores do mesmo tamanho, na mesma ordem (fornecida pelo
`index.py`, que ainda não existe). Os vetores têm 1024 dimensões (`bge-m3`) e o texto indexado de cada chunk é
`section + text`.

Motivo da busca híbrida: texto jurídico depende de termos exatos ("Selo Confia", "64-A", "30%"), que a busca
só por vetor encontra mal; e perguntas com palavras diferentes das da norma ("vender imóvel arrolado" × "alienação
de bem arrolado") são o ponto forte do vetor.

### O — Objetivo

Escrever primeiro os testes (`tests/test_search.py`) e depois `rag_normas/search.py` com:

- `tokenize(text)`: minúsculas, sem acentos, só letras e dígitos (`"64-A"` vira `["64", "a"]`);
- `bm25_scores(query_tokens, documents, k1=1.5, b=0.75)`: pontuação BM25 de cada documento (lista de listas de
  tokens), com IDF sempre positivo, normalização pelo tamanho do documento e termo repetido na pergunta contado
  uma vez;
- `cosine(a, b)`: similaridade de cosseno, com 0.0 para vetor nulo e erro claro para tamanhos diferentes;
- `rrf(rankings, k=60)`: Reciprocal Rank Fusion, somando `1 / (k + posição)` de cada lista em que o item aparece;
- `Hit`: dado imutável com `chunk`, `similarity`, `bm25` e `score` (o do RRF);
- `hybrid_search(query, chunks, vectors, embed, k=4)`: embute a pergunta **uma vez**, monta o ranking por vetor e o
  ranking por BM25 (**só com quem tem pontuação maior que zero**), funde por RRF e devolve os *k* melhores
  (desempate pela similaridade).

Também: adicionar a `Chunk` (em `ingest.py`) a propriedade `search_text`, que junta `section` e `text`, para o
`index.py` e o `search.py` usarem exatamente o mesmo texto.

### S — Estilo

Python 3.14, PEP 8, *type hints*, *docstrings* no formato Google, nomes em inglês, só biblioteca padrão
(`math`, `re`, `unicodedata`, `collections`, `dataclasses`). Uma função por responsabilidade, curtas. Testes com
valores numéricos conferíveis à mão (por exemplo, `1/61`), vetores de 2 dimensões e `embed` falso.

### T — Tom

Comentários curtos e didáticos sobre o porquê de cada decisão numérica (por que `+1` no IDF, por que o `k = 60`).

### A — Audiência

O autor (programador iniciante em Python) e o avaliador do curso.

### R — Resposta

`tests/test_search.py`, `rag_normas/search.py` e a alteração em `ingest.py` com o teste correspondente em
`tests/test_ingest.py`. Os testes devem falhar antes do código e passar depois.

## Resultado

Gerados `rag_normas/search.py` (`tokenize`, `cosine`, `bm25_scores`, `rrf`, `Hit`, `hybrid_search`) e
`tests/test_search.py` (31 testes), mais `Chunk.search_text` em `ingest.py`. Ciclo TDD: vermelho, depois verde
(52 testes no total).

**Teste de mutação automatizado** (script fora do repositório, 12 alterações propositais): 11 detectadas na
primeira rodada. Sobreviveu "sem desempate pela similaridade" e, desta vez, **não** era mutante equivalente:
foi construído um caso de empate exato no RRF (dois artigos que se alternam nas posições 1 e 2 dos dois
rankings) e o teste novo passou a detectá-la. Resultado final: 12/12.

**Teste de realidade com o Ollama** (embeddings reais do `bge-m3`, 6 perguntas; exploração, não faz parte da
suíte). Achados, com a ressalva de que são poucas perguntas:

- Funciona bem para perguntas com termos específicos: "Selo Confia" traz o art. 10 em 1º lugar; "prazo para
  recorrer" traz o art. 21.
- **Limite do `k = 4`:** "Qual o valor mínimo de débitos para o arrolamento?" traz o art. 2º da IN em 1º, mas
  **o Decreto 7.573 (art. 1º) e o art. 64 da Lei ficam de fora**: o caso planejado na D9 ainda não passa.
  "Posso vender um imóvel arrolado?" não traz o art. 12 da IN (a obrigação de comunicar a alienação).
- **Limiar de recusa:** a melhor similaridade das perguntas do corpus foi 0,57 a 0,69; fora do corpus, 0,33
  (bolo de chocolate) e **0,50** (alíquota do IRPF, tema vizinho). A separação existe, mas é estreita. O BM25
  **não serve** como sinal de recusa: a pergunta do IRPF teve BM25 alto (12,6) por palavras como "pessoa física".
- **RRF com `k = 60`:** as notas finais ficam entre 0,0305 e 0,0328, uma diferença mínima entre 1º e 4º. A
  calibração (por exemplo, `k = 20`, como no RAG do cofre) fica para a avaliação da Fase 4.
- Gerar os vetores dos 31 artigos levou **60 s** nesta máquina (custo único do comando `index`).

Pontos em que a IA foi além do pedido: `Chunk.search_text` compartilhado entre índice e busca; mensagem de erro
"reindexe o corpus" quando o número de vetores não bate com o de artigos.

## Revisão humana

- [ ] Você consegue explicar, com as suas palavras, por que BM25 e vetor se complementam?
- [ ] O `k = 60` do RRF vai ser calibrado na Fase 4 com o conjunto de avaliação. Concorda em deixar assim por ora?

_Alterações feitas após a revisão:_ (preencher)
