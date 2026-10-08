# Glossário do projeto

Vocabulário técnico usado em `rag-normas`, explicado em linguagem simples. Cada termo diz **o que é**, **onde aparece
no projeto** e, quando ajuda, traz uma **analogia**. Termos em inglês aparecem entre parênteses porque é como se
pesquisa sobre eles.

## 1. O problema e a ideia geral

**RAG (Retrieval-Augmented Generation, "geração aumentada por busca")**
Técnica em que o sistema primeiro **busca** trechos relevantes num acervo e só depois pede a um modelo de linguagem
que **escreva a resposta** com base neles. *Analogia:* prova com consulta. Em vez de responder de memória, o aluno
abre o livro na página certa e responde citando-a. É o que o projeto inteiro faz.

**LLM (Large Language Model, "modelo de linguagem")**
Programa treinado em muito texto que escreve texto novo prevendo a palavra seguinte. Aqui, o `qwen2.5:3b` (modelo de
chat) roda no seu computador, via Ollama. Escreve bem, mas **não sabe distinguir o que sabe do que está inventando**.

**Alucinação (hallucination)**
Resposta que soa correta e confiável, mas foi inventada pelo modelo. É o principal risco que o projeto combate: por
isso existem a recusa, a citação obrigatória e a verificação das citações.

**Ancoragem (grounding)**
Obrigar a resposta a se apoiar em fontes concretas. O RAG ancora a resposta nos artigos recuperados. Ancorar mostra
*de onde veio* a resposta, mas não garante que a fonte esteja certa.

**Ollama**
Programa que roda modelos de IA localmente, sem enviar nada para a internet. Fala com o resto do sistema por um
endereço local (`http://localhost:11434`). Só o arquivo `llm.py` conhece o Ollama.

**MVP (Minimum Viable Product, "produto mínimo viável")**
A menor versão que já entrega valor e pode ser avaliada. O `rag-normas` v1.0 é o MVP do curso.

## 2. Os dados

**Corpus**
O conjunto de textos sobre o qual o sistema responde. Aqui: 3 normas (IN RFB 2.091/2022, Lei 9.532/1997 arts. 64 e
64-A, Decreto 7.573/2011), 31 artigos ao todo, na pasta `data/normas/`. *Analogia:* os autos de um processo. O que não
está nos autos não existe para quem decide.

**Chunk ("pedaço")**
Cada fragmento em que o corpus é dividido para a busca. Aqui, **um chunk = um artigo** (com parágrafos e incisos).
Está em `ingest.py` (classe `Chunk`). Chunks pequenos demais perdem o contexto; grandes demais diluem o assunto.

**Proveniência (provenance)**
O registro de **de onde veio** cada dado e como foi tratado. Está em `data/normas/FONTES.md`. *Analogia:* a cadeia de
documentos que prova a origem de um bem.

**Texto consolidado**
Texto da norma já com todas as alterações posteriores aplicadas (a IN 2.091 foi alterada pelas INs 2.122/2022 e
2.338/2026). Um texto original, sem as alterações, daria respostas desatualizadas.

**Índice (index)**
O arquivo `data/index.json`, que guarda cada artigo junto com seu vetor, para não ter de recalcular tudo a cada
pergunta. É gerado pelo comando `index` e demora cerca de 1 minuto nesta máquina.

## 3. Como a busca funciona

**Embedding (vetor de significado)**
Lista de números (aqui, 1.024) que representa o **significado** de um texto, gerada por um modelo (`bge-m3`). Textos
com assuntos parecidos geram listas parecidas, mesmo com palavras diferentes. *Analogia:* coordenadas de GPS, mas de
assuntos em vez de lugares.

**Similaridade do cosseno (cosine similarity)**
Mede o ângulo entre dois vetores. Vai de -1 a 1; quanto mais perto de 1, mais parecidos os assuntos. Está em
`search.py` (`cosine`). **Não é uma porcentagem de acerto:** só serve para comparar.

**BM25**
Busca por **palavras**: pontua o artigo conforme quantas palavras da pergunta ele contém, dando mais peso às palavras
raras (por exemplo, "arrolamento" vale mais que "de"). Complementa o embedding, que às vezes perde termos exatos como
um número de artigo.

**Busca híbrida (hybrid search)**
Usar **duas buscas ao mesmo tempo** (por significado e por palavras) e juntar os resultados. Cada uma cobre a
fraqueza da outra.

**RRF (Reciprocal Rank Fusion, "fusão por posição")**
Jeito de juntar dois rankings usando só a **posição**: cada lista dá ao artigo `1 / (k + posição)` pontos e os pontos
se somam. Não precisa converter pontuações de escalas diferentes. *Analogia:* dois jurados que ordenam os candidatos;
vence quem fica bem colocado nas duas listas. Não serve para dizer se a resposta é boa, só quem está na frente.

**top-k**
Quantos artigos a busca entrega ao modelo (padrão: `k = 4`). Poucos podem deixar a resposta sem o artigo necessário;
muitos enchem o contexto e confundem o modelo.

**Limiar (threshold)**
Valor de corte: acima dele o sistema faz uma coisa, abaixo faz outra. Aqui, `min_similarity` (0,52, provisório): se
o melhor artigo ficar abaixo disso, o sistema recusa em vez de responder.

**Calibração**
Escolher o valor de um parâmetro (como o limiar) **medindo**, em vez de chutar. A Fase 4 faz isso com perguntas de
teste.

## 4. O modelo de chat

**Prompt**
O texto enviado ao modelo. Aqui há dois: a **instrução de sistema** (regras fixas de comportamento) e a mensagem do
usuário (artigos recuperados + pergunta). Está em `generate.py`.

**CO-STAR**
Roteiro para escrever prompts: **C**ontexto, **O**bjetivo, **E**stilo, **T**om, **A**udiência, **R**esposta. Os
prompts usados para *construir* o projeto estão em `PROMPTS/`.

**Janela de contexto (`num_ctx`)**
Quanto texto o modelo consegue "ler" de uma vez, medido em tokens. O padrão do Ollama (4.096) cortaria artigos
longos; por isso o projeto usa 8.192.

**Token**
Pedaço de palavra que o modelo usa como unidade. Em português, 1 token vale cerca de 3 a 4 caracteres.

**Temperatura**
Controla o quanto o modelo varia a resposta. Com `0`, a mesma pergunta dá a mesma resposta, o que torna os testes de
avaliação comparáveis.

**Guardrail ("trilho de proteção")**
Regra que limita o comportamento do sistema para evitar erros previsíveis. Aqui são três: G1 (sempre citar o artigo),
G2 (sem base, recusar) e G3 (aviso fixo no fim).

**Recusa**
A resposta padrão *"Não encontrei isso nas normas carregadas."* quando não há base suficiente. Responder "não sei" é
parte do bom comportamento, não uma falha.

**Citação verificada**
Depois que o modelo responde, o código confere se cada `[Fonte: ..., art. N]` citado **existe de fato** no índice. O
modelo pode inventar uma citação; o programa não confia nele, confere.

## 5. Como o código é organizado

**Módulo**
Um arquivo `.py` com uma responsabilidade (`ingest.py` lê as normas, `search.py` busca, `index.py` grava o índice…).

**Camada de isolamento / adaptador (adapter)**
Um único módulo que fala com algo externo, para o resto não depender dele. `llm.py` é o adaptador do Ollama: trocar
de ferramenta mexe só nele.

**Injeção de dependência (dependency injection)**
Em vez de um módulo criar o que precisa, ele **recebe** pronto por parâmetro. `hybrid_search` recebe a função
`embed`, e não importa o Ollama. Assim, nos testes, passamos uma versão falsa.

**Função como parâmetro (callable)**
Em Python, funções podem ser passadas como valores. `embed` e `chat` são assim: o resto do sistema as chama sem saber
como funcionam por dentro.

**`dataclass` imutável (`frozen=True`)**
Classe feita só para guardar dados (`Chunk`, `Hit`, `Settings`). Sendo imutável, ninguém a altera por engano.

**Variável de ambiente**
Configuração que mora fora do código, no sistema (`RAG_TOP_K=6`). Permite ajustar o programa sem editar arquivos.

**CLI (Command-Line Interface)**
Programa usado pelo terminal, com comandos como `index` e `ask`.

**Exceção (exception)**
Mecanismo do Python para sinalizar erro. Criamos exceções próprias (`LLMError`, `IndexFileError`, `ConfigError`)
cujas mensagens dizem *o que aconteceu* e *o que fazer*.

**Gravação atômica**
Gravar num arquivo temporário e só depois trocá-lo pelo definitivo. Se faltar luz no meio, o arquivo antigo continua
inteiro.

## 6. Testes e qualidade

**Teste unitário (unit test)**
Teste automático de uma função pequena, isolada, sem depender de internet nem do Ollama. Rodam em segundos
(`pytest`).

**Dublê de teste: *fake* e *mock***
Versão falsa de algo real, usada nos testes. Um *fake* funciona de forma simplificada (um `embed` que devolve vetores
fixos); um *mock* também registra como foi chamado. Permitem testar sem o Ollama.

**TDD (Test-Driven Development)**
Escrever o **teste primeiro**, vê-lo falhar (*vermelho*), escrever o código mínimo para passar (*verde*) e depois
melhorar o código (*refatorar*).

**Cobertura vs. força do teste**
Um teste pode executar uma linha sem realmente conferir seu resultado. Cobertura de 100% não prova que os testes
detectam erros.

**Teste de mutação (mutation testing)**
Estraga o código de propósito (troca `<` por `<=`, remove uma linha) e confere se algum teste **falha**. Se nenhum
falhar, o teste era fraco. Cada alteração é um *mutante*; o mutante que passa despercebido *sobreviveu*.

**Mutante equivalente**
Alteração que não muda o comportamento do programa; por isso nenhum teste poderia detectá-la. Não indica teste fraco.

**Teste de avaliação (eval)**
Mede a **qualidade das respostas** com perguntas reais e resposta esperada (acerto, recusa correta, citações
válidas). Diferente do teste unitário, depende do Ollama. É a Fase 4.

**Falso positivo / falso negativo**
Dois jeitos de errar numa decisão sim/não. No limiar de recusa: responder o que devia recusar (um tipo de erro) ou
recusar o que devia responder (o outro).

**Precisão e revocação (precision / recall)**
Medidas formais desses erros. Precisão: das respostas dadas, quantas estavam certas. Revocação: das que deviam ser
dadas, quantas foram.

## 7. Processo e documentação

**Requisito funcional (RF) e não funcional (RNF)**
RF diz **o que** o sistema faz ("recusar quando não houver base"). RNF diz **como** ele deve ser (rodar offline,
código legível, testável). Estão em `docs/requisitos.md`.

**Critério de aceitação (CA)**
Condição mensurável para considerar um requisito cumprido ("≥ 90% das perguntas fora do corpus são recusadas").

**Matriz de rastreabilidade**
Tabela que liga cada requisito ao critério e ao teste que o verifica. Mostra que nada ficou sem conferência.

**Registro de decisão (ADR — Architecture Decision Record)**
Anotar uma decisão, as alternativas descartadas e o motivo. A tabela D1–D10 em `docs/arquitetura.md` segue essa ideia.

**Conventional Commits**
Padrão de mensagem de commit (`feat:`, `fix:`, `docs:`, `test:`) que torna o histórico legível.

**Commit atômico**
Commit que contém **uma** mudança lógica, de modo que o histórico conte a história passo a passo.
