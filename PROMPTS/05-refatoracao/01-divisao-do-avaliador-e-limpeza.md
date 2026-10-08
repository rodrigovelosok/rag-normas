---
fase: 05-refatoracao
modulo: eval/ (avaliar.py dividido), rag_normas/ (ajustes apontados pelo linter)
unidade_curso: "C04 — Unidade 4 (Testes, refatoração e documentação)"
data: 2026-10-08
ferramenta: Claude Code
modelo: Claude Opus 5.5 (claude-opus-5-5)
autoria: prompt escrito e executado pela IA, sob direção e revisão de Rodrigo Kobayashi
artefato_gerado: eval/gabarito.py, eval/metricas.py, eval/rodada.py, eval/markdown.py, eval/avaliar.py, ruff.toml
---

# Prompt 05.1 — Divisão do avaliador e limpeza sem regressão

## Prompt (CO-STAR)

### C — Contexto

Projeto `rag-normas` com as Fases 3 e 4 concluídas: 245 testes (~3 s) e avaliação real registrada. O núcleo
(`rag_normas/`, 8 módulos de 11 a 167 linhas) está coeso. O avaliador cresceu durante a Fase 4 e virou um arquivo
único de 867 linhas (`eval/avaliar.py`) com cinco responsabilidades: gabarito (ler e validar perguntas), métricas,
execução das rodadas (busca, chat, arquivos `.jsonl`), relatórios em Markdown e linha de comando. Há também
duplicações pequenas (a conferência de itens e citações aparece em `run_answer` e em `rescore`; o cálculo dos
artigos ausentes aparece em `article_recall` e no relatório da busca) e duas funções longas (`render_comparison`,
55 linhas, e `render_retrieval_report`, 63 linhas). Um linter (`ruff`) aponta 26 linhas acima de 130 caracteres,
uma importação sem uso e dois `zip()` sem `strict=`.

### O — Objetivo

Melhorar a estrutura **sem mudar o comportamento**:

1. Dividir `eval/avaliar.py` por responsabilidade, sem ciclos de importação: `gabarito.py` → `metricas.py` →
   `rodada.py` e `markdown.py` → `avaliar.py` (só a linha de comando). O comando continua sendo
   `python -m eval.avaliar`.
2. Eliminar as duplicações citadas e quebrar as duas funções longas em partes com nome.
3. Adotar o `ruff` (linter e formatador) com configuração versionada (`ruff.toml`) e zerar os apontamentos.
4. Corrigir comentários desatualizados.

Rede de segurança, definida **antes** de mexer: (a) os 245 testes passam sem alterar nenhuma asserção (só as
linhas de importação podem mudar, porque as funções mudam de arquivo); (b) *golden master*: as saídas reais dos
comandos (`--help` de todos os comandos, `compare`, `rescore` das quatro rodadas, `retrieval` com o Ollama e uma
mensagem de erro) são gravadas antes e comparadas byte a byte depois.

Fora do escopo: mudar comportamento. Se o linter apontar um defeito real (como `zip()` que corta dados em
silêncio), a correção vai num commit separado, como `fix`, com teste primeiro.

### S — Estilo

Python 3.14, PEP 8, *type hints*, *docstrings* no formato Google, identificadores em inglês, textos e nomes de
arquivos do avaliador em português (como `avaliar.py`, `perguntas.json`). Um commit por passo, cada um com a
rede de segurança verde.

### T — Tom

Relatório objetivo, com números, e explicação didática dos termos de engenharia de software.

### A — Audiência

O autor (programador iniciante em Python, aprendendo engenharia de software) e o avaliador do mini-projeto.

### R — Resposta

Os módulos novos, o `ruff.toml`, as importações dos testes atualizadas, o relatório do *golden master* e uma tabela
"antes × depois" (linhas por arquivo, maior função, apontamentos do linter).

## Resultado

Sete commits, cada um com a rede de segurança verde:

| Commit | Tipo | O que fez |
|---|---|---|
| `5fe4d50` | refactor | `avaliar.py` dividido em 5 módulos; duas duplicações removidas; relatório da busca em 5 seções |
| `6047d20` | test | 2 testes novos e 1 asserção: partes do relatório que só o *golden master* protegia |
| `a9ff952` | style | `ruff` adotado (`ruff.toml`, `requirements-dev.txt`); formatação automática em 12 arquivos |
| `684debf` | style | alvo do `ruff` em 3.13 para manter `except (A, B):` e `-> "Settings"` legíveis |
| `2124f91` | fix | `save_index` recusa índice com quantidades diferentes de artigos e vetores (teste antes) |
| `ffd1e37` | docs | comentários que falavam da Fase 4 como futura |
| `876d49d` | fix | a ajuda do avaliador listava só 2 dos 4 comandos (teste antes) |

**Antes × depois:**

| | Antes | Depois |
|---|---|---|
| Maior arquivo do avaliador | `avaliar.py`, 867 linhas, 5 assuntos | `markdown.py`, 303 linhas, 1 assunto |
| Maior função de relatório | `render_retrieval_report`, 63 linhas | `render_report`, 46 linhas (lista plana de células) |
| Apontamentos do `ruff` (regras do `ruff.toml`) | 68 | 0 |
| Testes | 245 | 249 |
| Mutação nas partes refatoradas | — | 13 de 14 (o sobrevivente é o mutante equivalente já conhecido) |

**Rede de segurança.** Os testes antigos passaram sem mudar nenhuma asserção; no `test_avaliar.py` só as
importações mudaram. O *golden master* (15 saídas reais, incluindo a busca com o Ollama) ficou idêntico byte a byte
depois do `refactor` e do `style`. A única diferença no fim é a esperada, a linha de uso do `--help` corrigida no
último `fix`. Antes de usar o *golden master*, ele foi rodado duas vezes sem mudança no código, para confirmar
que as saídas não variam sozinhas. Os textos do prompt (`SYSTEM_PROMPT`, `REMINDER`) e dos avisos foram
conferidos antes e depois da quebra das linhas longas.

**O que a rede de segurança pegou durante o trabalho:**
- a quebra da linha longa do `SYSTEM_PROMPT` introduziu um `\n` literal no prompt (erro de barra invertida no
  *heredoc*); a comparação dos textos acusou a diferença antes do commit;
- o formatador, com alvo 3.14, removeu os parênteses de um `except (A, B, C):` e as aspas de anotações; o código
  continuava correto, mas a forma nova parece a sintaxe do Python 2 e confunde quem lê; corrigido na configuração;
- a mutação mostrou três comportamentos do relatório da busca sem teste (já existiam antes da refatoração).

**Achados que não eram refatoração** (viraram `fix` ou `docs`, separados):
- `zip()` sem `strict=` no `save_index` gravaria em silêncio um índice incompleto;
- a promessa do `generate.py` de "medir na Fase 4" as citações de artigos não recuperados nunca tinha sido
  cumprida. Foi medida agora nas rodadas gravadas: 1 caso em 65 respostas (3b, configuração antiga), nenhum com a
  calibrada;
- o `--help` desatualizado.

**Total de linhas do avaliador: 867 → 1.102 (+27%).** Cada módulo novo tem docstring e importações próprias, e o
formatador quebrou linhas longas em várias. Refatorar para clareza nem sempre reduz linhas: o ganho é cada arquivo
ter um assunto só e dependências em uma direção (`gabarito` → `metricas` → `rodada`/`markdown` → `avaliar`).
`build_parser` (67 linhas) ficou longa, mas é uma lista plana de opções, sem decisões; dividi-la só espalharia a
lista.

**Não feito (de propósito):** o arquivo de testes `test_avaliar.py` não foi dividido como o código; a função
`hybrid_search` mantém o padrão `rrf_k = 60` (o produto sempre passa o valor configurado, 5).

## Revisão humana

- [ ] A divisão em módulos ficou fácil de navegar (cada arquivo tem um assunto só)?
- [ ] Os nomes dos módulos (`gabarito`, `metricas`, `rodada`, `markdown`, `avaliar`) estão claros?

_Alterações feitas após a revisão:_ (preencher)
