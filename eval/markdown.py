"""Relatórios da avaliação em Markdown: rodada de respostas, comparação entre rodadas e avaliação da busca.

Só monta texto a partir dos resultados; as contas ficam em `metricas`. Depende de `gabarito` e `metricas`.
"""

from collections.abc import Callable, Mapping, Sequence

from eval.gabarito import GROUPS, Question
from eval.metricas import (
    AnswerScore,
    ResultsError,
    RrfRow,
    mean,
    missing_articles,
    recall_at_k,
    score_retrieval,
    summarize,
    sweep_threshold,
)
from rag_normas.search import Hit

GROUP_LABELS = {
    "fact": "Fatos pontuais",
    "list": "Listas e definições",
    "combined": "Combinação de normas",
    "hard": "Difíceis",
    "out_of_corpus": "Fora do corpus",
    "total": "Total",
}


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.0%}"


def _decimal(value: float, places: int = 2) -> str:
    return f"{value:.{places}f}".replace(".", ",")


def _md_row(*cells: str) -> str:
    """Uma linha de tabela Markdown: `_md_row("a", "b")` devolve "| a | b |"."""
    return "| " + " | ".join(cells) + " |"


# ---------- rodada de respostas ----------


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
            _md_row(
                GROUP_LABELS[row.group],
                str(row.n),
                str(row.correct),
                _pct(row.mean_item_score),
                _pct(row.mean_cited_recall),
                _pct(row.mean_retrieval_recall),
                str(row.false_refusals),
                str(row.missed_refusals),
                str(row.invalid_citations),
                _decimal(row.mean_seconds, 1),
            )
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


# ---------- comparação entre rodadas ----------


def _answerable(run: Sequence[AnswerScore]) -> list[AnswerScore]:
    return [score for score in run if score.kind == "answer"]


def _mean_seconds_answered(run: Sequence[AnswerScore]) -> str:
    answered = [score.seconds for score in run if not score.refused]  # recusa não chama o modelo: 0 s distorceria
    return _decimal(sum(answered) / len(answered), 1) if answered else "—"


# Cada métrica da tabela de comparação: (rótulo, função que recebe uma rodada e devolve o texto da célula).
_COMPARISON_METRICS: list[tuple[str, Callable[[Sequence[AnswerScore]], str]]] = [
    ("Respostas corretas", lambda run: f"{sum(s.correct for s in run)} de {len(run)}"),
    ("Itens do gabarito presentes", lambda run: _pct(mean([s.item_score for s in _answerable(run)]))),
    ("Citações dos artigos esperados", lambda run: _pct(mean([s.cited_recall for s in _answerable(run)]))),
    (
        "Busca (artigos esperados recuperados)",
        lambda run: _pct(mean([s.retrieval_recall for s in _answerable(run)])),
    ),
    ("Recusas indevidas", lambda run: str(sum(s.false_refusal for s in run))),
    ("Respostas indevidas", lambda run: str(sum(s.missed_refusal for s in run))),
    ("Citações inexistentes", lambda run: str(sum(len(s.invalid_citations) for s in run))),
    ("Tempo médio das respondidas (s)", _mean_seconds_answered),
]


def _comparison_cell(score: AnswerScore) -> str:
    """O que uma rodada fez numa pergunta: "recusou", "respondeu · 93 s" ou "sim · 100% · 58 s"."""
    if score.refused:
        return "recusou"
    if score.kind == "refuse":
        return f"respondeu · {score.seconds:.0f} s"
    return f"{'sim' if score.correct else 'não'} · {score.item_score:.0%} · {score.seconds:.0f} s"


def render_comparison(names: Sequence[str], runs: Sequence[Sequence[AnswerScore]], today: str) -> str:
    """Compara rodadas das mesmas perguntas lado a lado (por exemplo, dois modelos).

    Raises:
        ResultsError: Se faltar um nome para alguma rodada ou se as rodadas não tiverem as mesmas perguntas.
    """
    if len(names) != len(runs):
        raise ResultsError(
            f"é preciso um nome para cada arquivo de resultados: {len(runs)} arquivos e {len(names)} nomes"
        )
    ids = [{score.id for score in run} for run in runs]
    if any(group != ids[0] for group in ids):
        raise ResultsError(
            "as rodadas não têm as mesmas perguntas; compare só rodadas completas ou do mesmo subconjunto"
        )

    lines = [
        "# Comparação entre rodadas",
        "",
        f"Data: {today} · mesmas {len(ids[0])} perguntas em todas as rodadas",
        "",
        _md_row("Métrica", *names),
        "|---|" + "---:|" * len(names),
    ]
    for label, compute in _COMPARISON_METRICS:
        lines.append(_md_row(label, *(compute(run) for run in runs)))

    lines += [
        "",
        "## Por pergunta (acertou · itens presentes · tempo)",
        "",
        _md_row("Pergunta", "Grupo", *names),
        "|---|---|" + "---|" * len(names),
    ]
    by_run = [{score.id: score for score in run} for run in runs]
    for score in runs[0]:
        cells = [_comparison_cell(results[score.id]) for results in by_run]
        lines.append(_md_row(score.id, GROUP_LABELS[score.group], *cells))
    return "\n".join(lines) + "\n"


# ---------- avaliação da busca ----------


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
    ]
    sections = [
        _recall_section(questions, hits_by_id, ks),
        _rrf_section(rrf_rows) if rrf_rows else [],
        _missing_section(questions, hits_by_id, k),
        _similarity_section(questions, hits_by_id, k),
        _threshold_section(questions, hits_by_id, thresholds, k),
    ]
    for section in sections:
        if section:
            lines += ["", *section]
    return "\n".join(lines) + "\n"


def _recall_section(questions: Sequence[Question], hits_by_id: Mapping[str, Sequence[Hit]], ks: Sequence[int]) -> list[str]:
    groups = [g for g in GROUPS if any(q.group == g and q.kind == "answer" for q in questions)]
    lines = [
        "## Recuperação dos artigos esperados, por k",
        "",
        _md_row("k", *(GROUP_LABELS[g] for g in groups), "Total"),
        "|---:|" + "---:|" * (len(groups) + 1),
    ]
    for row in recall_at_k(questions, hits_by_id, ks):
        lines.append(_md_row(str(row.k), *(_pct(row.by_group.get(g)) for g in groups), _pct(row.total)))
    return lines


def _rrf_section(rrf_rows: Sequence[RrfRow]) -> list[str]:
    shown = sorted(rrf_rows[0].recall_by_k)
    lines = [
        "## Constante k do RRF (recuperação total, perguntas respondíveis)",
        "",
        _md_row("k do RRF", *(f"k = {n}" for n in shown)),
        "|---:|" + "---:|" * len(shown),
    ]
    for row in rrf_rows:
        lines.append(_md_row(str(row.rrf_k), *(_pct(row.recall_by_k[n]) for n in shown)))
    return lines


def _missing_section(questions: Sequence[Question], hits_by_id: Mapping[str, Sequence[Hit]], k: int) -> list[str]:
    lines = [f"## Perguntas em que falta algum artigo esperado entre os k = {k} primeiros", ""]
    missing_any = False
    for question in questions:
        if question.kind != "answer":
            continue
        absent = missing_articles(question.articles, score_retrieval(question, hits_by_id[question.id], k).retrieved)
        if absent:
            missing_any = True
            lines.append(f"- **{question.id}** ({GROUP_LABELS[question.group]}): faltou {'; '.join(absent)}")
    if not missing_any:
        lines.append("Nenhuma.")
    return lines


def _similarity_section(questions: Sequence[Question], hits_by_id: Mapping[str, Sequence[Hit]], k: int) -> list[str]:
    best = {q.id: score_retrieval(q, hits_by_id[q.id], k).best_similarity for q in questions}
    lines = [
        f"## Similaridade máxima por pergunta (k = {k})",
        "",
        "| Pergunta | Grupo | Deve | Similaridade |",
        "|---|---|---|---:|",
    ]
    for question in sorted(questions, key=lambda q: best[q.id], reverse=True):
        should = "responder" if question.kind == "answer" else "recusar"
        lines.append(_md_row(question.id, GROUP_LABELS[question.group], should, _decimal(best[question.id], 3)))
    return lines


def _threshold_section(
    questions: Sequence[Question], hits_by_id: Mapping[str, Sequence[Hit]], thresholds: Sequence[float], k: int
) -> list[str]:
    lines = [
        f"## Limiar de recusa (k = {k})",
        "",
        "| Limiar | Recusas indevidas | Respostas indevidas |",
        "|---:|---:|---:|",
    ]
    sweep = sweep_threshold(questions, hits_by_id, thresholds, k)
    for row in sweep:
        lines.append(
            _md_row(
                _decimal(row.threshold),
                f"{row.false_refusals} de {row.answerable}",
                f"{row.missed_refusals} de {row.refusable}",
            )
        )
    clean = [row.threshold for row in sweep if row.false_refusals == 0 and row.missed_refusals == 0]
    lines.append("")
    if clean:
        lines.append(f"Limiares sem nenhum erro: de {_decimal(min(clean))} a {_decimal(max(clean))}.")
    else:
        lines.append("Nenhum dos limiares testados separa perfeitamente as perguntas respondíveis das recusáveis.")
    return lines
