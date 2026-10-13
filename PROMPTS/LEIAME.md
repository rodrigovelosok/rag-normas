# Prompts usados no desenvolvimento

Este projeto foi desenvolvido com o Claude Code (ver "Como a IA foi usada" no [README](../README.md)). Esta pasta
guarda **o prompt de cada etapa**, o **resultado** e a **revisão humana**, para quem quiser ver como a IA foi
conduzida, e não só o que ela produziu.

## Como ler um arquivo

Cada arquivo segue o formato **CO-STAR**, que organiza um prompt em seis partes:

| Letra | Parte | Para quê |
|---|---|---|
| **C** | Contexto | o que a IA precisa saber sobre o projeto naquele momento |
| **O** | Objetivo | a tarefa, com critérios verificáveis |
| **S** | Estilo | convenções de código e escrita |
| **T** | Tom | como o texto deve soar |
| **A** | Audiência | quem vai ler o resultado |
| **R** | Resposta | o formato do que deve ser entregue |

Depois do prompt vêm duas seções:

- **Resultado:** o que a IA fez, com números, erros e decisões. Foi escrito **depois** da execução.
- **Revisão humana:** perguntas que o autor responde ao revisar a etapa, e o que mudou por causa da revisão.

## Índice

| Fase | Arquivo | Assunto |
|---|---|---|
| 1. Ideação e requisitos | [`01-ideacao-requisitos/01-especificacao-de-requisitos.md`](01-ideacao-requisitos/01-especificacao-de-requisitos.md) | requisitos funcionais, não funcionais e critérios de aceitação |
| 2. Arquitetura | [`02-arquitetura/01-arquitetura-e-modulos.md`](02-arquitetura/01-arquitetura-e-modulos.md) | módulos, fluxo de dados e decisões de projeto |
| 3. Núcleo | [`03-implementacao-nucleo/01-ingest-leitura-das-normas.md`](03-implementacao-nucleo/01-ingest-leitura-das-normas.md) | leitura das normas e divisão em artigos |
| | [`03-implementacao-nucleo/02-search-busca-hibrida.md`](03-implementacao-nucleo/02-search-busca-hibrida.md) | busca híbrida (BM25, vetor e RRF) |
| | [`03-implementacao-nucleo/03-config-llm-e-index.md`](03-implementacao-nucleo/03-config-llm-e-index.md) | configuração, acesso ao Ollama e índice |
| | [`03-implementacao-nucleo/04-generate-resposta-e-recusa.md`](03-implementacao-nucleo/04-generate-resposta-e-recusa.md) | resposta, recusa e conferência das citações (o experimento de prompt mais instrutivo) |
| | [`03-implementacao-nucleo/05-cli-index-e-ask.md`](03-implementacao-nucleo/05-cli-index-e-ask.md) | linha de comando |
| 4. Testes | [`04-testes/01-avaliacao-do-sistema.md`](04-testes/01-avaliacao-do-sistema.md) | conjunto de avaliação, calibração, comparação 3b × 7b e experimento de prompt |
| 5. Refatoração | [`05-refatoracao/01-divisao-do-avaliador-e-limpeza.md`](05-refatoracao/01-divisao-do-avaliador-e-limpeza.md) | divisão do avaliador, linter e rede de segurança |
| 6. Documentação | [`06-documentacao/01-readme-final.md`](06-documentacao/01-readme-final.md) | README final e demonstração |

Se for ler só um, leia o da fase 3 sobre **resposta e recusa**: mostra o modelo pequeno recusando perguntas que a
norma responde, e como isso foi descoberto e corrigido medindo, e não adivinhando.

## Uma correção de 13/10/2026

Os prompts foram escritos e executados com a audiência **"o autor e o avaliador do curso"**. Depois se percebeu que
o link do repositório vai ao fórum de discussão, onde todos os alunos da especialização o leem e comentam o
projeto. Por isso, **em 13/10/2026 a linha "Audiência" de nove arquivos foi ampliada** para incluir os colegas.
Foi só essa linha: o restante de cada prompt e de cada resultado está como foi executado. O prompt de
`04-generate-resposta-e-recusa.md` não mudou, porque a audiência dele é o modelo de linguagem e quem usa o
terminal.
