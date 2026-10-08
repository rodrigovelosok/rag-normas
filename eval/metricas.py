"""Métricas da avaliação: o que se mede em cada pergunta, as varreduras de calibração e o resumo por grupo.

Só faz contas: não chama o Ollama nem grava arquivos. Depende de `gabarito`.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from eval.gabarito import GROUPS, Question, match_items
from rag_normas.generate import article_key, extract_citations
from rag_normas.search import Hit


class ResultsError(ValueError):
    """Problema com um arquivo de resultados (.jsonl) gravado por uma rodada anterior."""


@dataclass(frozen=True)
class RetrievalScore:
    """Resultado da busca para uma pergunta."""

    id: str
    retrieved: list[str]
    recall: float
    best_similarity: float


@dataclass(frozen=True)
class AnswerScore:
    """Resultado de uma pergunta de ponta a ponta (busca + resposta). É o que se grava em cada linha do .jsonl."""

    id: str
    group: str
    kind: str
    refused: bool
    best_similarity: float
    retrieval_recall: float
    cited: list[str]
    cited_recall: float
    invalid_citations: list[str]
    items_found: list[str]
    items_missing: list[str]
    seconds: float
    text: str

    @property
    def item_score(self) -> float:
        """Fração dos itens do gabarito presentes na resposta (1.0 se a pergunta não tem itens)."""
        total = len(self.items_found) + len(self.items_missing)
        return len(self.items_found) / total if total else 1.0

    @property
    def complete(self) -> bool:
        return not self.items_missing

    @property
    def false_refusal(self) -> bool:
        """Recusou uma pergunta que o corpus responde."""
        return self.kind == "answer" and self.refused

    @property
    def missed_refusal(self) -> bool:
        """Respondeu uma pergunta que devia ser recusada."""
        return self.kind == "refuse" and not self.refused

    @property
    def correct(self) -> bool:
        """Critério de ponta a ponta. Recusável: recusou. Respondível: respondeu com todos os itens, citou todos
        os artigos esperados e não citou nenhum artigo inexistente."""
        if self.kind == "refuse":
            return self.refused
        return not self.refused and self.complete and self.cited_recall == 1.0 and not self.invalid_citations


@dataclass(frozen=True)
class SummaryRow:
    group: str
    n: int
    correct: int
    mean_item_score: float | None
    mean_cited_recall: float | None
    mean_retrieval_recall: float | None
    false_refusals: int
    missed_refusals: int
    invalid_citations: int
    mean_seconds: float


@dataclass(frozen=True)
class RecallRow:
    k: int
    by_group: dict[str, float]
    total: float


@dataclass(frozen=True)
class RrfRow:
    """Recuperação total (perguntas respondíveis) para cada k, com um dado `rrf_k`."""

    rrf_k: int
    recall_by_k: dict[int, float]


@dataclass(frozen=True)
class ThresholdRow:
    threshold: float
    false_refusals: int
    missed_refusals: int
    answerable: int
    refusable: int


# ---------- artigos ----------


def missing_articles(required: Sequence[str], found: Sequence[str]) -> list[str]:
    """Os artigos exigidos que NÃO aparecem em `found`. Compara pelo artigo, ignorando parágrafo e "º"."""
    present = {article_key(reference) for reference in found}
    return [article for article in required if article_key(article) not in present]


def article_recall(required: Sequence[str], found: Sequence[str]) -> float:
    """Fração dos artigos exigidos que aparecem em `found` (1.0 se nada é exigido)."""
    if not required:
        return 1.0
    return (len(required) - len(missing_articles(required, found))) / len(required)


def check_answer_text(question: Question, text: str, refused: bool) -> tuple[list[str], list[str], list[str]]:
    """Confere uma resposta com o gabarito: devolve (itens presentes, itens ausentes, citações).

    Na recusa não há o que conferir: todos os itens contam como ausentes e não há citações.
    """
    if refused:
        return [], [item.label for item in question.items], []
    found, missing = match_items(text, question.items)
    return found, missing, extract_citations(text)


# ---------- busca ----------


def score_retrieval(question: Question, hits: Sequence[Hit], k: int | None = None) -> RetrievalScore:
    used = list(hits)[:k] if k is not None else list(hits)
    references = [hit.chunk.reference for hit in used]
    best = max((hit.similarity for hit in used), default=0.0)
    return RetrievalScore(question.id, references, article_recall(question.articles, references), best)


def recall_at_k(
    questions: Sequence[Question], hits_by_id: Mapping[str, Sequence[Hit]], ks: Sequence[int]
) -> list[RecallRow]:
    """Recuperação média por grupo, para cada k, só sobre as perguntas que o corpus responde."""
    answerable = [q for q in questions if q.kind == "answer"]
    rows = []
    for k in ks:
        scores = {q.id: score_retrieval(q, hits_by_id[q.id], k).recall for q in answerable}
        by_group = {}
        for group in GROUPS:
            values = [scores[q.id] for q in answerable if q.group == group]
            if values:
                by_group[group] = sum(values) / len(values)
        total = sum(scores.values()) / len(scores) if scores else 0.0
        rows.append(RecallRow(k, by_group, total))
    return rows


def sweep_rrf_k(
    questions: Sequence[Question],
    search: Callable[[Question, int, int], Sequence[Hit]],
    rrf_ks: Sequence[int],
    ks: Sequence[int],
) -> list[RrfRow]:
    """Para cada valor da constante do RRF, mede a recuperação total em cada k.

    Args:
        questions: As perguntas.
        search: Função `search(pergunta, k, rrf_k)` que devolve os artigos recuperados.
        rrf_ks: Valores da constante do RRF a testar.
        ks: Valores de k em que medir a recuperação.
    """
    rows = []
    for rrf_k in rrf_ks:
        hits = {q.id: search(q, max(ks), rrf_k) for q in questions}  # busca com o maior k; os menores são prefixo
        rows.append(RrfRow(rrf_k, {row.k: row.total for row in recall_at_k(questions, hits, ks)}))
    return rows


def sweep_threshold(
    questions: Sequence[Question],
    hits_by_id: Mapping[str, Sequence[Hit]],
    thresholds: Sequence[float],
    k: int,
) -> list[ThresholdRow]:
    """Para cada limiar, conta os dois erros: recusar o que o corpus responde e responder o que devia ser recusado."""
    best = {q.id: score_retrieval(q, hits_by_id[q.id], k).best_similarity for q in questions}
    answerable = [q for q in questions if q.kind == "answer"]
    refusable = [q for q in questions if q.kind == "refuse"]
    return [
        ThresholdRow(
            threshold,
            false_refusals=sum(best[q.id] < threshold for q in answerable),
            missed_refusals=sum(best[q.id] >= threshold for q in refusable),
            answerable=len(answerable),
            refusable=len(refusable),
        )
        for threshold in thresholds
    ]


# ---------- resumo ----------


def mean(values: Sequence[float]) -> float | None:
    """Média, ou None se a lista estiver vazia (o relatório mostra "—")."""
    return sum(values) / len(values) if values else None


def _row(group: str, scores: Sequence[AnswerScore]) -> SummaryRow:
    answerable = [s for s in scores if s.kind == "answer"]
    return SummaryRow(
        group=group,
        n=len(scores),
        correct=sum(s.correct for s in scores),
        mean_item_score=mean([s.item_score for s in answerable]),
        mean_cited_recall=mean([s.cited_recall for s in answerable]),
        mean_retrieval_recall=mean([s.retrieval_recall for s in answerable]),
        false_refusals=sum(s.false_refusal for s in scores),
        missed_refusals=sum(s.missed_refusal for s in scores),
        invalid_citations=sum(len(s.invalid_citations) for s in scores),
        mean_seconds=sum(s.seconds for s in scores) / len(scores),
    )


def summarize(scores: Sequence[AnswerScore]) -> list[SummaryRow]:
    """Uma linha por grupo presente e, no fim, o total."""
    present = [group for group in GROUPS if any(s.group == group for s in scores)]
    rows = [_row(group, [s for s in scores if s.group == group]) for group in present]
    rows.append(_row("total", scores))
    return rows
