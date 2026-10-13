---
fase: 07-empacotamento-entrega
modulo: repositório inteiro (checklist de submissão, tag v1.0.0)
unidade_curso: "C04 — Unidade 5.1 (empacotamento) e 5.3 (checklist de submissão)"
data: 2026-10-13
ferramenta: Claude Code
modelo: Claude Sonnet 5.5 (claude-sonnet-5-5)
autoria: prompt escrito e executado pela IA, sob direção e revisão de Rodrigo Kobayashi
artefato_gerado: este registro; tag v1.0.0 (após a autorização do autor)
---

# Prompt 07.1 — Checklist de submissão final e versão 1.0.0

## Prompt (CO-STAR)

### C — Contexto

Projeto `rag-normas` com as fases 1 a 6 concluídas e enviadas ao GitHub (repositório público, 33 commits, 249 testes,
README final). O link do repositório vai ao fórum de discussão do curso (nota N5), onde todos os alunos da
especialização o leem; comentar o projeto de um colega também é tarefa do fórum. A Unidade 5.3.1 traz o checklist de
submissão final.

### O — Objetivo

Verificar **com comandos reais**, e não por memória, cada item do checklist 5.3.1, e só então marcar a versão:

1. repositório público e acessível; 2. README completo; 3. histórico de commits no padrão Conventional Commits, com
pelo menos cinco commits significativos; 4. arquivo de dependências com versões; 5. testes presentes, passando, com
instruções; 6. nenhuma credencial, nem caminho local, no código **nem no histórico**; 7. branch principal limpo;
8. release ou tag `v1.0.0`; 9. licença.

Prova de reprodutibilidade (RNF02): clonar o repositório **público** numa pasta nova, instalar só pelo README e rodar.

### S — Estilo

Resultado em tabela, cada linha com a evidência (o comando ou o número que a sustenta).

### T — Tom

Objetivo e honesto: o que não foi atingido aparece como não atingido.

### A — Audiência

O autor; o avaliador do curso; os colegas da especialização (o link vai ao fórum).

### R — Resposta

Tabela do checklist, lista do que ficou de fora e, após autorização do autor, a tag `v1.0.0` enviada ao GitHub.

## Resultado

| # | Item do checklist | Resultado | Evidência |
|---|---|---|---|
| 1 | Repositório público e acessível | ✅ | API do GitHub: `private: false`, `visibility: public`, página HTTP 200 |
| 2 | README completo e profissional | ✅ | seções de descrição, instalação, uso, tecnologias, IA, limitações e próximos passos; lido pelo autor em 13/10 |
| 3 | Histórico de commits consistente | ✅ | 33 commits, todos no padrão Conventional Commits (13 `docs`, 9 `feat`, 4 `chore`, 2 `style`, 2 `refactor`, 2 `fix`, 1 `test`); um só autor |
| 4 | Gerenciamento de dependências | ✅ | `requirements.txt` (`ollama==0.6.3`) e `requirements-dev.txt` (`pytest==9.1.1`, `ruff==0.16.10`), versões exatas |
| 5 | Testes automatizados | ✅ | 249 testes; no clone novo do repositório público: `249 passed`, `ruff check` sem apontamentos, formatação conferida |
| 6 | Credenciais e dados sensíveis | ✅ | varredura das 33 revisões: 0 chaves em formato conhecido, 0 caminhos locais; acertos em "secret" e "token" eram falsos positivos ("Secretaria", verbete do glossário); `.env` no `.gitignore` (o projeto não usa chaves) |
| 7 | Branch principal limpo | ✅ | `git status` limpo; só a branch `main`; 62 arquivos versionados, nenhum temporário |
| 8 | Release ou tag `v1.0.0` | ✅ | não existia nenhuma; tag anotada `v1.0.0` criada e enviada em 13/10/2026, com autorização do autor |
| 9 | Licença | ✅ | MIT, em nome do autor |

**Reprodutibilidade do usuário novo (RNF02):** clone do repositório público numa pasta nova, ambiente virtual novo,
`pip install -r requirements-dev.txt`, `python -m pytest -q` (249 passam), `python -m rag_normas index` (31 artigos em
52 s) e `ask` com pergunta fora das normas (recusa em 1 s). Pedido de pergunta sem índice: mensagem de erro com a
instrução de como criar e código de saída 1.

**Ressalva honesta.** O critério CA08 (tempo médio ≤ 60 s com o `qwen2.5:3b`) **não foi atingido**: 60,5 s. A decisão
do autor foi não alterar o critério depois de ver o resultado; o README informa o número.

**Observação.** O texto da IN RFB 2.091/2022 contém a expressão "Analista Tributário da Receita Federal" (quem pode
elaborar o relatório do arrolamento). É conteúdo legal do corpus e deve ser mantido como está.

## Revisão humana

- [x] O autor autoriza a criação da tag `v1.0.0` e o envio dela ao GitHub? (autorizado em 13/10/2026)
- [x] O autor quer criar também a *Release* (com notas) pela página do GitHub? O `gh` não está instalado. (sim; o texto das notas foi preparado pela IA e a criação da Release é feita pelo autor na página)

_Alterações feitas após a revisão:_ nenhuma.
