# Especificação de requisitos — `rag-normas` v1.0

> Gerado pelo prompt [`PROMPTS/01-ideacao-requisitos/01-especificacao-de-requisitos.md`](../PROMPTS/01-ideacao-requisitos/01-especificacao-de-requisitos.md)
> e revisado pelo autor.

## 1. Visão do produto

O `rag-normas` é um assistente de linha de comando que responde perguntas sobre a legislação federal de
**arrolamento de bens e direitos**. Toda resposta vem acompanhada do artigo da norma de onde foi tirada.
Tudo roda localmente: o texto das normas e as perguntas nunca saem da máquina.

**Usuário-alvo:** servidor ou estudante que precisa localizar rapidamente o que a norma diz durante uma
análise, sem ler a instrução normativa inteira.

**Corpus da v1.0:**

- Instrução Normativa RFB nº 2.091/2022, texto consolidado;
- Lei nº 9.532/1997, arts. 64 e 64-A;
- Decreto nº 7.573/2011, que eleva para R$ 2.000.000,00 o limite do § 7º do art. 64 da Lei 9.532/1997
  (incluído em 08/10/2026).

**Exemplos de perguntas:**

- "Em que situação o arrolamento de bens é realizado?"
- "O proprietário precisa comunicar a venda de um bem arrolado?"
- "Quais bens podem ser arrolados?"

**Como funciona, em uma linha:** a pergunta é comparada com os artigos indexados (busca híbrida). Os
artigos mais relevantes vão para o modelo de linguagem, que redige a resposta usando **somente** esses
trechos e citando cada um.

## 2. Requisitos funcionais

| ID | Requisito |
|---|---|
| RF01 | O sistema deve ler os textos das normas a partir de arquivos em `data/normas/` e dividi-los em fragmentos de **um artigo cada**, mantendo os parágrafos e incisos junto do artigo a que pertencem. |
| RF02 | Cada fragmento deve guardar sua referência: norma e número do artigo (ex.: `IN RFB 2.091/2022, art. 5º`). |
| RF03 | O sistema deve oferecer o comando `index`, que gera os embeddings dos fragmentos e o índice BM25 e grava tudo num arquivo JSON. |
| RF04 | O sistema deve oferecer o comando `ask "<pergunta>"`, que recupera os *k* fragmentos mais relevantes (padrão *k* = 4) por busca vetorial e BM25, fundidas por Reciprocal Rank Fusion (RRF). |
| RF05 | O sistema deve gerar a resposta com o modelo de chat, usando como base **apenas** os fragmentos recuperados. |
| RF06 | Abaixo de cada resposta, o sistema deve listar as fontes usadas (referência de cada fragmento). |
| RF07 | Quando nenhum fragmento atingir o limiar mínimo de relevância, o sistema deve responder com a mensagem padrão de recusa (ver G2) em vez de gerar texto. |
| RF08 | O modelo de chat, o *k* e o endereço do Ollama devem ser configuráveis por variável de ambiente ou opção da linha de comando. |
| RF09 | O sistema deve oferecer um script de avaliação que roda o conjunto de perguntas de `eval/` e informa as métricas dos critérios de aceitação. |
| RF10 | Depois da geração, o sistema deve **conferir se todo artigo citado na resposta existe no índice** e sinalizar a resposta quando não existir. |

## 3. Requisitos não funcionais

| ID | Requisito |
|---|---|
| RNF01 | **Execução local:** nenhuma chamada a serviço externo nem chave de API; só o Ollama na própria máquina. |
| RNF02 | **Reprodutibilidade:** um usuário novo instala e roda seguindo só o README, com `requirements.txt`. Testado em Python 3.14. |
| RNF03 | **Testes independentes do modelo:** a suíte de testes unitários roda sem Ollama instalado (modelo simulado) em menos de 30 segundos. |
| RNF04 | **Latência:** com `qwen2.5:3b` em CPU, a resposta deve chegar em até 60 segundos (meta medida pelo script de avaliação). |
| RNF05 | **Código:** Python com nomes em inglês, PEP 8, *type hints* e *docstrings* no formato Google. |
| RNF06 | **Dependências mínimas:** sem framework de orquestração (LangChain etc.) e sem banco vetorial. |
| RNF07 | **Dados:** o repositório contém só textos normativos de domínio público (Lei 9.610/1998, art. 8º, IV); nenhum dado de contribuinte. |

## 4. Regras de segurança da resposta (guardrails)

| ID | Regra |
|---|---|
| G1 | Toda afirmação da resposta cita o artigo que a sustenta. |
| G2 | Sem base nos fragmentos, a resposta é exatamente: *"Não encontrei isso nas normas carregadas."* Nada de chute. |
| G3 | Toda saída termina com o aviso fixo: *"Ferramenta de estudo. Não substitui a leitura da norma nem constitui parecer."* |

## 5. Critérios de aceitação

As metas da v1.0 são estimativas iniciais e serão recalibradas com os primeiros dados da Fase 4.

| ID | Critério | Meta | Como verificar |
|---|---|---|---|
| CA01 | A divisão em artigos reconhece todos os artigos do corpus, sem fundir nem quebrar artigos. | 100% | Teste unitário: contagem de artigos por norma = contagem conferida à mão |
| CA02 | Parágrafos e incisos ficam no fragmento do seu artigo. | 100% | Teste unitário com trecho de exemplo |
| CA03 | Para as perguntas do conjunto de avaliação, o artigo esperado aparece entre as *k* fontes recuperadas. | ≥ 80% | Script de avaliação (taxa de acerto da recuperação) |
| CA04 | Perguntas fora do corpus (ex.: "qual a alíquota do IRPF?") recebem a recusa G2. | ≥ 90% | Script de avaliação |
| CA05 | Nenhuma resposta cita artigo inexistente no índice. | 100% | RF10 aplicado a todas as respostas do conjunto de avaliação |
| CA06 | Toda saída contém o aviso G3. | 100% | Teste unitário da formatação da saída |
| CA07 | A suíte de testes unitários passa sem Ollama instalado. | 100% | `pytest` numa máquina sem Ollama |
| CA08 | O tempo médio de resposta com `qwen2.5:3b` fica no limite do RNF04. | ≤ 60 s | Script de avaliação |
| CA09 | A comparação 3b × 7b é reportada (acerto e tempo). | relatório gerado | Script de avaliação com `--model` |

## 6. Fora de escopo da v1.0

- Interface web (Streamlit/Gradio): fica nos próximos passos do README.
- Medida cautelar fiscal (Lei 8.397/1992) e qualquer outra norma além do corpus da seção 1. (O capítulo da IN
  sobre a representação para a cautelar **está** no corpus, porque faz parte do texto da IN.)
- Conversa com várias perguntas encadeadas (memória de diálogo).
- Versões históricas da norma (só o texto consolidado vigente).
- Qualquer dado de contribuinte, real ou fictício.
- Parecer ou interpretação jurídica: o sistema só localiza e resume o texto.

## 7. Glossário

- **RAG (Retrieval-Augmented Generation):** técnica que primeiro *busca* trechos relevantes e depois pede
  ao modelo que *gere* a resposta com base neles.
- **Embedding:** vetor de números que representa o significado de um texto; textos parecidos têm vetores
  próximos.
- **BM25:** busca por palavras, que dá mais peso aos termos raros.
- **RRF (Reciprocal Rank Fusion):** forma de juntar dois rankings somando 1/(k + posição) de cada item.
- **Mock:** objeto que imita o modelo de linguagem nos testes, devolvendo uma resposta fixa.

## 8. Rastreabilidade

| Requisito | Critério(s) |
|---|---|
| RF01, RF02 | CA01, CA02 |
| RF03, RF04 | CA03 |
| RF05, G1 | CA05 |
| RF07, G2 | CA04 |
| RF10 | CA05 |
| G3 | CA06 |
| RF09 | CA03, CA04, CA05, CA08, CA09 |
| RNF03 | CA07 |
| RNF04 | CA08 |
