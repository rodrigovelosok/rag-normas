---
fase: 06-documentacao
modulo: README.md, docs/img/demo.gif
unidade_curso: "C04 — Unidade 4.3 (documentação) e Unidade 5.2 (README final)"
data: 2026-10-08
ferramenta: Claude Code
modelo: Claude Opus 5.5 (claude-opus-5-5)
autoria: prompt escrito e executado pela IA, sob direção e revisão de Rodrigo Kobayashi
artefato_gerado: README.md, docs/img/demo.gif
---

# Prompt 06.1 — README final e demonstração

## Prompt (CO-STAR)

### C — Contexto

Projeto `rag-normas` com núcleo, avaliação e refatoração concluídos (249 testes, avaliação real registrada em
`eval/relatorios/`, prompts por fase em `PROMPTS/`). O README atual é provisório. O curso (Unidade 5.2 e checklist
5.3.1) pede: objetivo, instalação, execução, exemplos, tecnologias, seção sobre o uso de IA (desafios superados,
ganhos de produtividade, decisões de design, lições aprendidas e revisão humana), limitações, próximos passos,
instruções de teste e, se possível, demonstração visual (GIF).

### O — Objetivo

Escrever o README final e um GIF de demonstração:

- exemplos com **saída real** do `ask` (uma pergunta respondida e uma recusada), não inventada;
- números da avaliação tirados dos relatórios versionados, com o critério de aceitação que **não** foi atingido
  (CA08, tempo médio) dito com clareza;
- seção de IA com o que a IA fez, o que a revisão humana mudou e os erros da própria IA, a partir do registro de
  uso mantido durante o projeto;
- GIF montado a partir da saída real, com prompt genérico (sem caminho local) e a espera encurtada **declarada**
  na animação e no README.

### S — Estilo

Markdown que o GitHub renderiza (tabelas, bloco `mermaid`), seções curtas, comandos copiáveis para Windows e
Linux/macOS.

### T — Tom

Profissional e honesto: resultados com números, limitações sem eufemismo.

### A — Audiência

O avaliador do mini-projeto; os colegas da especialização (o link do repositório vai ao fórum do curso), entre eles quem vai
comentar o projeto (tarefa do fórum); e qualquer pessoa que encontre o repositório no GitHub. Todos precisam
conseguir instalar e rodar só com o README (RNF02), sem conhecer o domínio jurídico.

### R — Resposta

`README.md` completo e `docs/img/demo.gif`.

## Resultado

README reescrito com as seções pedidas pela Unidade 5.2 e pelo checklist 5.3.1 (objetivo, como funciona,
tecnologias, instalação, uso, exemplos, testes, resultados, uso de IA, limitações, próximos passos, estrutura).

- **Exemplos reais:** as duas saídas foram capturadas rodando o `ask` em 08/10/2026 (pergunta respondida: 100 s;
  recusa: 1 s). Nada foi editado além da quebra de linha.
- **GIF:** montado por um script (Pillow, fora do repositório) a partir dessas saídas, com prompt genérico `$`; a
  espera foi encurtada e isso está escrito na animação e na legenda. Conferido: nenhum caminho local nos bytes do
  arquivo (303 KB, 58 quadros).
- **Números:** todos tirados de `eval/relatorios/` e de `docs/requisitos.md`; o CA08 (tempo médio ≤ 60 s) aparece
  como **não atingido** (60,5 s).
- **Conferência das afirmações:** uma frase do rascunho atribuía a escolha da busca híbrida a um problema com
  "art. 64-A" que nunca foi medido; foi retirada. Outras três foram corrigidas para os números exatos (CA05 em
  perguntas, não respostas; ~200 mutações; estimativa do 7b de 10–15 min contra 2–3,5 min medidos).
- **Seção de IA:** montada a partir do registro de uso mantido durante o projeto, incluindo dois erros da própria
  IA e um experimento com resultado negativo.

## Revisão humana

- [ ] A seção "Como a IA foi usada" representa bem a divisão de trabalho e as decisões que foram suas?
- [ ] Alguma informação do README não deveria estar pública?

_Alterações feitas após a revisão:_ (preencher)
