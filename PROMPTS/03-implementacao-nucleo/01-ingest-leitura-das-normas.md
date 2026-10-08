---
fase: 03-implementacao-nucleo
modulo: rag_normas/ingest.py
unidade_curso: "C04 — Unidade 3 (Implementação do núcleo)"
data: 2026-10-08
ferramenta: Claude Code
modelo: Claude Sonnet 5.5 (claude-sonnet-5-5)
autoria: prompt escrito e executado pela IA, sob direção e revisão de Rodrigo Kobayashi
artefato_gerado: rag_normas/ingest.py, tests/test_ingest.py
---

# Prompt 03.1 — `ingest.py`: leitura das normas e divisão por artigo

## Prompt (CO-STAR)

### C — Contexto

Projeto `rag-normas` (chatbot RAG local sobre arrolamento de bens). Arquitetura em `docs/arquitetura.md`:
`ingest.py` é o primeiro módulo do fluxo `index`; ele lê os textos de `data/normas/*.txt` e devolve uma lista
de `Chunk`, um por artigo. Requisitos atendidos: RF01 e RF02; critérios CA01 e CA02.

Formato dos arquivos (já verificado):

- Primeira linha: título da norma; segunda: ementa; depois, um preâmbulo, que **não** é artigo.
- Cada artigo começa em uma linha que inicia com `Art. N` seguido de `º` ou `.` (`Art. 1º`, `Art. 10.`,
  `Art. 64-A.`). Parágrafos (`§ 1º`), incisos (`I -`) e alíneas (`a)`) vêm nas linhas seguintes.
- Cabeçalhos de estrutura ocupam **duas linhas**: `CAPÍTULO II` + título em maiúsculas, ou `Seção VII` + título.
  Eles não fazem parte do texto de nenhum artigo.
- Referências a outros artigos no meio de uma linha (`...prevista no art. 12., com...`) **não** iniciam artigo.
- Anotações de alteração aparecem entre colchetes no fim do dispositivo (`[Redação dada pela IN RFB nº 2338/2026]`)
  e devem ficar no texto.
- Gabarito do corpus: IN RFB 2.091/2022 com 27 artigos, Lei 9.532/1997 com 2 (`64`, `64-A`) e Decreto
  7.573/2011 com 2; total 31.

### O — Objetivo

Escrever **primeiro os testes** (`tests/test_ingest.py`) e depois `rag_normas/ingest.py` com:

- `Chunk`: dado imutável com `norm`, `article`, `section` e `text`, e uma propriedade `reference` no formato
  `IN RFB 2.091/2022, art. 5º` (com `º` de 1 a 9, sem `º` de 10 em diante, e `art. 64-A`);
- `parse_norm(text, norm)`: divide **um** texto em chunks, registrando a seção (capítulo e seção em vigor);
- `load_corpus(folder)`: lê todos os `.txt` da pasta, em ordem alfabética, e junta os chunks.

### S — Estilo

Python 3.14, PEP 8, *type hints* e *docstrings* no formato Google. Nomes em inglês. Funções curtas e
legíveis por quem está começando: uma expressão regular nomeada por tipo de linha, sem truques. Só biblioteca
padrão (`re`, `dataclasses`, `pathlib`). Testes com `pytest`, nomes de teste descritivos.

### T — Tom

Comentários didáticos e curtos, explicando o **porquê** de cada regex; mensagens de erro claras em português.

### A — Audiência

O autor (programador iniciante em Python), que vai ler o código e explicá-lo no fórum, e o avaliador do curso.

### R — Resposta

Dois arquivos: `tests/test_ingest.py` e `rag_normas/ingest.py` (mais `rag_normas/__init__.py` vazio). Os testes
precisam falhar antes de existir o código e passar depois.

## Resultado

Gerados `tests/test_ingest.py` (21 testes) e `rag_normas/ingest.py`, seguindo o ciclo do TDD: testes primeiro
(vermelho: o módulo não existia), código depois (verde: 21 passam). O corpus real produz os 31 chunks esperados
(27 + 2 + 2), com a seção de cada artigo registrada.

Verificação adicional feita pela IA: **teste de mutação manual**. Quatro alterações propositais no código foram
todas detectadas pelos testes. Uma quinta (remover a âncora `^` da regex de artigo) **não era detectada**: nenhum
teste tinha um "Art. N" com maiúscula no meio de uma linha. O teste `test_reference_inside_a_line_does_not_start_an_article`
foi reforçado e passou a falhar com essa mutação.

Pontos em que a IA foi além do pedido:

- **Campo `section`** com capítulo e seção (decisão da IA): serve de contexto para a busca, por exemplo "Da
  Substituição de Bens e Direitos Arrolados" ajuda a achar o art. 15 numa pergunta sobre substituição.
- **Rótulos de norma por dicionário** (`NORM_LABELS`), com o nome do arquivo como padrão, para novas normas
  entrarem no corpus sem mexer no código.
- **Correção de inconsistência:** `docs/arquitetura.md` nomeava os campos em português, contra o RNF05. Corrigido
  para inglês no mesmo commit.

Achado para o próximo módulo: o art. 4º da IN tem 4.104 caracteres; quatro artigos grandes passam do contexto
padrão do Ollama (4.096 tokens). O `generate.py` deve configurar `num_ctx` explicitamente.

## Revisão humana

- [ ] O código está legível? Alguma parte você não consegue explicar?
- [ ] As seções (`section`) ajudam ou atrapalham a leitura dos chunks?

_Alterações feitas após a revisão:_ (preencher)
