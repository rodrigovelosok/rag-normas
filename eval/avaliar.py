"""Avaliação do sistema (RF09): gabarito de perguntas, métricas, calibração e relatórios.

Dois comandos:
    python -m eval.avaliar retrieval   mede só a BUSCA (sem modelo de chat) e ajuda a calibrar k e o limiar de recusa
    python -m eval.avaliar answers     roda as perguntas com o modelo de chat e mede a resposta de ponta a ponta
"""

import argparse
import json
import re
import sys
import time
import unicodedata
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from datetime import date
from pathlib import Path

from rag_normas.config import ConfigError, Settings
from rag_normas.generate import ChatFn, answer, article_key, extract_citations
from rag_normas.index import Index, IndexFileError, load_index
from rag_normas.ingest import Chunk
from rag_normas.llm import LLMError, make_llm
from rag_normas.search import EmbedFn, Hit, hybrid_search

GROUPS = ("fact", "list", "combined", "hard", "out_of_corpus")
KINDS = ("answer", "refuse")
GROUP_LABELS = {
    "fact": "Fatos pontuais",
    "list": "Listas e definições",
    "combined": "Combinação de normas",
    "hard": "Difíceis",
    "out_of_corpus": "Fora do corpus",
    "total": "Total",
}

DEFAULT_QUESTIONS = Path("eval/perguntas.json")
REPORTS_DIR = Path("eval/relatorios")
DEFAULT_THRESHOLDS = [round(0.40 + 0.02 * step, 2) for step in range(16)]  # 0,40 a 0,70
DEFAULT_RRF_KS = [1, 5, 10, 20, 30, 60, 100]  # constantes do RRF testadas na varredura
RRF_SWEEP_KS = [3, 4, 5, 6]  # k em que a varredura mede a recuperação


class QuestionsError(ValueError):
    """Problema no arquivo de perguntas. A mensagem diz qual pergunta e o que corrigir."""


class ResultsError(ValueError):
    """Problema com um arquivo de resultados (.jsonl) gravado por uma rodada anterior."""


@dataclass(frozen=True)
class Item:
    """Um ponto que a resposta deve trazer. Basta casar UMA das expressões de `any_of`."""

    label: str
    any_of: tuple[str, ...]


@dataclass(frozen=True)
class Question:
    """Uma pergunta com o gabarito.

    Attributes:
        id: Identificador ("Q01").
        group: Um de `GROUPS`.
        text: A pergunta.
        kind: "answer" (o corpus responde) ou "refuse" (deve ser recusada).
        articles: Referências dos artigos que deveriam ser recuperados e citados.
        items: Pontos que a resposta deve conter (expressões regulares sem acento, em minúsculas).
    """

    id: str
    group: str
    text: str
    kind: str
    articles: tuple[str, ...]
    items: tuple[Item, ...]


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


# ---------- gabarito ----------

def load_questions(path: Path, valid_articles: Collection[str] | None = None) -> list[Question]:
    """Lê e valida o arquivo de perguntas.

    Args:
        path: Arquivo JSON.
        valid_articles: Se informado, todo artigo esperado precisa estar aqui (referências do corpus/índice).

    Raises:
        QuestionsError: Arquivo ausente, JSON inválido ou pergunta mal formada (a mensagem cita o id).
    """
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise QuestionsError(f"arquivo de perguntas não encontrado: {path}") from None
    except json.JSONDecodeError as error:
        raise QuestionsError(f"o arquivo de perguntas não é um JSON válido ({error})") from None
    if not isinstance(raw, list):
        raise QuestionsError("o arquivo de perguntas deve conter uma lista de perguntas")

    questions: list[Question] = []
    seen: set[str] = set()
    for position, entry in enumerate(raw, 1):
        name = entry.get("id", f"#{position}") if isinstance(entry, dict) else f"#{position}"
        question = _parse_question(name, entry)
        if question.id in seen:
            raise QuestionsError(f"{question.id}: id duplicado")
        seen.add(question.id)
        if valid_articles is not None:
            for article in question.articles:
                if article not in valid_articles:
                    raise QuestionsError(f"{question.id}: artigo esperado inexistente no corpus: {article!r}")
        questions.append(question)
    return questions


def _parse_question(name: str, entry: object) -> Question:
    if not isinstance(entry, dict):
        raise QuestionsError(f"{name}: cada pergunta deve ser um objeto JSON")
    for key in ("id", "group", "kind", "question", "articles", "items"):
        if key not in entry:
            raise QuestionsError(f"{name}: falta a chave '{key}'")
    if entry["kind"] not in KINDS:
        raise QuestionsError(f"{name}: kind inválido ({entry['kind']!r}); use 'answer' ou 'refuse'")
    if entry["group"] not in GROUPS:
        raise QuestionsError(f"{name}: group inválido ({entry['group']!r}); use um de {', '.join(GROUPS)}")
    if entry["kind"] == "answer" and not entry["articles"]:
        raise QuestionsError(f"{name}: pergunta 'answer' precisa de 'articles' (artigos esperados)")
    if entry["kind"] == "answer" and not entry["items"]:
        raise QuestionsError(f"{name}: pergunta 'answer' precisa de 'items' (o que a resposta deve conter)")
    if entry["kind"] == "refuse" and (entry["articles"] or entry["items"]):
        raise QuestionsError(f"{name}: pergunta 'refuse' não pode ter 'articles' nem 'items'")

    items: list[Item] = []
    for raw_item in entry["items"]:
        label, patterns = raw_item["label"], raw_item["any_of"]
        if not patterns:
            raise QuestionsError(f"{name}: o item {label!r} precisa de 'any_of' com ao menos um padrão")
        for pattern in patterns:
            try:
                re.compile(pattern)
            except re.error as error:
                raise QuestionsError(f"{name}: regex inválida {pattern!r} no item {label!r}: {error}") from None
        items.append(Item(label, tuple(patterns)))
    return Question(entry["id"], entry["group"], entry["question"], entry["kind"], tuple(entry["articles"]), tuple(items))


# ---------- texto e artigos ----------

def fold(text: str) -> str:
    """Minúsculas e sem acentos, para comparar "Extinção" com "extincao"."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def strip_citations(text: str) -> str:
    """Tira os `[Fonte: ...]`. Sem isso, "Decreto" dentro da citação contaria como se o modelo explicasse o decreto."""
    return re.sub(r"\[Fonte:[^\]]*\]", " ", text)


def match_items(text: str, items: Sequence[Item]) -> tuple[list[str], list[str]]:
    """Separa os itens em presentes e ausentes no texto da resposta (ignorando acentos, maiúsculas e citações)."""
    folded = fold(strip_citations(text))
    found, missing = [], []
    for item in items:
        present = any(re.search(pattern, folded, re.DOTALL) for pattern in item.any_of)
        (found if present else missing).append(item.label)
    return found, missing


def article_recall(required: Sequence[str], found: Sequence[str]) -> float:
    """Fração dos artigos exigidos que aparecem em `found`. Compara pelo artigo, ignorando parágrafo e "º"."""
    if not required:
        return 1.0
    present = {article_key(reference) for reference in found}
    return sum(article_key(article) in present for article in required) / len(required)


# ---------- busca ----------

def retrieve(questions: Sequence[Question], index: Index, embed: EmbedFn, k: int, rrf_k: int = 60) -> dict[str, list[Hit]]:
    """Busca os `k` artigos de cada pergunta. Não usa o modelo de chat."""
    return {q.id: hybrid_search(q.text, index.chunks, index.vectors, embed, k=k, rrf_k=rrf_k) for q in questions}


def make_search(index: Index, embed: EmbedFn) -> Callable[[Question, int, int], list[Hit]]:
    """Cria a função `search(pergunta, k, rrf_k)` usada na varredura da constante do RRF."""

    def search(question: Question, k: int, rrf_k: int) -> list[Hit]:
        return hybrid_search(question.text, index.chunks, index.vectors, embed, k=k, rrf_k=rrf_k)

    return search


def score_retrieval(question: Question, hits: Sequence[Hit], k: int | None = None) -> RetrievalScore:
    used = list(hits)[:k] if k is not None else list(hits)
    references = [hit.chunk.reference for hit in used]
    best = max((hit.similarity for hit in used), default=0.0)
    return RetrievalScore(question.id, references, article_recall(question.articles, references), best)


def recall_at_k(questions: Sequence[Question], hits_by_id: Mapping[str, Sequence[Hit]], ks: Sequence[int]) -> list[RecallRow]:
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

    if result.refused:
        found, missing, cited = [], [item.label for item in question.items], []
    else:
        found, missing = match_items(result.text, question.items)
        cited = extract_citations(result.text)
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
    path.write_text("".join(json.dumps(asdict(score), ensure_ascii=False) + "\n" for score in scores), encoding="utf-8")


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
        if score.refused:
            found, missing, cited = [], [item.label for item in question.items], []
        else:
            found, missing = match_items(score.text, question.items)
            cited = extract_citations(score.text)
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


# ---------- resumo e relatórios ----------

def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _row(group: str, scores: Sequence[AnswerScore]) -> SummaryRow:
    answerable = [s for s in scores if s.kind == "answer"]
    return SummaryRow(
        group=group,
        n=len(scores),
        correct=sum(s.correct for s in scores),
        mean_item_score=_mean([s.item_score for s in answerable]),
        mean_cited_recall=_mean([s.cited_recall for s in answerable]),
        mean_retrieval_recall=_mean([s.retrieval_recall for s in answerable]),
        false_refusals=sum(s.false_refusal for s in scores),
        missed_refusals=sum(s.missed_refusal for s in scores),
        invalid_citations=sum(len(s.invalid_citations) for s in scores),
        mean_seconds=sum(s.seconds for s in scores) / len(scores),
    )


def summarize(scores: Sequence[AnswerScore]) -> list[SummaryRow]:
    """Uma linha por grupo presente e, no fim, o total."""
    rows = [_row(group, [s for s in scores if s.group == group]) for group in GROUPS if any(s.group == group for s in scores)]
    rows.append(_row("total", scores))
    return rows


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.0%}"


def _decimal(value: float, places: int = 2) -> str:
    return f"{value:.{places}f}".replace(".", ",")


def render_report(
    model: str, k: int, min_similarity: float, scores: Sequence[AnswerScore], today: str, rrf_k: int = 60
) -> str:
    """Relatório em Markdown de uma rodada de respostas."""
    lines = [
        f"# Avaliação das respostas — {model}",
        "",
        f"Data: {today} · modelo de chat: `{model}` · k = {k} · constante do RRF: {rrf_k} · "
        f"limiar de recusa: {_decimal(min_similarity)}",
        "",
        "| Grupo | Perguntas | Corretas | Itens | Citações | Busca | Recusas indevidas | Respostas indevidas "
        "| Citações inexistentes | Tempo médio (s) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summarize(scores):
        lines.append(
            f"| {GROUP_LABELS[row.group]} | {row.n} | {row.correct} | {_pct(row.mean_item_score)} | "
            f"{_pct(row.mean_cited_recall)} | {_pct(row.mean_retrieval_recall)} | {row.false_refusals} | "
            f"{row.missed_refusals} | {row.invalid_citations} | {_decimal(row.mean_seconds, 1)} |"
        )
    lines += [
        "",
        "**Legenda.** *Corretas*: respondeu com todos os itens do gabarito, citou todos os artigos esperados e não "
        "citou nenhum inexistente (nas perguntas fora do corpus: recusou). *Itens*: fração dos pontos do gabarito "
        "presentes na resposta. *Citações*: fração dos artigos esperados que o modelo citou. *Busca*: fração dos "
        "artigos esperados entre os recuperados. *Recusas indevidas*: recusou o que o corpus responde. "
        "*Respostas indevidas*: respondeu o que devia recusar.",
        "",
        "## Falhas",
        "",
    ]
    failures = [s for s in scores if not s.correct]
    if not failures:
        lines.append("Nenhuma.")
    for score in failures:
        lines.append(f"- **{score.id}** ({GROUP_LABELS[score.group]}): {_describe_failure(score)}")
    return "\n".join(lines) + "\n"


def _describe_failure(score: AnswerScore) -> str:
    if score.missed_refusal:
        return f"respondeu em vez de recusar (similaridade máxima {_decimal(score.best_similarity)})"
    if score.false_refusal:
        return f"recusou indevidamente (similaridade máxima {_decimal(score.best_similarity)})"
    parts = []
    if score.items_missing:
        parts.append("faltou: " + "; ".join(score.items_missing))
    if score.cited_recall < 1.0:
        parts.append(f"citou {_pct(score.cited_recall)} dos artigos esperados")
    if score.invalid_citations:
        parts.append("citação inexistente: " + "; ".join(score.invalid_citations))
    return " · ".join(parts)


def render_comparison(names: Sequence[str], runs: Sequence[Sequence[AnswerScore]], today: str) -> str:
    """Compara rodadas das mesmas perguntas lado a lado (por exemplo, dois modelos).

    Raises:
        ResultsError: Se faltar um nome para alguma rodada ou se as rodadas não tiverem as mesmas perguntas.
    """
    if len(names) != len(runs):
        raise ResultsError(f"é preciso um nome para cada arquivo de resultados: {len(runs)} arquivos e {len(names)} nomes")
    ids = [{score.id for score in run} for run in runs]
    if any(group != ids[0] for group in ids):
        raise ResultsError("as rodadas não têm as mesmas perguntas; compare só rodadas completas ou do mesmo subconjunto")

    def answerable(run: Sequence[AnswerScore]) -> list[AnswerScore]:
        return [score for score in run if score.kind == "answer"]

    def seconds(run: Sequence[AnswerScore]) -> str:
        answered = [score.seconds for score in run if not score.refused]  # recusa não chama o modelo: 0 s distorceria
        return _decimal(sum(answered) / len(answered), 1) if answered else "—"

    metrics = [
        ("Respostas corretas", lambda run: f"{sum(s.correct for s in run)} de {len(run)}"),
        ("Itens do gabarito presentes", lambda run: _pct(_mean([s.item_score for s in answerable(run)]))),
        ("Citações dos artigos esperados", lambda run: _pct(_mean([s.cited_recall for s in answerable(run)]))),
        ("Busca (artigos esperados recuperados)", lambda run: _pct(_mean([s.retrieval_recall for s in answerable(run)]))),
        ("Recusas indevidas", lambda run: str(sum(s.false_refusal for s in run))),
        ("Respostas indevidas", lambda run: str(sum(s.missed_refusal for s in run))),
        ("Citações inexistentes", lambda run: str(sum(len(s.invalid_citations) for s in run))),
        ("Tempo médio das respondidas (s)", seconds),
    ]
    lines = [
        "# Comparação entre rodadas",
        "",
        f"Data: {today} · mesmas {len(ids[0])} perguntas em todas as rodadas",
        "",
        "| Métrica | " + " | ".join(names) + " |",
        "|---|" + "---:|" * len(names),
    ]
    for label, compute in metrics:
        lines.append(f"| {label} | " + " | ".join(compute(run) for run in runs) + " |")

    lines += ["", "## Por pergunta (acertou · itens presentes · tempo)", "", "| Pergunta | Grupo | " + " | ".join(names) + " |",
              "|---|---|" + "---|" * len(names)]
    by_run = [{score.id: score for score in run} for run in runs]
    for score in runs[0]:
        cells = []
        for results in by_run:
            other = results[score.id]
            if other.refused:
                cells.append("recusou")
            elif other.kind == "refuse":
                cells.append(f"respondeu · {other.seconds:.0f} s")
            else:
                cells.append(f"{'sim' if other.correct else 'não'} · {other.item_score:.0%} · {other.seconds:.0f} s")
        lines.append(f"| {score.id} | {GROUP_LABELS[score.group]} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def render_retrieval_report(
    questions: Sequence[Question],
    hits_by_id: Mapping[str, Sequence[Hit]],
    k: int,
    ks: Sequence[int],
    thresholds: Sequence[float],
    today: str,
    rrf_rows: Sequence[RrfRow] | None = None,
    rrf_k: int = 60,
) -> str:
    """Relatório em Markdown da avaliação da busca: recuperação por k, k do RRF, falhas e varredura do limiar."""
    lines = [
        "# Avaliação da busca (sem modelo de chat)",
        "",
        f"Data: {today} · k usado nas tabelas de falhas e de limiar: {k} · "
        f"constante do RRF usada nas demais tabelas: {rrf_k}",
        "",
    ]

    lines += ["## Recuperação dos artigos esperados, por k", ""]
    groups = [g for g in GROUPS if any(q.group == g and q.kind == "answer" for q in questions)]
    lines += ["| k | " + " | ".join(GROUP_LABELS[g] for g in groups) + " | Total |", "|---:|" + "---:|" * (len(groups) + 1)]
    for row in recall_at_k(questions, hits_by_id, ks):
        cells = " | ".join(_pct(row.by_group.get(g)) for g in groups)
        lines.append(f"| {row.k} | {cells} | {_pct(row.total)} |")

    if rrf_rows:
        shown = sorted(rrf_rows[0].recall_by_k)
        lines += ["", "## Constante k do RRF (recuperação total, perguntas respondíveis)", ""]
        lines += ["| k do RRF | " + " | ".join(f"k = {n}" for n in shown) + " |", "|---:|" + "---:|" * len(shown)]
        for row in rrf_rows:
            lines.append(f"| {row.rrf_k} | " + " | ".join(_pct(row.recall_by_k[n]) for n in shown) + " |")

    lines += ["", f"## Perguntas em que falta algum artigo esperado entre os k = {k} primeiros", ""]
    missing_any = False
    for question in questions:
        if question.kind != "answer":
            continue
        score = score_retrieval(question, hits_by_id[question.id], k)
        if score.recall < 1.0:
            missing_any = True
            absent = [a for a in question.articles if article_key(a) not in {article_key(r) for r in score.retrieved}]
            lines.append(f"- **{question.id}** ({GROUP_LABELS[question.group]}): faltou {'; '.join(absent)}")
    if not missing_any:
        lines.append("Nenhuma.")

    lines += ["", f"## Similaridade máxima por pergunta (k = {k})", "", "| Pergunta | Grupo | Deve | Similaridade |", "|---|---|---|---:|"]
    ranked = sorted(questions, key=lambda q: score_retrieval(q, hits_by_id[q.id], k).best_similarity, reverse=True)
    for question in ranked:
        best = score_retrieval(question, hits_by_id[question.id], k).best_similarity
        lines.append(f"| {question.id} | {GROUP_LABELS[question.group]} | {'responder' if question.kind == 'answer' else 'recusar'} | {_decimal(best, 3)} |")

    lines += ["", f"## Limiar de recusa (k = {k})", "", "| Limiar | Recusas indevidas | Respostas indevidas |", "|---:|---:|---:|"]
    sweep = sweep_threshold(questions, hits_by_id, thresholds, k)
    for row in sweep:
        lines.append(f"| {_decimal(row.threshold)} | {row.false_refusals} de {row.answerable} | {row.missed_refusals} de {row.refusable} |")
    clean = [row.threshold for row in sweep if row.false_refusals == 0 and row.missed_refusals == 0]
    lines.append("")
    if clean:
        lines.append(f"Limiares sem nenhum erro: de {_decimal(min(clean))} a {_decimal(max(clean))}.")
    else:
        lines.append("Nenhum dos limiares testados separa perfeitamente as perguntas respondíveis das recusáveis.")
    return "\n".join(lines) + "\n"


# ---------- linha de comando ----------

def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS, help="arquivo de perguntas (padrão: eval/perguntas.json)")
    common.add_argument("--index", type=Path, help="arquivo do índice (padrão: data/index.json)")
    common.add_argument("--host", help="endereço do Ollama")
    common.add_argument("--embed-model", help="modelo de embedding")
    common.add_argument("-k", "--top-k", type=int, help="quantos artigos entram na resposta (padrão: 4)")
    common.add_argument("--rrf-k", type=int, help="constante do RRF (padrão: 5)")

    parser = argparse.ArgumentParser(prog="python -m eval.avaliar", description="Avalia a busca e as respostas do rag-normas.")
    commands = parser.add_subparsers(dest="command", required=True, metavar="{retrieval,answers}")

    retrieval = commands.add_parser("retrieval", parents=[common], help="avalia só a busca e a varredura do limiar (rápido, sem chat)")
    retrieval.add_argument("--max-k", type=int, default=8, help="maior k da tabela de recuperação (padrão: 8)")
    retrieval.add_argument("--report", type=Path, default=REPORTS_DIR / "busca.md", help="onde gravar o relatório")

    answers = commands.add_parser("answers", parents=[common], help="roda as perguntas com o modelo de chat (lento)")
    answers.add_argument("--model", help="modelo de chat (padrão: qwen2.5:3b)")
    answers.add_argument("--min-similarity", type=float, help="limiar de recusa (padrão: 0.56)")
    answers.add_argument("--only", help="ids separados por vírgula, por exemplo Q01,Q05")
    answers.add_argument("--resume", action="store_true", help="não repete as perguntas já gravadas no arquivo de saída")
    answers.add_argument("--output", type=Path, help="arquivo .jsonl de resultados (padrão: eval/relatorios/respostas-<modelo>-k<k>.jsonl)")
    answers.add_argument("--report", type=Path, help="relatório em Markdown (padrão: o mesmo nome do --output, com .md)")

    again = commands.add_parser("rescore", help="reavalia respostas já gravadas com o gabarito atual (sem Ollama nem índice)")
    again.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS, help="arquivo de perguntas (padrão: eval/perguntas.json)")
    again.add_argument("--input", type=Path, required=True, help="arquivo .jsonl gravado por 'answers'")
    again.add_argument("--output", type=Path, help="onde gravar os resultados reavaliados (padrão: reescreve o --input)")
    again.add_argument("--report", type=Path, help="relatório em Markdown (padrão: o mesmo nome do arquivo de saída, com .md)")
    again.add_argument("--model", required=True, help="nome do modelo, só para o cabeçalho do relatório")
    again.add_argument("-k", "--top-k", type=int, help="k usado na rodada original, para o cabeçalho (padrão: 4)")
    again.add_argument("--rrf-k", type=int, help="constante do RRF usada na rodada original, para o cabeçalho (padrão: 5)")
    again.add_argument("--min-similarity", type=float, help="limiar usado na rodada original, para o cabeçalho (padrão: 0.56)")

    compare = commands.add_parser("compare", help="compara rodadas gravadas das mesmas perguntas (por exemplo, 3b e 7b)")
    compare.add_argument("--inputs", type=Path, nargs="+", required=True, help="arquivos .jsonl de resultados")
    compare.add_argument("--names", nargs="+", required=True, help="um nome para cada arquivo, na mesma ordem")
    compare.add_argument("--report", type=Path, default=REPORTS_DIR / "comparacao.md", help="onde gravar o relatório")
    return parser


def main(
    argv: list[str] | None = None,
    environ: Mapping[str, str] | None = None,
    llm_factory: Callable[[Settings], tuple[EmbedFn, ChatFn]] = make_llm,
) -> int:
    """Executa um comando e devolve o código de saída: 0 sucesso, 1 erro, 2 erro de uso."""
    args = build_parser().parse_args(argv)
    try:
        if args.command == "compare":  # só lê resultados gravados
            return _run_compare(args)
        settings = Settings.from_env(environ).with_overrides(
            ollama_host=getattr(args, "host", None),
            embed_model=getattr(args, "embed_model", None),
            top_k=args.top_k,
            rrf_k=args.rrf_k,
            index_path=getattr(args, "index", None),
            chat_model=getattr(args, "model", None),
            min_similarity=getattr(args, "min_similarity", None),
        )
        if args.command == "rescore":  # só relê o que já foi gravado: não precisa do índice nem do Ollama
            return _run_rescore(args, settings)
        index = load_index(settings.index_path, expected_model=settings.embed_model)
        questions = load_questions(args.questions, valid_articles={chunk.reference for chunk in index.chunks})
        if args.command == "retrieval":
            return _run_retrieval(args, settings, index, questions, llm_factory)
        return _run_answers(args, settings, index, questions, llm_factory)
    except (ConfigError, LLMError, IndexFileError, QuestionsError, ResultsError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1


def _run_compare(args) -> int:
    for path in args.inputs:
        if not path.exists():
            raise ResultsError(f"arquivo de resultados não encontrado: {path}")
    report = render_comparison(args.names, [load_scores(path) for path in args.inputs], date.today().isoformat())
    _write(args.report, report)
    print(report, end="")
    return 0


def _run_rescore(args, settings: Settings) -> int:
    if not args.input.exists():
        raise ResultsError(f"arquivo de resultados não encontrado: {args.input}")
    questions = load_questions(args.questions)
    scores = rescore(questions, load_scores(args.input))
    output = args.output or args.input
    save_scores(output, scores)
    report = render_report(
        settings.chat_model, settings.top_k, settings.min_similarity, scores, date.today().isoformat(), settings.rrf_k
    )
    _write(args.report or output.with_suffix(".md"), report)
    print(report, end="")
    return 0


def _memoized(embed: EmbedFn) -> EmbedFn:
    """Guarda o resultado de cada chamada: o mesmo texto não é enviado ao Ollama duas vezes."""
    cache: dict[tuple[str, ...], list[list[float]]] = {}

    def wrapper(texts: list[str]) -> list[list[float]]:
        key = tuple(texts)
        if key not in cache:
            cache[key] = embed(texts)
        return cache[key]

    return wrapper


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run_retrieval(args, settings: Settings, index: Index, questions: list[Question], llm_factory) -> int:
    raw_embed, _ = llm_factory(settings)
    embed = _memoized(raw_embed)  # a pergunta é a mesma em todas as buscas da varredura: um embedding por pergunta
    max_k = max(args.max_k, settings.top_k)
    hits = retrieve(questions, index, embed, max_k, settings.rrf_k)
    rrf_rows = sweep_rrf_k(questions, make_search(index, embed), DEFAULT_RRF_KS, RRF_SWEEP_KS)
    report = render_retrieval_report(
        questions, hits, settings.top_k, list(range(1, max_k + 1)), DEFAULT_THRESHOLDS, date.today().isoformat(),
        rrf_rows, settings.rrf_k,
    )
    _write(args.report, report)
    print(report, end="")
    return 0


def _run_answers(args, settings: Settings, index: Index, questions: list[Question], llm_factory) -> int:
    if args.only:
        wanted = [name.strip() for name in args.only.split(",") if name.strip()]
        unknown = [name for name in wanted if name not in {q.id for q in questions}]
        if unknown:
            raise QuestionsError(f"id desconhecido em --only: {', '.join(unknown)}")
        questions = [q for q in questions if q.id in wanted]

    slug = re.sub(r"[^a-z0-9.]+", "-", settings.chat_model.lower()).strip("-")
    output = args.output or REPORTS_DIR / f"respostas-{slug}-k{settings.top_k}.jsonl"
    report_path = args.report or output.with_suffix(".md")

    embed, chat = llm_factory(settings)
    hits = retrieve(questions, index, embed, settings.top_k, settings.rrf_k)

    def progress(number: int, total: int, score: AnswerScore) -> None:
        print(f"[{number}/{total}] {score.id} {'ok' if score.correct else 'falhou'} ({score.seconds:.0f} s)", file=sys.stderr)

    scores = run_answers(
        questions, hits, chat, index.chunks, settings.min_similarity, output=output, resume=args.resume, on_progress=progress
    )
    report = render_report(
        settings.chat_model, settings.top_k, settings.min_similarity, scores, date.today().isoformat(), settings.rrf_k
    )
    _write(report_path, report)
    print(report, end="")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
    sys.exit(main())
