"""Testes do avaliador (RF09): validação do gabarito, métricas, varreduras de calibração e linha de comando.

Nenhum teste usa o Ollama: `embed` e `chat` são funções falsas.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from eval.avaliar import main
from eval.gabarito import Item, Question, QuestionsError, fold, load_questions, match_items, strip_citations
from eval.markdown import render_comparison, render_report, render_retrieval_report
from eval.metricas import (
    AnswerScore,
    ResultsError,
    RrfRow,
    article_recall,
    recall_at_k,
    score_retrieval,
    summarize,
    sweep_rrf_k,
    sweep_threshold,
)
from eval.rodada import append_score, load_scores, make_search, rescore, retrieve, run_answer, run_answers
from rag_normas.generate import REFUSAL_MESSAGE
from rag_normas.index import build_index, save_index
from rag_normas.ingest import Chunk, load_corpus
from rag_normas.search import Hit

ART_2 = "IN RFB 2.091/2022, art. 2º"
ART_5 = "IN RFB 2.091/2022, art. 5º"
DECREE = "Decreto 7.573/2011, art. 1º"
ROOT = Path(__file__).resolve().parent.parent


def chunk(reference_norm: str, article: str, text: str = "Texto.") -> Chunk:
    return Chunk(reference_norm, article, "", text)


CHUNK_2 = chunk("IN RFB 2.091/2022", "2")
CHUNK_5 = chunk("IN RFB 2.091/2022", "5")
CHUNK_DECREE = chunk("Decreto 7.573/2011", "1")
INDEX_CHUNKS = [CHUNK_2, CHUNK_5, CHUNK_DECREE]


def hit(c: Chunk, similarity: float = 0.7) -> Hit:
    return Hit(c, similarity=similarity, bm25=0.0, score=0.0)


def question(**changes) -> Question:
    base = dict(
        id="Q01",
        group="fact",
        text="Qual o limite?",
        kind="answer",
        articles=(ART_2,),
        items=(Item("30%", ("30 ?%",)), Item("R$ 2 milhões", ("2[.]000[.]000", "2 milh"))),
    )
    base.update(changes)
    return Question(**base)


REFUSE_Q = question(id="Q02", group="out_of_corpus", text="Alíquota do IRPF?", kind="refuse", articles=(), items=())


class FakeChat:
    def __init__(self, reply: str):
        self.reply = reply
        self.calls = 0

    def __call__(self, messages):
        self.calls += 1
        return self.reply


def ticking_clock(*values: float):
    """Relógio falso: devolve os valores dados, um por chamada."""
    iterator = iter(values)
    return lambda: next(iterator)


GOOD_REPLY = "O limite é de 30% do patrimônio e R$ 2.000.000. [Fonte: IN RFB 2.091/2022, art. 2º]"


# ---------- gabarito: validação ----------


def write_questions(tmp_path, entries) -> Path:
    path = tmp_path / "perguntas.json"
    path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return path


def entry(**changes) -> dict:
    base = {
        "id": "Q01",
        "group": "fact",
        "kind": "answer",
        "question": "Pergunta?",
        "articles": [ART_2],
        "items": [{"label": "x", "any_of": ["x"]}],
    }
    base.update(changes)
    return base


def test_the_real_question_set_is_valid_and_matches_the_corpus():
    references = {c.reference for c in load_corpus(ROOT / "data" / "normas")}
    questions = load_questions(ROOT / "eval" / "perguntas.json", valid_articles=references)
    assert [q.id for q in questions] == [f"Q{n:02d}" for n in range(1, 22)]
    assert sum(q.kind == "refuse" for q in questions) == 5
    assert all(q.articles and q.items for q in questions if q.kind == "answer")


def test_valid_file_is_loaded_into_dataclasses(tmp_path):
    [loaded] = load_questions(write_questions(tmp_path, [entry()]))
    assert loaded == Question("Q01", "fact", "Pergunta?", "answer", (ART_2,), (Item("x", ("x",)),))


@pytest.mark.parametrize(
    "bad, fragment",
    [
        (entry(kind="talvez"), "kind"),
        (entry(group="outro"), "group"),
        (entry(articles=[]), "articles"),
        (entry(items=[]), "items"),
        (entry(kind="refuse"), "refuse"),
        (entry(items=[{"label": "x", "any_of": ["("]}]), "regex"),
        (entry(items=[{"label": "x", "any_of": []}]), "any_of"),
    ],
)
def test_invalid_entries_are_rejected_with_the_question_id(tmp_path, bad, fragment):
    with pytest.raises(QuestionsError) as error:
        load_questions(write_questions(tmp_path, [bad]))
    assert "Q01" in str(error.value) and fragment in str(error.value)


def test_duplicate_ids_are_rejected(tmp_path):
    with pytest.raises(QuestionsError, match="duplicad"):
        load_questions(write_questions(tmp_path, [entry(), entry()]))


def test_missing_key_is_rejected(tmp_path):
    broken = entry()
    del broken["question"]
    with pytest.raises(QuestionsError, match="question"):
        load_questions(write_questions(tmp_path, [broken]))


def test_unknown_expected_article_is_rejected_when_the_corpus_is_given(tmp_path):
    path = write_questions(tmp_path, [entry(articles=["IN RFB 2.091/2022, art. 99"])])
    with pytest.raises(QuestionsError, match="art. 99"):
        load_questions(path, valid_articles={ART_2})


def test_missing_or_broken_file_is_a_questions_error(tmp_path):
    with pytest.raises(QuestionsError, match="não encontrado"):
        load_questions(tmp_path / "nao-existe.json")
    broken = tmp_path / "quebrado.json"
    broken.write_text("{ isto não é json", encoding="utf-8")
    with pytest.raises(QuestionsError, match="JSON"):
        load_questions(broken)


# ---------- texto: fold, citações, itens ----------


def test_fold_removes_accents_and_case():
    assert fold("Extinção do CRÉDITO") == "extincao do credito"


def test_strip_citations_removes_only_the_bracketed_citation():
    assert "decreto" not in strip_citations("Vale. [Fonte: Decreto 7.573/2011, art. 1º] Fim.").lower()
    assert "Vale." in strip_citations("Vale. [Fonte: Decreto 7.573/2011, art. 1º] Fim.")
    assert strip_citations("Veja [1] e (art. 2º).") == "Veja [1] e (art. 2º)."


def test_match_items_finds_by_any_alternative_ignoring_accents_and_case():
    items = (Item("prazo", ("cinco dias", "5 dias")), Item("fundamento", ("ato fundamentado",)))
    found, missing = match_items("O prazo é de 5 DIAS.", items)
    assert found == ["prazo"] and missing == ["fundamento"]
    found, missing = match_items("Por ATO FUNDAMENTADO, em cinco dias.", items)
    assert found == ["prazo", "fundamento"] and missing == []


def test_match_items_patterns_can_cross_line_breaks():
    items = (Item("cônjuge no patrimônio", ("patrimonio conhecido.{0,50}conjuge",)),)
    found, _ = match_items("Patrimônio conhecido inclui\no cônjuge.", items)
    assert found == ["cônjuge no patrimônio"]


def test_match_items_ignores_what_is_inside_the_citation_brackets():
    items = (Item("decreto", ("decreto",)),)
    found, missing = match_items("Vale R$ 2 milhões. [Fonte: Decreto 7.573/2011, art. 1º]", items)
    assert found == [] and missing == ["decreto"]


def test_match_items_without_items_is_empty():
    assert match_items("qualquer coisa", ()) == ([], [])


# ---------- artigos ----------


def test_article_recall_is_a_fraction_of_the_required_articles():
    assert article_recall([ART_2, DECREE], [ART_2]) == 0.5
    assert article_recall([ART_2, DECREE], [DECREE, ART_2, ART_5]) == 1.0
    assert article_recall([ART_2], []) == 0.0


def test_article_recall_with_nothing_required_is_one():
    assert article_recall([], [ART_2]) == 1.0


def test_article_recall_ignores_paragraph_and_ordinal_sign():
    assert article_recall([ART_2], ["IN RFB 2.091/2022, art. 2, § 1º"]) == 1.0


# ---------- recuperação ----------


def test_score_retrieval_reports_recall_best_similarity_and_references():
    hits = [hit(CHUNK_5, 0.4), hit(CHUNK_2, 0.65)]
    result = score_retrieval(question(articles=(ART_2, DECREE)), hits)
    assert result.retrieved == [ART_5, ART_2]
    assert result.recall == 0.5
    assert result.best_similarity == 0.65


def test_score_retrieval_can_limit_to_the_first_k_hits():
    hits = [hit(CHUNK_5, 0.4), hit(CHUNK_2, 0.65)]
    result = score_retrieval(question(), hits, k=1)
    assert result.retrieved == [ART_5] and result.recall == 0.0 and result.best_similarity == 0.4


def test_score_retrieval_without_hits():
    result = score_retrieval(question(), [])
    assert result.recall == 0.0 and result.best_similarity == 0.0 and result.retrieved == []


def test_recall_at_k_is_averaged_per_group_over_answerable_questions():
    q_fact = question(id="Q01", group="fact", articles=(ART_2,))
    q_hard = question(id="Q03", group="hard", articles=(ART_2, DECREE))
    hits = {
        "Q01": [hit(CHUNK_5), hit(CHUNK_2)],  # artigo esperado na 2ª posição
        "Q03": [hit(CHUNK_2), hit(CHUNK_5), hit(CHUNK_DECREE)],
        "Q02": [hit(CHUNK_5)],
    }
    rows = recall_at_k([q_fact, q_hard, REFUSE_Q], hits, ks=[1, 2, 3])
    by_k = {row.k: row for row in rows}
    assert by_k[1].by_group == {"fact": 0.0, "hard": 0.5} and by_k[1].total == 0.25
    assert by_k[2].by_group == {"fact": 1.0, "hard": 0.5} and by_k[2].total == 0.75
    assert by_k[3].by_group == {"fact": 1.0, "hard": 1.0} and by_k[3].total == 1.0
    assert "out_of_corpus" not in by_k[3].by_group  # perguntas recusáveis não têm artigo esperado


def test_sweep_threshold_counts_both_kinds_of_error():
    answerable = [question(id="Q01"), question(id="Q03")]
    refusable = [question(id="Q04", kind="refuse", group="out_of_corpus", articles=(), items=()), REFUSE_Q]
    hits = {
        "Q01": [hit(CHUNK_2, 0.60)],
        "Q03": [hit(CHUNK_2, 0.50)],
        "Q04": [hit(CHUNK_5, 0.45)],
        "Q02": [hit(CHUNK_5, 0.55)],
    }
    rows = {
        row.threshold: row
        for row in sweep_threshold(answerable + refusable, hits, [0.4, 0.5, 0.52, 0.55, 0.56, 0.7], k=4)
    }
    assert (rows[0.55].false_refusals, rows[0.55].missed_refusals) == (
        1,
        1,
    )  # 0,55 >= 0,55 conta como resposta indevida
    # recusa indevida = pergunta respondível com similaridade < limiar;
    # resposta indevida = recusável com similaridade >= limiar
    assert (rows[0.4].false_refusals, rows[0.4].missed_refusals) == (0, 2)
    assert (rows[0.5].false_refusals, rows[0.5].missed_refusals) == (0, 1)  # 0,50 não é < 0,50
    assert (rows[0.52].false_refusals, rows[0.52].missed_refusals) == (1, 1)
    assert (rows[0.56].false_refusals, rows[0.56].missed_refusals) == (1, 0)
    assert (rows[0.7].false_refusals, rows[0.7].missed_refusals) == (2, 0)
    assert rows[0.7].answerable == 2 and rows[0.7].refusable == 2


def test_sweep_rrf_k_tries_each_value_and_reports_recall_per_k():
    calls = []

    def search(q, k, rrf_k):
        calls.append((q.id, k, rrf_k))
        if rrf_k == 10:
            return [hit(CHUNK_2)]  # com rrf_k = 10 o artigo certo vem em 1º
        return [hit(CHUNK_5)] * 4 + [hit(CHUNK_2)]  # com rrf_k = 60 ele cai para o 5º

    rows = sweep_rrf_k([question()], search, rrf_ks=[10, 60], ks=[1, 4, 5])
    assert [row.rrf_k for row in rows] == [10, 60]
    assert rows[0].recall_by_k == {1: 1.0, 4: 1.0, 5: 1.0}
    assert rows[1].recall_by_k == {1: 0.0, 4: 0.0, 5: 1.0}
    assert calls == [("Q01", 5, 10), ("Q01", 5, 60)]  # busca uma vez por valor, já com o maior k


def test_sweep_rrf_k_ignores_questions_that_must_be_refused():
    rows = sweep_rrf_k([question(), REFUSE_Q], lambda q, k, rrf_k: [hit(CHUNK_2)], rrf_ks=[60], ks=[1])
    assert rows[0].recall_by_k == {1: 1.0}


def test_retrieve_uses_the_given_rrf_k():
    chunks = [
        Chunk("norma-teste", "1", "", "Art. 1º Texto sobre arrolamento."),
        Chunk("norma-teste", "2", "", "Art. 2º Outro assunto."),
    ]
    index = build_index(chunks, fake_embed, "bge-m3")
    q = question(text="arrolamento")
    assert retrieve([q], index, fake_embed, 1, rrf_k=10)["Q01"][0].score == pytest.approx(2 / 11)
    assert retrieve([q], index, fake_embed, 1)["Q01"][0].score == pytest.approx(2 / 61)  # padrão: 60


def test_make_search_passes_k_and_rrf_k_to_the_hybrid_search():
    chunks = [
        Chunk("norma-teste", "1", "", "Art. 1º Texto sobre arrolamento."),
        Chunk("norma-teste", "2", "", "Art. 2º Outro assunto."),
    ]
    index = build_index(chunks, fake_embed, "bge-m3")
    search = make_search(index, fake_embed)
    q = question(text="arrolamento")
    # o art. 1º é o 1º do ranking por vetor e o 1º do ranking por palavras: nota 2 / (rrf_k + 1)
    assert search(q, 1, 60)[0].score == pytest.approx(2 / 61)
    assert search(q, 1, 10)[0].score == pytest.approx(2 / 11)
    assert len(search(q, 2, 10)) == 2 and len(search(q, 1, 10)) == 1  # o k limita a quantidade


def test_retrieval_report_has_the_rrf_section_only_when_rows_are_given():
    args = ([question()], {"Q01": [hit(CHUNK_2)]})
    kwargs = dict(k=4, ks=[1, 4], thresholds=[0.5], today="2026-10-08")
    without = render_retrieval_report(*args, **kwargs)
    assert "k do RRF" not in without
    assert "constante do RRF usada nas demais tabelas: 60" in without
    assert "constante do RRF usada nas demais tabelas: 7" in render_retrieval_report(*args, **kwargs, rrf_k=7)
    with_rows = render_retrieval_report(
        *args, **kwargs, rrf_rows=[RrfRow(10, {1: 1.0, 4: 1.0}), RrfRow(60, {1: 0.0, 4: 1.0})]
    )
    assert "k do RRF" in with_rows and "| 10 | 100% | 100% |" in with_rows and "| 60 | 0% | 100% |" in with_rows
    # sem as linhas do RRF, a tabela de recuperação é seguida (após uma linha em branco) pela seção de ausentes
    assert "| 4 | 100% | 100% |\n\n## Perguntas em que falta" in without


def test_retrieval_report_lists_the_missing_articles_or_says_none():
    two = question(articles=(ART_2, ART_5))
    kwargs = dict(k=4, ks=[4], thresholds=[0.5], today="2026-10-08")
    partial = render_retrieval_report([two], {"Q01": [hit(CHUNK_2)]}, **kwargs)
    assert f"- **Q01** (Fatos pontuais): faltou {ART_5}" in partial and "Nenhuma." not in partial
    complete = render_retrieval_report([two], {"Q01": [hit(CHUNK_2), hit(CHUNK_5)]}, **kwargs)
    assert "entre os k = 4 primeiros\n\nNenhuma.\n" in complete


def test_retrieval_report_sorts_questions_by_best_similarity_descending():
    hits = {"Q01": [hit(CHUNK_2, 0.40)], "Q02": [hit(CHUNK_2, 0.90)]}
    report = render_retrieval_report(
        [question(id="Q01"), question(id="Q02")], hits, k=4, ks=[4], thresholds=[0.5], today="2026-10-08"
    )
    assert report.index("| Q02 | Fatos pontuais | responder | 0,900 |") < report.index(
        "| Q01 | Fatos pontuais | responder | 0,400 |"
    )


# ---------- resposta: pontuação de uma pergunta ----------


def test_a_complete_cited_answer_is_correct():
    score = run_answer(
        question(), [hit(CHUNK_2)], FakeChat(GOOD_REPLY), INDEX_CHUNKS, 0.52, clock=ticking_clock(10.0, 12.5)
    )
    assert score.correct and score.complete and score.item_score == 1.0
    assert score.cited == [ART_2] and score.cited_recall == 1.0 and score.invalid_citations == []
    assert score.retrieval_recall == 1.0 and score.best_similarity == 0.7
    assert score.seconds == 2.5 and not score.refused


def test_an_incomplete_answer_is_not_correct_and_lists_what_is_missing():
    reply = "O limite é de 30% do patrimônio. [Fonte: IN RFB 2.091/2022, art. 2º]"
    score = run_answer(question(), [hit(CHUNK_2)], FakeChat(reply), INDEX_CHUNKS, 0.52)
    assert score.items_found == ["30%"] and score.items_missing == ["R$ 2 milhões"]
    assert score.item_score == 0.5 and not score.complete and not score.correct


def test_a_complete_answer_without_the_expected_citation_is_not_correct():
    reply = "30% e R$ 2 milhões. [Fonte: IN RFB 2.091/2022, art. 5º]"
    score = run_answer(question(), [hit(CHUNK_2)], FakeChat(reply), INDEX_CHUNKS, 0.52)
    assert score.complete and score.cited_recall == 0.0 and not score.correct


def test_an_invented_citation_makes_the_answer_incorrect():
    reply = "30% e R$ 2 milhões. [Fonte: IN RFB 2.091/2022, art. 2º] [Fonte: IN RFB 2.091/2022, art. 99]"
    score = run_answer(question(), [hit(CHUNK_2)], FakeChat(reply), INDEX_CHUNKS, 0.52)
    assert score.invalid_citations == ["IN RFB 2.091/2022, art. 99"] and not score.correct


def test_refusing_an_answerable_question_is_a_false_refusal():
    chat = FakeChat(GOOD_REPLY)
    score = run_answer(question(), [hit(CHUNK_2, 0.30)], chat, INDEX_CHUNKS, 0.52)
    assert score.refused and score.false_refusal and not score.correct
    assert score.items_missing == ["30%", "R$ 2 milhões"] and score.cited == []
    assert chat.calls == 0  # recusou pelo limiar, sem chamar o modelo
    assert score.best_similarity == 0.30


def test_refusing_a_refusable_question_is_correct():
    score = run_answer(REFUSE_Q, [hit(CHUNK_5, 0.40)], FakeChat(GOOD_REPLY), INDEX_CHUNKS, 0.52)
    assert score.refused and score.correct and not score.missed_refusal and not score.false_refusal


def test_answering_a_refusable_question_is_a_missed_refusal():
    score = run_answer(
        REFUSE_Q,
        [hit(CHUNK_5, 0.60)],
        FakeChat("Resposta inventada. [Fonte: IN RFB 2.091/2022, art. 5º]"),
        INDEX_CHUNKS,
        0.52,
    )
    assert not score.refused and score.missed_refusal and not score.correct


def test_retrieval_recall_comes_from_the_hits_and_not_from_the_answer():
    score = run_answer(question(), [hit(CHUNK_5)], FakeChat(GOOD_REPLY), INDEX_CHUNKS, 0.52)
    assert score.retrieval_recall == 0.0 and score.cited_recall == 1.0


def test_the_answer_text_is_kept_without_the_disclaimer():
    score = run_answer(question(), [hit(CHUNK_2)], FakeChat(GOOD_REPLY), INDEX_CHUNKS, 0.52)
    assert score.text == GOOD_REPLY


def test_a_refusal_keeps_the_refusal_phrase_as_text():
    score = run_answer(question(), [], FakeChat(GOOD_REPLY), INDEX_CHUNKS, 0.52)
    assert score.text == REFUSAL_MESSAGE and score.best_similarity == 0.0


# ---------- arquivo de resultados (uma linha por pergunta) ----------


def make_score(**changes) -> AnswerScore:
    base = dict(
        id="Q01",
        group="fact",
        kind="answer",
        refused=False,
        best_similarity=0.7,
        retrieval_recall=1.0,
        cited=[ART_2],
        cited_recall=1.0,
        invalid_citations=[],
        items_found=["a"],
        items_missing=[],
        seconds=2.0,
        text="t",
    )
    base.update(changes)
    return AnswerScore(**base)


def test_item_score_of_a_question_without_items_is_full():
    assert make_score(items_found=[], items_missing=[]).item_score == 1.0
    assert make_score(items_found=["a"], items_missing=["b", "c", "d"]).item_score == 0.25


def test_scores_are_appended_as_json_lines_and_read_back(tmp_path):
    path = tmp_path / "saida" / "r.jsonl"
    first, second = make_score(id="Q01"), make_score(id="Q02", items_missing=["b"])
    append_score(path, first)
    append_score(path, second)
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2
    assert load_scores(path) == [first, second]


def test_load_scores_of_a_missing_file_is_empty(tmp_path):
    assert load_scores(tmp_path / "nao-existe.jsonl") == []


def questions_pair():
    return [question(id="Q01"), question(id="Q03")]


def hits_pair():
    return {"Q01": [hit(CHUNK_2)], "Q03": [hit(CHUNK_2)]}


def test_run_answers_writes_each_result_as_soon_as_it_is_ready(tmp_path):
    output = tmp_path / "r.jsonl"
    lines_seen = []

    def progress(done, total, score):
        lines_seen.append(len(output.read_text(encoding="utf-8").splitlines()))

    scores = run_answers(
        questions_pair(), hits_pair(), FakeChat(GOOD_REPLY), INDEX_CHUNKS, 0.52, output=output, on_progress=progress
    )
    assert [s.id for s in scores] == ["Q01", "Q03"]
    assert lines_seen == [1, 2]  # a linha já estava no arquivo quando o progresso foi avisado


def test_run_answers_resume_skips_what_is_already_done(tmp_path):
    output = tmp_path / "r.jsonl"
    append_score(output, make_score(id="Q01", seconds=9.0))
    chat = FakeChat(GOOD_REPLY)
    scores = run_answers(questions_pair(), hits_pair(), chat, INDEX_CHUNKS, 0.52, output=output, resume=True)
    assert chat.calls == 1  # só a Q03
    assert [s.id for s in scores] == ["Q01", "Q03"] and scores[0].seconds == 9.0
    assert [s.id for s in load_scores(output)] == ["Q01", "Q03"]


def test_run_answers_without_resume_starts_the_file_over(tmp_path):
    output = tmp_path / "r.jsonl"
    append_score(output, make_score(id="Q01", seconds=9.0))
    chat = FakeChat(GOOD_REPLY)
    run_answers(questions_pair(), hits_pair(), chat, INDEX_CHUNKS, 0.52, output=output, resume=False)
    assert chat.calls == 2 and [s.id for s in load_scores(output)] == ["Q01", "Q03"]
    assert load_scores(output)[0].seconds != 9.0


# ---------- reavaliação de respostas já gravadas ----------


def test_rescore_applies_the_current_answer_key_to_the_saved_text():
    saved = make_score(
        id="Q01",
        text="O limite é 30% e R$ 2.000.000. [Fonte: IN RFB 2.091/2022, art. 2º]",
        items_found=["30%"],
        items_missing=["R$ 2 milhões"],
        cited=[ART_2],
        cited_recall=1.0,
    )
    [updated] = rescore([question()], [saved])  # o gabarito atual reconhece "2.000.000"
    assert updated.items_found == ["30%", "R$ 2 milhões"] and updated.items_missing == []
    assert updated.text == saved.text and updated.seconds == saved.seconds  # o resto não muda


def test_rescore_can_also_remove_items_the_new_key_no_longer_finds():
    stricter = question(items=(Item("30%", ("trinta e um por cento",)),))
    saved = make_score(id="Q01", text="30%. [Fonte: IN RFB 2.091/2022, art. 2º]", items_found=["30%"], items_missing=[])
    [updated] = rescore([stricter], [saved])
    assert updated.items_found == [] and updated.items_missing == ["30%"] and not updated.correct


def test_rescore_recomputes_the_citation_recall_with_the_current_articles():
    saved = make_score(
        id="Q01",
        text="X. [Fonte: IN RFB 2.091/2022, art. 5º]",
        cited=[ART_5],
        cited_recall=0.0,
        items_found=["30%", "R$ 2 milhões"],
        items_missing=[],
    )
    [updated] = rescore([question(articles=(ART_5,))], [saved])
    assert updated.cited_recall == 1.0


def test_rescore_recomputes_the_citations_from_the_saved_text():
    saved = make_score(id="Q01", text="X. [Fonte: IN RFB 2.091/2022, art. 2º]", cited=[], cited_recall=0.0)
    [updated] = rescore([question()], [saved])
    assert updated.cited == [ART_2] and updated.cited_recall == 1.0


def test_rescore_takes_the_kind_from_the_current_questions():
    saved = make_score(id="Q01", kind="answer")
    [updated] = rescore([question(kind="refuse", group="out_of_corpus", articles=(), items=())], [saved])
    assert updated.kind == "refuse"


def test_rescore_keeps_refusals_and_refreshes_the_missing_labels():
    saved = make_score(
        id="Q01",
        refused=True,
        text=REFUSAL_MESSAGE,
        cited=[],
        cited_recall=0.0,
        items_found=[],
        items_missing=["antigo"],
    )
    [updated] = rescore([question()], [saved])
    assert updated.refused and updated.items_missing == ["30%", "R$ 2 milhões"] and updated.cited == []


def test_rescore_takes_group_and_kind_from_the_current_questions():
    saved = make_score(id="Q01", group="fact", kind="answer")
    [updated] = rescore([question(group="hard")], [saved])
    assert updated.group == "hard"


def test_rescore_rejects_a_result_without_a_matching_question():
    with pytest.raises(QuestionsError, match="Q99"):
        rescore([question()], [make_score(id="Q99")])


def test_rescore_command_rewrites_the_results_and_the_report(workspace, capsys):
    tmp = workspace["tmp"]
    output, report = tmp / "r.jsonl", tmp / "r.md"
    answers = ["answers", *common(workspace), "--output", str(output), "--report", str(report)]
    assert main(answers, environ={}, llm_factory=FakeLLM("Sem o termo. [Fonte: norma-teste, art. 1º]")) == 0
    assert load_scores(output)[0].items_missing == ["cita arrolamento"]  # a resposta não traz a palavra do gabarito

    data = json.loads(workspace["questions"].read_text(encoding="utf-8"))
    data[0]["items"] = [{"label": "cita o termo", "any_of": ["termo"]}]  # gabarito corrigido
    workspace["questions"].write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    code = main(
        [
            "rescore",
            "--questions",
            str(workspace["questions"]),
            "--input",
            str(output),
            "--report",
            str(report),
            "--model",
            "modelo-x",
        ],
        environ={},
        llm_factory=FakeLLM(),
    )
    assert code == 0
    assert load_scores(output)[0].items_found == ["cita o termo"]  # reescrito no próprio arquivo
    text = report.read_text(encoding="utf-8")
    assert "modelo-x" in text and "Total" in text
    assert "Total" in capsys.readouterr().out


def test_rescore_command_does_not_need_the_index_or_the_model(workspace):
    output = workspace["tmp"] / "r.jsonl"
    append_score(output, make_score(id="Q01", text="Sobre arrolamento. [Fonte: norma-teste, art. 1º]"))
    llm = FakeLLM()
    code = main(
        [
            "rescore",
            "--questions",
            str(workspace["questions"]),
            "--input",
            str(output),
            "--model",
            "m",
            "--report",
            str(workspace["tmp"] / "r.md"),
        ],
        environ={},
        llm_factory=llm,
    )
    assert code == 0 and llm.settings_seen == []  # nem o Ollama nem o índice foram tocados


def test_rescore_command_reports_a_missing_input_file(workspace, capsys):
    code = main(
        [
            "rescore",
            "--questions",
            str(workspace["questions"]),
            "--input",
            str(workspace["tmp"] / "nada.jsonl"),
            "--model",
            "m",
        ],
        environ={},
        llm_factory=FakeLLM(),
    )
    assert code == 1 and capsys.readouterr().err.startswith("Erro:")


# ---------- resumo e relatório ----------


def test_summarize_groups_and_totals():
    scores = [
        make_score(
            id="Q01",
            group="fact",
            items_found=["a"],
            items_missing=[],
            cited_recall=1.0,
            retrieval_recall=1.0,
            seconds=10.0,
        ),
        make_score(
            id="Q03",
            group="fact",
            items_found=["a"],
            items_missing=["b"],
            cited_recall=0.5,
            retrieval_recall=0.0,
            seconds=20.0,
            invalid_citations=["X"],
        ),
        make_score(
            id="Q04",
            group="hard",
            refused=True,
            items_found=[],
            items_missing=["a", "b"],
            cited=[],
            cited_recall=0.0,
            retrieval_recall=1.0,
            seconds=0.1,
        ),
        make_score(
            id="Q05",
            group="out_of_corpus",
            kind="refuse",
            refused=True,
            items_found=[],
            items_missing=[],
            cited=[],
            cited_recall=1.0,
            retrieval_recall=1.0,
            seconds=0.1,
        ),
        make_score(
            id="Q06",
            group="out_of_corpus",
            kind="refuse",
            refused=False,
            items_found=[],
            items_missing=[],
            cited=[],
            cited_recall=1.0,
            retrieval_recall=1.0,
            seconds=30.0,
        ),
    ]
    rows = {row.group: row for row in summarize(scores)}
    fact = rows["fact"]
    assert (fact.n, fact.correct) == (2, 1)
    assert fact.mean_item_score == 0.75 and fact.mean_cited_recall == 0.75 and fact.mean_retrieval_recall == 0.5
    assert fact.invalid_citations == 1 and fact.mean_seconds == 15.0
    hard = rows["hard"]
    assert hard.false_refusals == 1 and hard.correct == 0
    refuse = rows["out_of_corpus"]
    assert (refuse.n, refuse.correct, refuse.missed_refusals) == (2, 1, 1)
    assert refuse.mean_item_score is None  # não se aplica a perguntas recusáveis
    total = rows["total"]
    assert (total.n, total.correct, total.false_refusals, total.missed_refusals) == (5, 2, 1, 1)
    assert total.mean_seconds == pytest.approx((10 + 20 + 0.1 + 0.1 + 30) / 5)


def test_report_has_parameters_groups_total_and_the_failures():
    scores = [
        make_score(id="Q01", group="fact"),
        make_score(
            id="Q03",
            group="hard",
            items_found=["a"],
            items_missing=["b"],
            invalid_citations=["IN RFB 2.091/2022, art. 99"],
        ),
    ]
    report = render_report("qwen2.5:3b", k=4, min_similarity=0.52, scores=scores, today="2026-10-08")
    assert "qwen2.5:3b" in report and "k = 4" in report and "0,52" in report and "2026-10-08" in report
    assert "constante do RRF: 60" in report
    assert "constante do RRF: 7" in render_report(
        "m", k=4, min_similarity=0.5, scores=scores, today="2026-10-08", rrf_k=7
    )
    assert "Fatos pontuais" in report and "Difíceis" in report and "Total" in report
    assert "Q03" in report and "b" in report and "art. 99" in report  # a falha aparece com o item que faltou
    assert "Q01" not in report.split("Falhas")[-1]  # a pergunta correta não é listada como falha


# ---------- linha de comando ----------

VOCABULARY = ["arrolamento", "cancelamento", "imovel"]


def fake_embed(texts):
    vectors = []
    for text in texts:
        words = text.lower().replace(".", " ").replace("º", " ").split()
        vectors.append([float(words.count(word)) for word in VOCABULARY])
    return vectors


class FakeLLM:
    def __init__(self, reply="Resposta de arrolamento. [Fonte: norma-teste, art. 1º]"):
        self.chat = FakeChat(reply)
        self.settings_seen = []

    def __call__(self, settings):
        self.settings_seen.append(settings)
        return fake_embed, self.chat


@pytest.fixture
def workspace(tmp_path):
    chunks = [
        Chunk("norma-teste", "1", "", "Art. 1º Texto sobre arrolamento."),
        Chunk("norma-teste", "2", "", "Art. 2º Texto sobre cancelamento."),
    ]
    index_path = tmp_path / "index.json"
    save_index(build_index(chunks, fake_embed, "bge-m3"), index_path)
    questions = [
        {
            "id": "Q01",
            "group": "fact",
            "kind": "answer",
            "question": "arrolamento",
            "articles": ["norma-teste, art. 1º"],
            "items": [{"label": "cita arrolamento", "any_of": ["arrolamento"]}],
        },
        {"id": "Q02", "group": "out_of_corpus", "kind": "refuse", "question": "imovel", "articles": [], "items": []},
    ]
    questions_path = tmp_path / "perguntas.json"
    questions_path.write_text(json.dumps(questions, ensure_ascii=False), encoding="utf-8")
    return {"tmp": tmp_path, "index": index_path, "questions": questions_path}


def common(workspace) -> list[str]:
    return ["--index", str(workspace["index"]), "--questions", str(workspace["questions"])]


def test_retrieval_command_prints_and_saves_the_calibration_report(workspace, capsys):
    report = workspace["tmp"] / "retrieval.md"
    code = main(["retrieval", *common(workspace), "--report", str(report)], environ={}, llm_factory=FakeLLM())
    assert code == 0
    out = capsys.readouterr().out
    assert "Recuperação" in out and "Limiar" in out
    assert report.read_text(encoding="utf-8") == out.rstrip("\n") + "\n" or "Recuperação" in report.read_text(
        encoding="utf-8"
    )


def test_retrieval_command_embeds_each_question_only_once_even_with_the_rrf_sweep(workspace, capsys):
    embedded = []

    def embed(texts):
        embedded.append(list(texts))
        return fake_embed(texts)

    code = main(
        ["retrieval", *common(workspace), "--report", str(workspace["tmp"] / "r.md")],
        environ={},
        llm_factory=lambda settings: (embed, FakeChat("x")),
    )
    assert code == 0
    assert len(embedded) == 2  # uma pergunta = um embedding, mesmo com a busca repetida para cada k do RRF
    assert "k do RRF" in capsys.readouterr().out


def test_retrieval_command_never_calls_the_chat(workspace):
    llm = FakeLLM()
    assert (
        main(["retrieval", *common(workspace), "--report", str(workspace["tmp"] / "r.md")], environ={}, llm_factory=llm)
        == 0
    )
    assert llm.chat.calls == 0


def test_answers_command_runs_writes_jsonl_and_report(workspace, capsys):
    output, report = workspace["tmp"] / "r.jsonl", workspace["tmp"] / "r.md"
    llm = FakeLLM()
    code = main(
        ["answers", *common(workspace), "--model", "modelo-x", "--output", str(output), "--report", str(report)],
        environ={},
        llm_factory=llm,
    )
    assert code == 0
    assert llm.settings_seen[0].chat_model == "modelo-x"
    scores = load_scores(output)
    assert [(s.id, s.correct) for s in scores] == [("Q01", True), ("Q02", True)]
    assert llm.chat.calls == 1  # a Q02 é recusada pelo limiar, sem chamar o modelo
    assert "modelo-x" in report.read_text(encoding="utf-8")
    assert "Total" in capsys.readouterr().out


def test_rrf_k_option_is_used_and_shown_in_both_reports(workspace, capsys):
    tmp = workspace["tmp"]
    assert (
        main(
            ["retrieval", *common(workspace), "--rrf-k", "7", "--report", str(tmp / "b.md")],
            environ={},
            llm_factory=FakeLLM(),
        )
        == 0
    )
    assert "usada nas demais tabelas: 7" in capsys.readouterr().out
    args = [
        "answers",
        *common(workspace),
        "--rrf-k",
        "7",
        "--output",
        str(tmp / "r.jsonl"),
        "--report",
        str(tmp / "r.md"),
    ]
    assert main(args, environ={}, llm_factory=FakeLLM()) == 0
    assert "constante do RRF: 7" in capsys.readouterr().out
    assert main(args, environ={"RAG_RRF_K": "9"}, llm_factory=FakeLLM()) == 0  # a opção vence o ambiente
    assert "constante do RRF: 7" in capsys.readouterr().out
    assert main([a for a in args if a not in ("--rrf-k", "7")], environ={"RAG_RRF_K": "9"}, llm_factory=FakeLLM()) == 0
    assert "constante do RRF: 9" in capsys.readouterr().out


@pytest.mark.parametrize("command", ["retrieval", "answers"])
def test_both_commands_search_with_the_configured_rrf_k(workspace, monkeypatch, command):
    from eval import avaliar

    seen = []
    real = avaliar.retrieve

    def spy(questions, index, embed, k, rrf_k=60):
        seen.append(rrf_k)
        return real(questions, index, embed, k, rrf_k)

    monkeypatch.setattr(avaliar, "retrieve", spy)
    tmp = workspace["tmp"]
    args = [command, *common(workspace), "--rrf-k", "7", "--report", str(tmp / "r.md")]
    if command == "answers":
        args += ["--output", str(tmp / "r.jsonl")]
    assert main(args, environ={}, llm_factory=FakeLLM()) == 0
    assert seen == [7]


def test_answers_command_only_runs_the_chosen_questions(workspace):
    output = workspace["tmp"] / "r.jsonl"
    code = main(
        [
            "answers",
            *common(workspace),
            "--only",
            "Q01",
            "--output",
            str(output),
            "--report",
            str(workspace["tmp"] / "r.md"),
        ],
        environ={},
        llm_factory=FakeLLM(),
    )
    assert code == 0 and [s.id for s in load_scores(output)] == ["Q01"]


def test_answers_command_resume_does_not_repeat_finished_questions(workspace):
    args = [
        "answers",
        *common(workspace),
        "--output",
        str(workspace["tmp"] / "r.jsonl"),
        "--report",
        str(workspace["tmp"] / "r.md"),
    ]
    first = FakeLLM()
    assert main(args, environ={}, llm_factory=first) == 0 and first.chat.calls == 1
    second = FakeLLM()
    assert main([*args, "--resume"], environ={}, llm_factory=second) == 0
    assert second.chat.calls == 0


def test_options_reach_the_settings(workspace):
    llm = FakeLLM()
    args = [
        "answers",
        *common(workspace),
        "--model",
        "modelo-y",
        "--min-similarity",
        "0.9",
        "-k",
        "1",
        "--host",
        "http://outro:11434",
        "--output",
        str(workspace["tmp"] / "r.jsonl"),
        "--report",
        str(workspace["tmp"] / "r.md"),
    ]
    assert main(args, environ={}, llm_factory=llm) == 0
    settings = llm.settings_seen[0]
    assert (settings.chat_model, settings.min_similarity, settings.top_k, settings.ollama_host) == (
        "modelo-y",
        0.9,
        1,
        "http://outro:11434",
    )


def test_embed_model_option_is_checked_against_the_index(workspace, capsys):
    code = main(["retrieval", *common(workspace), "--embed-model", "outro-modelo"], environ={}, llm_factory=FakeLLM())
    err = capsys.readouterr().err
    assert code == 1 and "bge-m3" in err and "outro-modelo" in err


def test_retrieval_table_goes_up_to_max_k(workspace, capsys):
    args = ["retrieval", *common(workspace), "--max-k", "6", "--report", str(workspace["tmp"] / "r.md")]
    assert main(args, environ={}, llm_factory=FakeLLM()) == 0
    out = capsys.readouterr().out
    assert "| 6 |" in out and "| 7 |" not in out


def test_default_output_paths_are_relative_and_named_after_the_model(workspace, monkeypatch):
    monkeypatch.chdir(workspace["tmp"])  # os caminhos padrão são relativos ao diretório atual
    assert main(["answers", *common(workspace), "--model", "Qwen2.5:3B"], environ={}, llm_factory=FakeLLM()) == 0
    assert (workspace["tmp"] / "eval" / "relatorios" / "respostas-qwen2.5-3b-k4.jsonl").exists()
    assert (workspace["tmp"] / "eval" / "relatorios" / "respostas-qwen2.5-3b-k4.md").exists()
    assert main(["retrieval", *common(workspace)], environ={}, llm_factory=FakeLLM()) == 0
    assert (workspace["tmp"] / "eval" / "relatorios" / "busca.md").exists()


def test_answers_command_reports_progress_on_stderr_and_dates_the_report(workspace, capsys):
    args = [
        "answers",
        *common(workspace),
        "--output",
        str(workspace["tmp"] / "r.jsonl"),
        "--report",
        str(workspace["tmp"] / "r.md"),
    ]
    assert main(args, environ={}, llm_factory=FakeLLM()) == 0
    out = capsys.readouterr()
    assert "[1/2] Q01 ok" in out.err and "[2/2] Q02 ok" in out.err
    assert date.today().isoformat() in out.out


def test_unknown_question_id_in_only_is_an_error(workspace, capsys):
    code = main(["answers", *common(workspace), "--only", "Q99"], environ={}, llm_factory=FakeLLM())
    assert code == 1 and capsys.readouterr().err.startswith("Erro:")


def test_missing_index_is_reported_without_traceback(workspace, capsys):
    code = main(
        ["retrieval", "--index", str(workspace["tmp"] / "nao-existe.json"), "--questions", str(workspace["questions"])],
        environ={},
        llm_factory=FakeLLM(),
    )
    err = capsys.readouterr().err
    assert code == 1 and err.startswith("Erro:") and "Traceback" not in err


def test_missing_questions_file_is_reported(workspace, capsys):
    code = main(
        ["retrieval", "--index", str(workspace["index"]), "--questions", str(workspace["tmp"] / "x.json")],
        environ={},
        llm_factory=FakeLLM(),
    )
    assert code == 1 and "não encontrado" in capsys.readouterr().err


def test_questions_with_an_article_missing_from_the_index_are_rejected(workspace, capsys):
    data = json.loads(workspace["questions"].read_text(encoding="utf-8"))
    data[0]["articles"] = ["norma-teste, art. 77"]
    workspace["questions"].write_text(json.dumps(data), encoding="utf-8")
    code = main(["retrieval", *common(workspace)], environ={}, llm_factory=FakeLLM())
    assert code == 1 and "art. 77" in capsys.readouterr().err


def test_bad_usage_exits_with_code_2():
    with pytest.raises(SystemExit) as stop:
        main([], environ={}, llm_factory=FakeLLM())
    assert stop.value.code == 2


def test_rescore_command_requires_the_model_name_for_the_report_header(workspace):
    with pytest.raises(SystemExit) as stop:
        main(
            ["rescore", "--questions", str(workspace["questions"]), "--input", str(workspace["tmp"] / "r.jsonl")],
            environ={},
            llm_factory=FakeLLM(),
        )
    assert stop.value.code == 2


def test_rescore_command_writes_to_another_file_when_asked(workspace):
    source, target = workspace["tmp"] / "r.jsonl", workspace["tmp"] / "novo.jsonl"
    append_score(source, make_score(id="Q01", text="Sobre arrolamento. [Fonte: norma-teste, art. 1º]"))
    before = source.read_text(encoding="utf-8")
    code = main(
        [
            "rescore",
            "--questions",
            str(workspace["questions"]),
            "--input",
            str(source),
            "--output",
            str(target),
            "--model",
            "m",
        ],
        environ={},
        llm_factory=FakeLLM(),
    )
    assert (
        code == 0
        and source.read_text(encoding="utf-8") == before
        and load_scores(target)[0].items_found == ["cita arrolamento"]
    )
    assert (workspace["tmp"] / "novo.md").exists()  # o relatório acompanha o arquivo de saída


# ---------- comparação entre rodadas ----------


def comparison_runs():
    answered = make_score(id="Q01", seconds=10.0)
    half = make_score(id="Q02", items_found=["a"], items_missing=["b"], seconds=20.0)
    refusal = make_score(
        id="Q03", kind="refuse", group="out_of_corpus", refused=True, items_found=[], items_missing=[], seconds=0.0
    )
    slower = [make_score(id="Q01", seconds=100.0), make_score(id="Q02", seconds=300.0), refusal]
    return [answered, half, refusal], slower


def test_render_comparison_summarizes_each_run_and_marks_each_question():
    first, second = comparison_runs()
    report = render_comparison(["3b", "7b"], [first, second], today="2026-10-08")
    assert "2026-10-08" in report and "| Métrica | 3b | 7b |" in report
    assert "| Respostas corretas | 2 de 3 | 3 de 3 |" in report
    assert "| Itens do gabarito presentes | 75% | 100% |" in report
    assert "| Tempo médio das respondidas (s) | 15,0 | 200,0 |" in report  # a recusa (0 s) não entra na média
    assert "| Q01 | Fatos pontuais | sim · 100% · 10 s | sim · 100% · 100 s |" in report
    assert "| Q02 | Fatos pontuais | não · 50% · 20 s | sim · 100% · 300 s |" in report
    assert "| Q03 | Fora do corpus | recusou | recusou |" in report


def test_render_comparison_counts_errors_of_each_kind_per_run():
    refused_wrongly = dict(refused=True, items_found=[], items_missing=["a"])
    answered_wrongly = dict(
        kind="refuse", group="out_of_corpus", refused=False, items_found=[], items_missing=[], seconds=42.0
    )
    refused_rightly = dict(kind="refuse", group="out_of_corpus", refused=True, items_found=[], items_missing=[])
    wrong_a = [
        make_score(id="Q01", **refused_wrongly),
        make_score(id="Q02", **refused_wrongly),
        make_score(id="Q03", **answered_wrongly),
        make_score(id="Q04", invalid_citations=["X", "Y"]),
    ]
    clean_b = [
        make_score(id="Q01"),
        make_score(id="Q02"),
        make_score(id="Q03", **refused_rightly),
        make_score(id="Q04"),
    ]
    report = render_comparison(["a", "b"], [wrong_a, clean_b], today="2026-10-08")
    assert "| Recusas indevidas | 2 | 0 |" in report  # contagens diferentes: não dá para trocar uma pela outra
    assert "| Respostas indevidas | 1 | 0 |" in report
    assert "| Citações inexistentes | 2 | 0 |" in report  # conta as citações, e não as perguntas
    assert "| Q03 | Fora do corpus | respondeu · 42 s | recusou |" in report


def test_render_comparison_requires_the_same_questions_in_every_run():
    first, second = comparison_runs()
    with pytest.raises(ResultsError, match="mesmas perguntas"):
        render_comparison(["a", "b"], [first, second[:2]], today="2026-10-08")


def test_render_comparison_requires_one_name_per_run():
    first, second = comparison_runs()
    with pytest.raises(ResultsError, match="nomes"):
        render_comparison(["só um"], [first, second], today="2026-10-08")


def test_compare_command_writes_the_report(workspace, capsys):
    first, second = comparison_runs()
    file_a, file_b, report = workspace["tmp"] / "a.jsonl", workspace["tmp"] / "b.jsonl", workspace["tmp"] / "c.md"
    for path, scores in ((file_a, first), (file_b, second)):
        for score in scores:
            append_score(path, score)
    code = main(
        ["compare", "--inputs", str(file_a), str(file_b), "--names", "3b", "7b", "--report", str(report)],
        environ={},
        llm_factory=FakeLLM(),
    )
    assert code == 0
    assert "| Métrica | 3b | 7b |" in report.read_text(encoding="utf-8")
    assert "Respostas corretas" in capsys.readouterr().out


def test_compare_command_reports_wrong_number_of_names_and_missing_files(workspace, capsys):
    path = workspace["tmp"] / "a.jsonl"
    append_score(path, make_score())
    assert (
        main(["compare", "--inputs", str(path), str(path), "--names", "só-um"], environ={}, llm_factory=FakeLLM()) == 1
    )
    assert "nomes" in capsys.readouterr().err
    assert (
        main(
            ["compare", "--inputs", str(path), str(workspace["tmp"] / "x.jsonl"), "--names", "a", "b"],
            environ={},
            llm_factory=FakeLLM(),
        )
        == 1
    )
    err = capsys.readouterr().err
    assert err.startswith("Erro:") and "não encontrado" in err
