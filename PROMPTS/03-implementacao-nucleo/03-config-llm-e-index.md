---
fase: 03-implementacao-nucleo
modulo: rag_normas/config.py, rag_normas/llm.py, rag_normas/index.py
unidade_curso: "C04 — Unidade 3 (Implementação do núcleo)"
data: 2026-10-08
ferramenta: Claude Code
modelo: Claude Sonnet 5.5 (claude-sonnet-5-5)
autoria: prompt escrito e executado pela IA, sob direção e revisão de Rodrigo Kobayashi
artefato_gerado: rag_normas/config.py, rag_normas/llm.py, rag_normas/index.py e os testes correspondentes
---

# Prompt 03.3 — Configuração, ponte com o Ollama e índice

## Prompt (CO-STAR)

### C — Contexto

Projeto `rag-normas`; `ingest.py` e `search.py` já existem (52 testes). Faltam, no fluxo `index`, a leitura da
configuração, a chamada ao Ollama e a gravação do índice (RF03, RF08). Decisões da arquitetura: `llm.py` é o
**único** módulo que importa `ollama` (D4); `embed` e `chat` são funções entregues aos outros módulos (D5); o
índice é um JSON com `embedding_model`, `created_at` e a lista de chunks, cada um com seu `vector`.

Fatos medidos nesta máquina (CPU, sem GPU dedicada): embutir os 31 artigos leva ~60 s; o art. 4º tem 4.104
caracteres e quatro artigos grandes passam do contexto padrão do Ollama (4.096 tokens), então o `num_ctx` deve
ser configurado explicitamente. A biblioteca `ollama` 0.6.3 lança `ConnectionError` quando o servidor não
responde e `ollama.ResponseError(error, status_code)` quando, por exemplo, o modelo não está instalado (404).

### O — Objetivo

Testes primeiro, depois:

- `config.py`: `Settings` imutável (host do Ollama, modelo de chat, modelo de embedding, `top_k`, limiar mínimo de
  similaridade, `num_ctx`, `timeout`, caminho do índice, pasta do corpus) com `Settings.from_env(environ)`, valores
  padrão e erro claro (`ConfigError`) para valor inválido;
- `llm.py`: `make_llm(settings, client=None)` devolvendo as funções `embed(texts)` e `chat(messages)`, com
  `temperature = 0` e `num_ctx` no chat, e erros `LLMError` com mensagem que diga **o que fazer** (iniciar o
  Ollama, instalar o modelo com `ollama pull`);
- `index.py`: `Index`, `build_index` (em lotes, com callback de progresso), `save_index` (gravação atômica) e
  `load_index` (arquivo ausente, JSON quebrado e modelo de embedding diferente viram `IndexFileError` com instrução).

### S — Estilo

Python 3.14, PEP 8, *type hints*, *docstrings* no formato Google, nomes em inglês, mensagens de erro em português.
Só biblioteca padrão, além do `ollama` dentro de `llm.py`. Os testes usam um cliente falso e um `embed` falso, e
cada mensagem de erro é verificada.

### T — Tom

Mensagens de erro diretas, no formato "o que aconteceu + o que fazer".

### A — Audiência

O autor (programador iniciante em Python), que vai rodar os comandos, e o avaliador.

### R — Resposta

Seis arquivos: três módulos e três arquivos de teste. Os testes falham antes e passam depois; depois roda-se o
teste de mutação.

## Resultado

Gerados `config.py`, `llm.py`, `index.py` e seus 36 testes (88 no total). Ciclo TDD: vermelho (módulos
inexistentes), verde, mutação.

**Teste de mutação:** 24 alterações propositais (8 por módulo), **24/24 detectadas** na primeira rodada.

**Teste de realidade contra o Ollama** (executado de verdade, fora da suíte):

- Indexar os 31 artigos levou **55 s** em 4 lotes de 8; o índice (JSON) tem 479 KB, vetores de 1024 dimensões,
  e foi gravado e relido idêntico.
- Os três caminhos de erro foram provocados e as mensagens aparecem como planejado: Ollama fora do ar
  (`ollama serve`), modelo de chat inexistente e modelo de embedding inexistente (`ollama pull <modelo>`).
  Isso confirma que o Ollama real lança `ConnectionError` e `ResponseError` 404, como o código esperava.
- Chat real com `num_ctx = 8192` e temperatura 0: resposta em 6,7 s (modelo já carregado).

Decisões da IA além do pedido:

- **Validação num só lugar** (`_RULES` em `config.py`), valendo para variável de ambiente e para valor passado
  no código; as mensagens de variável citam o nome (`RAG_TOP_K`).
- **Limiar de similaridade provisório (0,52)**, marcado como provisório na docstring, escolhido entre o pior
  caso do corpus (0,57) e o IRPF fora do corpus (0,50); a calibração fica para a Fase 4.
- **Gravação atômica** do índice (arquivo temporário e troca), para uma falha no meio não destruir o índice
  anterior.
- `httpx` importado em `llm.py` só para tratar timeout; ele já vem como dependência do `ollama`.

## Revisão humana

- [ ] As mensagens de erro ajudam alguém que nunca viu o projeto?
- [ ] O limiar de similaridade provisório está claramente marcado como provisório?

_Alterações feitas após a revisão:_ (preencher)
