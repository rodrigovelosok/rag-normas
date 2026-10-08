---
fase: 03-implementacao-nucleo
modulo: rag_normas/cli.py, rag_normas/__main__.py
unidade_curso: "C04 — Unidade 3 (Implementação do núcleo)"
data: 2026-10-08
ferramenta: Claude Code
modelo: Claude Sonnet 5.5 (claude-sonnet-5-5)
autoria: prompt escrito e executado pela IA, sob direção e revisão de Rodrigo Kobayashi
artefato_gerado: rag_normas/cli.py, rag_normas/__main__.py, tests/test_cli.py
---

# Prompt 03.5 — `cli.py`: os comandos `index` e `ask`

## Prompt (CO-STAR)

### C — Contexto

Projeto `rag-normas`. Os módulos `ingest`, `search`, `config`, `llm`, `index` e `generate` estão prontos e
testados (124 testes). Falta a camada que o usuário toca: a linha de comando (RF03, RF04, RF08). Decisões
herdadas: só `llm.py` importa `ollama` (D4); as funções `embed` e `chat` são entregues por parâmetro (D5);
`Settings.from_env` lê as variáveis `RAG_*` e `Settings.with_overrides` ignora valores `None`, de modo que as
opções da linha de comando (que valem `None` quando não informadas) tenham precedência sobre o ambiente.
Todas as exceções do projeto (`ConfigError`, `LLMError`, `IndexFileError`) já trazem mensagem do tipo "o que
aconteceu + o que fazer".

### O — Objetivo

Testes primeiro (`tests/test_cli.py`), depois `rag_normas/cli.py` e `rag_normas/__main__.py`:

- `main(argv=None, environ=None, llm_factory=make_llm) -> int`, com `llm_factory(settings)` devolvendo
  `(embed, chat)`; assim os testes passam funções falsas e nunca precisam do Ollama;
- comando `index`: lê o corpus, gera os vetores com progresso a cada lote (na saída de erro), grava o índice e
  imprime um resumo (quantidade de artigos, modelo, caminho). Com corpus vazio, falha **antes** de chamar o Ollama;
- comando `ask "<pergunta>"`: carrega o índice (conferindo o modelo de embedding), busca, gera e imprime a saída de
  `format_output`. Índice ausente ou de outro modelo falha **antes** de chamar o Ollama. Pergunta vazia é erro de uso;
- opções `--host`, `--model`, `--embed-model`, `--top-k`/`-k`, `--min-similarity`, `--index`, `--corpus`, que
  sobrepõem as variáveis de ambiente, que sobrepõem os padrões;
- opção `--scores` no `ask`: mostra, na saída de erro, o limiar e a similaridade de cada artigo recuperado (para
  calibrar o limiar na Fase 4);
- códigos de saída: 0 sucesso (inclusive recusa, que é um resultado válido), 1 erro do sistema ou de configuração
  (mensagem `Erro: ...` sem traceback), 2 erro de uso (do `argparse` ou pergunta vazia);
- `python -m rag_normas` chama `main`.

### S — Estilo

Python 3.14, PEP 8, *type hints*, *docstrings* no formato Google, nomes em inglês, textos para o usuário em
português. Só biblioteca padrão (`argparse`). Nenhum caminho absoluto em mensagens.

### T — Tom

Mensagens curtas e diretas; erros dizem o que fazer.

### A — Audiência

O autor (programador iniciante em Python), que vai rodar os comandos, e o avaliador do mini-projeto.

### R — Resposta

Três arquivos (dois módulos e os testes). Testes falham antes e passam depois; depois, teste de mutação e um teste
de realidade com o Ollama.

## Resultado

Gerados `cli.py`, `__main__.py` e `tests/test_cli.py` (26 testes; 150 no total, em ~3 s, bem abaixo do limite de 30 s
do RNF03). Ciclo TDD: vermelho (módulo inexistente), verde com 2 falhas **nos testes** (não no código): uma
asserção que ignorava a linha "Indexando..." na saída de erro, e a saída do subprocesso, que no Windows sai em
cp1252 quando redirecionada (o teste passou a fixar `PYTHONIOENCODING=utf-8`).

**Teste de mutação:** 29 alterações propositais, 29 detectadas. Na primeira rodada, 1 sobreviveu: nenhum teste
distinguia "conferir as citações contra os artigos do índice" de "contra os artigos recuperados". Virou o teste
`test_citation_of_an_indexed_article_that_was_not_retrieved_is_not_flagged`.

**Incidente durante a mutação (erro da IA, sem dano):** os mutantes "`--index` ignorado" e "`--corpus` ignorado" fazem
o programa usar o caminho padrão, e os testes gravaram um índice falso por cima do `data/index.json` real. O arquivo é
gerado e está no `.gitignore`, então nada foi publicado; foi regenerado com o próprio comando novo (64 s, 479 KB,
idêntico). O script de mutação agora guarda uma cópia do índice real e a restaura no fim. Lição: um mutante pode
fazer o código atingir arquivos reais, e o experimento precisa ser isolado antes de rodar.

**Teste de realidade (comandos de verdade, com o Ollama):**

| Comando | Resultado |
|---|---|
| `index` | 31 artigos, progresso em 4 lotes, 64 s, `data/index.json` regravado |
| `ask "Quem pode pedir o cancelamento…" --scores` | saída completa com limiar e similaridades; **conteúdo errado**: o 3b respondeu sobre medida cautelar fiscal (art. 11, § 6º), não sobre quem pede o cancelamento, e na rodada anterior havia dado outra resposta incompleta |
| `ask "Qual a alíquota do IRPF?"` | recusa pelo limiar (0,49 < 0,52), código de saída 0 |
| `--host` inválido | `Erro: Não consegui falar com o Ollama em … Execute: ollama serve`, saída 1, sem traceback |
| `--model` inexistente | `Erro: O modelo '…' não está instalado… ollama pull …`, saída 1 |
| `RAG_TOP_K=zero` | `Erro: RAG_TOP_K deve ser um número inteiro maior que 0; recebi 'zero'`, saída 1 |
| índice ausente | `Erro: Índice não encontrado em … Crie com: python -m rag_normas index`, saída 1 |

**Para a Fase 4:** o mesmo modelo, com temperatura 0, deu respostas de qualidade diferente para a mesma pergunta
conforme os artigos recuperados mudaram de ordem; a qualidade do conteúdo com 4 artigos longos (~12 mil caracteres)
é o ponto fraco do `qwen2.5:3b`. A avaliação precisa medir isso (acerto do conteúdo, não só da citação) e testar
`k` menor e o modelo de 7 bilhões.

Decisões da IA além do pedido: `--scores` (mostra o que a recusa viu, para calibrar o limiar) e a escrita do
progresso na saída de erro, deixando a saída padrão só com o resultado.

## Revisão humana

- [ ] Os nomes das opções (`--model`, `--top-k`, `--scores`…) fazem sentido para quem usa?
- [ ] As mensagens de erro dizem o que fazer?
- [ ] A regra "opção > variável de ambiente > padrão" está clara?

_Alterações feitas após a revisão:_ (preencher)
