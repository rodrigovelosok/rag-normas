"""Geração da resposta: monta o prompt, aplica a recusa, confere as citações e formata a saída.

Este módulo NÃO conhece o Ollama: recebe a função `chat` pronta (docs/arquitetura.md, D4 e D5).
Implementa os guardrails G1 (citar o artigo), G2 (recusar sem base) e G3 (aviso fixo) e o RF10.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from rag_normas.ingest import Chunk
from rag_normas.search import Hit

ChatFn = Callable[[list[dict[str, str]]], str]

REFUSAL_MESSAGE = "Não encontrei isso nas normas carregadas."  # G2
DISCLAIMER = "Ferramenta de estudo. Não substitui a leitura da norma nem constitui parecer."  # G3

# Atenção: o prompt NÃO ensina ao modelo a frase de recusa. Em teste com o qwen2.5:3b, qualquer regra do tipo
# "se os fragmentos não responderem, diga X" fez o modelo recusar também perguntas que a norma responde
# (PROMPTS/03-implementacao-nucleo/04-generate-resposta-e-recusa.md). Quem decide recusar é o código, pelo limiar.
SYSTEM_PROMPT = """Você responde perguntas sobre normas brasileiras de arrolamento de bens, usando apenas os fragmentos fornecidos.

Como responder:
- Leia os fragmentos e responda à pergunta com o que eles dizem, em português, em poucas frases.
- Depois de cada afirmação, cite o fragmento copiando o rótulo exatamente como aparece.
  Exemplo de formato: [Fonte: Norma Exemplo, art. 1º]
- Se dois fragmentos tratarem do mesmo ponto de formas diferentes, mencione os dois, cada um com sua citação.
- Não dê opinião nem parecer."""

# Lembrete no FIM da mensagem do usuário: com 4 artigos (~3.000 tokens), o qwen2.5:3b esquecia o formato da
# citação dado no início; repetido no fim, passou a segui-lo (mesmo arquivo de PROMPTS citado acima).
REMINDER = "Responda em poucas frases e coloque [Fonte: ...] depois de cada afirmação, copiando o rótulo do fragmento."

# Pega o que está entre "[Fonte:" e o primeiro "]". `[^\]]*` = qualquer coisa que não seja "]",
# o que impede a captura de atravessar dois colchetes seguidos.
CITATION = re.compile(r"\[Fonte:([^\]]*)\]")

# Parte da referência até o número do artigo: "Lei 9.532/1997, art. 64-A, § 3º" -> "Lei 9.532/1997, art. 64-A".
ARTICLE_PART = re.compile(r"^(.*?,\s*art\.\s*\d+(?:-[A-Z])?)", re.IGNORECASE)


@dataclass(frozen=True)
class Answer:
    """O resultado de uma pergunta, já conferido.

    Attributes:
        text: Texto da resposta (ou a frase de recusa).
        refused: True se o sistema recusou (G2).
        sources: Referências dos artigos que o modelo recebeu (RF06); vazio na recusa.
        invalid_citations: Citadas na resposta, mas cujo artigo NÃO existe no índice (RF10). O modelo inventou.
        unretrieved_citations: Citadas e existentes no índice, mas que não estavam entre os artigos
            recuperados. Não vira aviso; fica registrado para a Fase 4 medir quantas respostas
            a verificação mais forte reprovaria.
        uncited: True se a resposta não traz nenhuma citação no formato `[Fonte: ...]` (viola G1).
    """

    text: str
    refused: bool
    sources: list[str]
    invalid_citations: list[str]
    unretrieved_citations: list[str]
    uncited: bool


def build_messages(question: str, hits: list[Hit]) -> list[dict[str, str]]:
    """Monta as mensagens para o modelo: regras (sistema) e fragmentos + pergunta + lembrete (usuário)."""
    fragments = "\n\n".join(f"[Fonte: {hit.chunk.reference}]\n{hit.chunk.text}" for hit in hits)
    user = f"Fragmentos das normas:\n\n{fragments}\n\nPergunta: {question}\n\n{REMINDER}"
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def extract_citations(text: str) -> list[str]:
    """Lista as referências citadas no formato `[Fonte: ...]`, sem repetição e na ordem em que aparecem.

    Tolera espaços a mais e o sinal "°" (grau) no lugar de "º" (ordinal), erro comum em modelos pequenos.
    """
    found: list[str] = []
    for raw in CITATION.findall(text):
        reference = " ".join(raw.split()).replace("°", "º")
        if reference and reference not in found:
            found.append(reference)
    return found


def answer(
    question: str,
    hits: list[Hit],
    chat: ChatFn,
    index_chunks: list[Chunk],
    min_similarity: float,
) -> Answer:
    """Responde à pergunta com base nos artigos recuperados, ou recusa.

    Args:
        question: A pergunta do usuário.
        hits: Artigos recuperados por `hybrid_search` (ordenados pelo RRF).
        chat: Função que envia mensagens ao modelo e devolve o texto.
        index_chunks: Todos os artigos do índice, para conferir se as citações existem (RF10).
        min_similarity: Limiar de recusa. Compara-se com a MAIOR similaridade entre os hits, porque
            os hits vêm ordenados pelo RRF, e não pela similaridade.
    """
    if not hits or max(hit.similarity for hit in hits) < min_similarity:
        return _refusal()

    reply = chat(build_messages(question, hits)).strip()
    if reply == REFUSAL_MESSAGE:  # o modelo não é instruído a isso, mas, se disser a frase exata, vale como recusa
        return _refusal()

    cited = extract_citations(reply)
    in_index = {article_key(chunk.reference) for chunk in index_chunks}
    retrieved = {article_key(hit.chunk.reference) for hit in hits}
    return Answer(
        text=reply,
        refused=False,
        sources=[hit.chunk.reference for hit in hits],
        invalid_citations=[ref for ref in cited if article_key(ref) not in in_index],
        unretrieved_citations=[
            ref for ref in cited if article_key(ref) in in_index and article_key(ref) not in retrieved
        ],
        uncited=not cited,
    )


def format_output(result: Answer) -> str:
    """Texto final para o terminal: resposta, fontes consultadas, avisos e, sempre por último, o aviso G3."""
    parts = [result.text]
    if result.sources:
        parts.append("Fontes consultadas:\n" + "\n".join(f"- {source}" for source in result.sources))
    if result.invalid_citations:
        cited = "; ".join(result.invalid_citations)
        parts.append(f"ATENÇÃO: a resposta cita artigo que não consta no índice ({cited}). Não confie nessa citação; confira na norma.")
    if result.uncited:
        parts.append("ATENÇÃO: a resposta não traz nenhuma citação no formato [Fonte: ...]. Confira nas fontes consultadas antes de usar.")
    parts.append(DISCLAIMER)
    return "\n\n".join(parts)


def article_key(reference: str) -> str:
    """Identifica o artigo de uma referência, ignorando parágrafo, inciso e o "º".

    O modelo cita com mais precisão do que o índice ("art. 11, § 6º"); a conferência é por artigo, então
    "art. 11, § 6º" vale como "art. 11". Sem o padrão esperado, a referência inteira é a chave (e não casará).
    """
    match = ARTICLE_PART.match(reference)
    return (match.group(1) if match else reference).lower()


def _refusal() -> Answer:
    return Answer(REFUSAL_MESSAGE, refused=True, sources=[], invalid_citations=[], unretrieved_citations=[], uncited=False)
