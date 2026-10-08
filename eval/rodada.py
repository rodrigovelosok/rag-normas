"""Execução de uma rodada: busca, chamada ao modelo de chat e gravação dos resultados (.jsonl).

As funções `embed`, `chat` e o relógio entram por parâmetro, então os testes rodam sem o Ollama.
Depende de `gabarito` e `metricas`.
"""

import json
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, replace
from pathlib import Path

from eval.gabarito import Question, QuestionsError
from eval.metricas import AnswerScore, article_recall, check_answer_text
from rag_normas.generate import ChatFn, answer
from rag_normas.index import Index
from rag_normas.ingest import Chunk
from rag_normas.search import EmbedFn, Hit, hybrid_search

# ---------- busca ----------


def retrieve(
    questions: Sequence[Question], index: Index, embed: EmbedFn, k: int, rrf_k: int = 60
) -> dict[str, list[Hit]]:
    """Busca os `k` artigos de cada pergunta. Não usa o modelo de chat."""
    return {q.id: hybrid_search(q.text, index.chunks, index.vectors, embed, k=k, rrf_k=rrf_k) for q in questions}


def make_search(index: Index, embed: EmbedFn) -> Callable[[Question, int, int], list[Hit]]:
    """Cria a função `search(pergunta, k, rrf_k)` usada na varredura da constante do RRF."""

    def search(question: Question, k: int, rrf_k: int) -> list[Hit]:
        return hybrid_search(question.text, index.chunks, index.vectors, embed, k=k, rrf_k=rrf_k)

    return search


# ---------- resposta ----------


def run_answer(
    question: Question,
    hits: Sequence[Hit],
    chat: ChatFn,
    index_chunks: list[Chunk],
    min_similarity: float,
    clock: Callable[[], float] = time.perf_counter,
) -> AnswerScore:
    """Responde uma pergunta como o `ask` faria e confere o resultado com o gabarito."""
    start = clock()
    result = answer(question.text, list(hits), chat, index_chunks, min_similarity)
    seconds = clock() - start

    found, missing, cited = check_answer_text(question, result.text, result.refused)
    return AnswerScore(
        id=question.id,
        group=question.group,
        kind=question.kind,
        refused=result.refused,
        best_similarity=max((hit.similarity for hit in hits), default=0.0),
        retrieval_recall=article_recall(question.articles, [hit.chunk.reference for hit in hits]),
        cited=cited,
        cited_recall=article_recall(question.articles, cited),
        invalid_citations=result.invalid_citations,
        items_found=found,
        items_missing=missing,
        seconds=seconds,
        text=result.text,
    )


def run_answers(
    questions: Sequence[Question],
    hits_by_id: Mapping[str, Sequence[Hit]],
    chat: ChatFn,
    index_chunks: list[Chunk],
    min_similarity: float,
    output: Path | None = None,
    resume: bool = False,
    on_progress: Callable[[int, int, AnswerScore], None] | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> list[AnswerScore]:
    """Roda as perguntas em ordem, gravando cada resultado em `output` assim que fica pronto.

    Com `resume`, as perguntas que já constam em `output` não são repetidas. Sem `resume`, o arquivo recomeça vazio.
    """
    done: dict[str, AnswerScore] = {}
    if output is not None:
        if resume:
            done = {score.id: score for score in load_scores(output)}
        else:
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            Path(output).write_text("", encoding="utf-8")

    scores = []
    for number, question in enumerate(questions, 1):
        if question.id in done:
            score = done[question.id]
        else:
            score = run_answer(question, hits_by_id[question.id], chat, index_chunks, min_similarity, clock)
            if output is not None:
                append_score(output, score)
        scores.append(score)
        if on_progress:
            on_progress(number, len(questions), score)
    return scores


def rescore(questions: Sequence[Question], scores: Sequence[AnswerScore]) -> list[AnswerScore]:
    """Reavalia respostas JÁ GRAVADAS com o gabarito atual, sem chamar o modelo.

    Serve quando o gabarito (expressões regulares) é corrigido depois de uma rodada: o texto de cada resposta está
    no arquivo de resultados, então itens e citações podem ser conferidos de novo. O que depende da execução
    (tempo, busca, citações inexistentes, recusa) não muda.

    Raises:
        QuestionsError: Se algum resultado tiver um id que não existe no gabarito.
    """
    by_id = {question.id: question for question in questions}
    updated = []
    for score in scores:
        question = by_id.get(score.id)
        if question is None:
            raise QuestionsError(f"o resultado de {score.id} não tem pergunta correspondente no gabarito")
        found, missing, cited = check_answer_text(question, score.text, score.refused)
        updated.append(
            replace(
                score,
                group=question.group,
                kind=question.kind,
                items_found=found,
                items_missing=missing,
                cited=cited,
                cited_recall=article_recall(question.articles, cited),
            )
        )
    return updated


# ---------- arquivos de resultados ----------


def append_score(path: Path, score: AnswerScore) -> None:
    """Acrescenta uma linha JSON ao arquivo de resultados (assim uma rodada interrompida não perde o que já fez)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(asdict(score), ensure_ascii=False) + "\n")
        file.flush()


def load_scores(path: Path) -> list[AnswerScore]:
    path = Path(path)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [AnswerScore(**json.loads(line)) for line in lines if line.strip()]


def save_scores(path: Path, scores: Sequence[AnswerScore]) -> None:
    """Grava todos os resultados de uma vez, uma linha JSON por pergunta (substitui o arquivo)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = (json.dumps(asdict(score), ensure_ascii=False) + "\n" for score in scores)
    path.write_text("".join(lines), encoding="utf-8")
