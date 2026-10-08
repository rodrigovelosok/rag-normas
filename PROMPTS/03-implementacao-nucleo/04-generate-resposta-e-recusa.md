---
fase: 03-implementacao-nucleo
modulo: rag_normas/generate.py
unidade_curso: "C04 — Unidade 3 (Implementação do núcleo)"
data: 2026-10-08
ferramenta: Claude Code
modelo: Claude Sonnet 5.5 (claude-sonnet-5-5)
autoria: prompt escrito e executado pela IA, sob direção e revisão de Rodrigo Kobayashi
artefato_gerado: rag_normas/generate.py, tests/test_generate.py
---

# Prompt 03.4 — `generate.py`: prompt, recusa, citações e saída

## Prompt (CO-STAR)

### C — Contexto

Projeto `rag-normas`. Já existem `ingest.py` (`Chunk`, com `.reference`), `search.py` (`Hit` com `chunk`,
`similarity`, `bm25`, `score`; `hybrid_search` devolve os hits **ordenados pelo RRF**, não pela similaridade),
`config.py` (`min_similarity`, provisório em 0,52), `llm.py` e `index.py` (88 testes passando). Falta o módulo que
transforma artigos recuperados em resposta, aplicando os guardrails: G1 (citar o artigo), G2 (recusar sem base:
*"Não encontrei isso nas normas carregadas."*) e G3 (aviso fixo no fim). Decisões já tomadas: `generate.py` **não
importa `ollama`**; recebe `chat` como função (D4, D5); citação no formato fixo `[Fonte: <norma>, art. N]` (D6).

Dois pontos que a arquitetura deixou em aberto e que este módulo precisa resolver:

1. **Critério de recusa (RF07).** O RRF não dá nota absoluta, e a pontuação BM25 não serve de sinal de recusa
   (qualquer palavra em comum já pontua). A única medida absoluta disponível é a similaridade de cosseno.
2. **Escopo da verificação de citações (RF10).** Mínimo: o artigo citado existe no índice. Mais forte: está entre
   os recuperados.

### O — Objetivo

Testes primeiro (`tests/test_generate.py`), depois `rag_normas/generate.py` com:

- constantes `REFUSAL_MESSAGE` e `DISCLAIMER` com os textos exatos de G2 e G3;
- `build_messages(question, hits)`: devolve a lista `[{"role": "system", ...}, {"role": "user", ...}]`. O prompt de
  sistema manda usar **só** os fragmentos, citar com o rótulo exato `[Fonte: ...]` após cada afirmação e responder a
  frase de recusa quando os fragmentos não bastarem. A mensagem do usuário traz cada fragmento sob seu rótulo e, por
  fim, a pergunta;
- `extract_citations(text)`: referências citadas no formato `[Fonte: ...]`, sem repetição, na ordem de aparição,
  tolerando espaços a mais e o sinal `°` no lugar de `º`;
- `answer(question, hits, chat, index_chunks, min_similarity)`: **recusa sem chamar o chat** se não houver hits ou
  se a **maior similaridade entre os hits** ficar abaixo do limiar (igual ao limiar não recusa); senão chama o chat,
  trata como recusa a resposta que for exatamente a frase de G2, e confere as citações (RF10). Devolve um
  `Answer` imutável com: texto, se recusou, fontes consultadas, citações inexistentes no índice, citações
  existentes mas não recuperadas (só para medir na Fase 4) e se faltou citação;
- `format_output(answer)`: texto + fontes consultadas (RF06) + avisos de problema + `DISCLAIMER` sempre por último.

### S — Estilo

Python 3.14, PEP 8, *type hints*, *docstrings* no formato Google, nomes em inglês, mensagens em português. Só
biblioteca padrão. Testes com `chat` falso que grava as chamadas, para provar quando o chat **não** foi chamado.

### T — Tom

O prompt de sistema é direto e impessoal. Os avisos de problema são curtos, sem alarmismo, e dizem o que o
leitor deve fazer ("confira na norma").

### A — Audiência

O modelo `qwen2.5:3b` (leitor do prompt de sistema, um modelo pequeno que precisa de regras explícitas e curtas) e,
na saída, quem usa o terminal, que não deve ser induzido a confiar em citação não verificada.

### R — Resposta

Dois arquivos (módulo e testes). Testes falham antes e passam depois; depois, teste de mutação e um teste de
realidade com o Ollama.

## Resultado

Gerados `generate.py` e `tests/test_generate.py` (28 testes; 117 no total depois do ajuste de prompt abaixo).
Ciclo TDD: vermelho (módulo inexistente), verde na primeira execução. **Teste de mutação: 21 alterações
propositais, todas detectadas** (duas precisaram ser refeitas porque meu script de mutação escapava mal as
quebras de linha; o defeito era do script, não do código).

**Achado do teste com o Ollama real (o mais importante desta etapa).** Na primeira versão, o prompt de sistema
ensinava ao modelo a frase de recusa ("se os fragmentos não responderem, responda exatamente: ..."). Resultado com o
`qwen2.5:3b`: perguntas que a norma responde (valor mínimo de débitos; venda de imóvel arrolado) passaram do
limiar de similaridade e o **próprio modelo recusou**. Experimento controlado (mesma pergunta, mesmos artigos, só o
prompt mudando):

| Variante do prompt | Resposta do modelo |
|---|---|
| A. regra de recusa ("se não responderem, diga X") | recusou (errado) |
| C. recusa "somente se NENHUM fragmento tratar do assunto" | recusou (errado) |
| G. C com a pergunta antes dos fragmentos | recusou (errado) |
| **E. sem regra de recusa** | **respondeu, citando `[Fonte: IN RFB 2.091/2022, art. 2º]`** |
| H. instruções em inglês, com regra de recusa | respondeu, mas sem o formato `[Fonte: ...]` |

**Decisão:** retirar do prompt qualquer regra de recusa; quem recusa é o código (limiar de similaridade, D10). Um
teste (`test_system_prompt_does_not_teach_the_refusal_phrase`) impede que a regra volte sem querer. Efeito colateral
a medir na Fase 4: sem a segunda barreira do modelo, perguntas fora do corpus que passarem do limiar podem receber
resposta; e a resposta do 3b trouxe um erro de leitura ("30% **somado a** R$ 2 milhões", quando a norma diz que
ambos os limites são exigidos simultaneamente). Ambos entram no conjunto de avaliação.

**Segundo achado: o formato da citação.** Já sem a regra de recusa, o modelo respondia, mas citava em texto corrido
("conforme o art. 2º da IN RFB 2.091/2022") e não no formato `[Fonte: ...]` que a verificação lê; o aviso "sem
citação" disparava em todas. Novo experimento (pergunta "Quem pode pedir o cancelamento do arrolamento?", 4
artigos): repetir a exigência **no fim da mensagem do usuário** (lembrete) fez o modelo usar o formato; o
lembrete mais um exemplo de resposta também funcionou, mas custa mais tokens, então ficou só o lembrete.

**Terceiro achado: o modelo cita com mais precisão que o índice.** Passou a escrever `art. 11, § 5º` ou
`art. 64, § 3º`. A verificação exata trataria isso como artigo inexistente (alarme falso). A conferência passou a
ser **por artigo**, ignorando parágrafo, inciso e o "º" (`_article_key`), sem deixar `art. 64` valer por `art. 64-A`.
Também reescrevi o aviso para dizer exatamente o que falta ("nenhuma citação no formato [Fonte: ...]").

**Mutação final:** 27 alterações propositais, 27 detectadas (a rodada anterior deixou sobreviver o caso `[Fonte: ]`
vazio; virou teste). Suíte: 124 testes.

**Teste de realidade final (4 perguntas, código definitivo):**

| Pergunta | Resultado |
|---|---|
| Valor mínimo de débitos | respondeu com `[Fonte: ... art. 2º]`; **erro de conteúdo**: diz "soma de 30% do patrimônio e R$ 2.000.000", quando a norma exige que a dívida exceda *simultaneamente* os dois limites. O Decreto (D9) não foi recuperado |
| Alíquota do IRPF (fora do corpus) | recusou pelo limiar (0,49 < 0,52), sem chamar o modelo (0,2 s) |
| Vender imóvel arrolado | respondeu corretamente, `[Fonte: Lei 9.532/1997, art. 64, § 3º]` |
| Quem pode pedir o cancelamento | resposta correta mas **incompleta** (só a autoridade da RFB; faltou o sujeito passivo) |

**Latência:** 16 a 21 s por resposta, dentro da meta de 60 s do RNF04. Nas rodadas de experimento, a mesma
chamada chegou a levar 40 a 125 s; a variação grande indica competição por memória/CPU na máquina (o `ollama ps`
mostra os dois modelos carregados) e precisa ser medida com cuidado na Fase 4, com o modelo já carregado.

**Para a Fase 4:** (1) o 3b erra a leitura de "simultaneamente"; (2) o k=4 não recupera o Decreto na pergunta do
valor mínimo; (3) respostas corretas, porém incompletas, não aparecem em nenhuma métrica de citação: o conjunto de
avaliação precisa conferir também o conteúdo esperado (artigos que *deveriam* ser citados).

Decisões da IA além do pedido: resolver os dois pontos em aberto da arquitetura (D10, D11) e listar como fontes os
artigos **consultados**, e não só os citados (D12); registrar também as citações "existentes mas não recuperadas"
(`unretrieved_citations`), sem alertar o usuário, para medir depois o efeito da verificação mais forte.

## Revisão humana

- [ ] O critério de recusa (só similaridade) é compreensível e a decisão está documentada?
- [ ] O prompt de sistema está claro para um modelo pequeno?
- [ ] A saída deixa evidente quando uma citação não pôde ser verificada?

_Observação:_ o prompt acima é o **pedido original**. O que ele pedia sobre a frase de recusa no prompt de sistema
foi desfeito depois do teste real (ver "Resultado"); o código final difere do pedido nesse ponto, de propósito.

_Alterações feitas após a revisão:_ (preencher)
