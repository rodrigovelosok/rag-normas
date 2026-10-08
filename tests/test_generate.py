"""Testes da geração (RF05–RF07, RF10, G1–G3): prompt, recusa, conferência das citações e saída."""

import pytest

from rag_normas.generate import (
    DISCLAIMER,
    REFUSAL_MESSAGE,
    REMINDER,
    Answer,
    answer,
    build_messages,
    extract_citations,
    format_output,
)
from rag_normas.ingest import Chunk
from rag_normas.search import Hit

IN_2 = Chunk("IN RFB 2.091/2022", "2", "", "Art. 2º O arrolamento é feito quando o total dos débitos for superior a R$ 2.000.000,00.")
IN_5 = Chunk("IN RFB 2.091/2022", "5", "", "Art. 5º O arrolamento recai sobre bens suficientes.")
LEI_64A = Chunk("Lei 9.532/1997", "64-A", "", "Art. 64-A. O registro do arrolamento nos órgãos competentes.")
DECREE_1 = Chunk("Decreto 7.573/2011", "1", "", "Art. 1º O valor do crédito passa a ser de R$ 2.000.000,00.")
INDEX_CHUNKS = [IN_2, IN_5, LEI_64A, DECREE_1]  # tudo o que existe no índice


def hit(chunk: Chunk, similarity: float = 0.7) -> Hit:
    return Hit(chunk, similarity=similarity, bm25=0.0, score=0.0)


class FakeChat:
    """chat falso: devolve uma resposta fixa e guarda as chamadas, para provar quando NÃO foi chamado."""

    def __init__(self, reply: str = "Resposta. [Fonte: IN RFB 2.091/2022, art. 2º]"):
        self.reply = reply
        self.calls: list[list[dict[str, str]]] = []

    def __call__(self, messages):
        self.calls.append(messages)
        return self.reply


def run(hits, chat=None, min_similarity=0.52, question="Quando o arrolamento é feito?"):
    chat = chat or FakeChat()
    return answer(question, hits, chat, INDEX_CHUNKS, min_similarity), chat


# ---------- build_messages ----------

def test_build_messages_has_system_then_user():
    messages = build_messages("Pergunta?", [hit(IN_2)])
    assert [m["role"] for m in messages] == ["system", "user"]


def test_system_prompt_gives_the_rules():
    system = build_messages("Pergunta?", [hit(IN_2)])[0]["content"]
    assert "[Fonte:" in system  # o formato da citação
    assert "apenas" in system.lower()  # só os fragmentos


def test_system_prompt_does_not_teach_the_refusal_phrase():
    # Achado com o qwen2.5:3b: com essa regra no prompt, ele recusa também o que a norma responde.
    # Quem recusa é o código, pelo limiar de similaridade.
    system = build_messages("Pergunta?", [hit(IN_2)])[0]["content"]
    assert REFUSAL_MESSAGE not in system


def test_user_message_labels_each_fragment_in_order_then_asks_the_question():
    user = build_messages("Qual o valor mínimo?", [hit(IN_2), hit(DECREE_1)])[1]["content"]
    label_2 = f"[Fonte: {IN_2.reference}]\n{IN_2.text}"
    label_decree = f"[Fonte: {DECREE_1.reference}]\n{DECREE_1.text}"
    assert label_2 in user and label_decree in user
    assert user.index(label_2) < user.index(label_decree)  # mesma ordem dos hits
    assert user.index("Pergunta: Qual o valor mínimo?") > user.index(label_decree)  # a pergunta vem depois dos fragmentos


def test_user_message_ends_with_the_citation_reminder():
    # Achado com o qwen2.5:3b: sem o lembrete no fim, ele esquecia o formato [Fonte: ...].
    user = build_messages("Pergunta?", [hit(IN_2)])[1]["content"]
    assert user.rstrip().endswith(REMINDER)
    assert "[Fonte:" in REMINDER


# ---------- extract_citations ----------

def test_extract_finds_one_citation():
    assert extract_citations("Vale R$ 2 milhões. [Fonte: IN RFB 2.091/2022, art. 2º]") == ["IN RFB 2.091/2022, art. 2º"]


def test_extract_keeps_order_and_drops_repeats():
    text = "A [Fonte: Lei 9.532/1997, art. 64-A] B [Fonte: IN RFB 2.091/2022, art. 5º] C [Fonte: Lei 9.532/1997, art. 64-A]"
    assert extract_citations(text) == ["Lei 9.532/1997, art. 64-A", "IN RFB 2.091/2022, art. 5º"]


def test_extract_does_not_run_across_two_brackets():
    text = "[Fonte: A, art. 1º] e depois [Fonte: B, art. 2º]"
    assert extract_citations(text) == ["A, art. 1º", "B, art. 2º"]


def test_extract_tolerates_extra_spaces():
    assert extract_citations("[Fonte:   IN RFB 2.091/2022,   art. 2º  ]") == ["IN RFB 2.091/2022, art. 2º"]


def test_extract_accepts_degree_sign_in_place_of_ordinal():
    assert extract_citations("[Fonte: IN RFB 2.091/2022, art. 2°]") == ["IN RFB 2.091/2022, art. 2º"]


def test_extract_ignores_other_brackets_and_plain_text():
    assert extract_citations("Veja [1] e (art. 2º) e [nota: algo].") == []


def test_extract_ignores_an_empty_citation():
    assert extract_citations("Texto [Fonte: ] e [Fonte:   ].") == []


def test_extract_on_empty_text():
    assert extract_citations("") == []


# ---------- answer: recusa (RF07, G2) ----------

def test_refuses_without_hits_and_does_not_call_chat():
    result, chat = run([])
    assert result.refused and result.text == REFUSAL_MESSAGE
    assert chat.calls == []


def test_refuses_below_threshold_and_does_not_call_chat():
    result, chat = run([hit(IN_2, 0.51), hit(IN_5, 0.40)], min_similarity=0.52)
    assert result.refused and result.text == REFUSAL_MESSAGE
    assert result.sources == []
    assert chat.calls == []


def test_threshold_uses_the_best_similarity_not_the_first_hit():
    # Os hits vêm na ordem do RRF, e o primeiro pode ter similaridade baixa.
    result, chat = run([hit(IN_5, 0.30), hit(IN_2, 0.60)], min_similarity=0.52)
    assert not result.refused
    assert len(chat.calls) == 1


def test_similarity_equal_to_threshold_is_not_refused():
    result, _ = run([hit(IN_2, 0.52)], min_similarity=0.52)
    assert not result.refused


def test_model_that_replies_the_refusal_is_a_refusal():
    chat = FakeChat(REFUSAL_MESSAGE + "\n")
    result, _ = run([hit(IN_2)], chat=chat)
    assert result.refused and result.text == REFUSAL_MESSAGE
    assert result.sources == [] and not result.uncited  # recusa não leva aviso de "sem citação"


# ---------- answer: resposta normal ----------

def test_normal_answer_returns_text_and_consulted_sources():
    result, chat = run([hit(IN_2), hit(DECREE_1)], chat=FakeChat("  Sim. [Fonte: IN RFB 2.091/2022, art. 2º]\n"))
    assert not result.refused
    assert result.text == "Sim. [Fonte: IN RFB 2.091/2022, art. 2º]"  # sem espaços nas pontas
    assert result.sources == [IN_2.reference, DECREE_1.reference]
    assert result.invalid_citations == [] and result.unretrieved_citations == [] and not result.uncited


def test_chat_receives_exactly_the_built_messages():
    hits = [hit(IN_2), hit(IN_5)]
    _, chat = run(hits, question="Pergunta X?")
    assert chat.calls == [build_messages("Pergunta X?", hits)]


# ---------- answer: conferência das citações (RF10, G1) ----------

def test_citation_of_an_article_that_is_not_in_the_index_is_invalid():
    chat = FakeChat("Texto. [Fonte: IN RFB 2.091/2022, art. 99]")
    result, _ = run([hit(IN_2)], chat=chat)
    assert result.invalid_citations == ["IN RFB 2.091/2022, art. 99"]
    assert result.unretrieved_citations == []


def test_citation_of_a_wrong_norm_is_invalid():
    chat = FakeChat("Texto. [Fonte: Lei 1/2000, art. 2º]")
    result, _ = run([hit(IN_2)], chat=chat)
    assert result.invalid_citations == ["Lei 1/2000, art. 2º"]


def test_citation_with_paragraph_counts_as_the_article():
    # O modelo cita com mais precisão que o índice: "art. 2º, § 1º" é o art. 2º, que existe.
    chat = FakeChat("Texto. [Fonte: IN RFB 2.091/2022, art. 2º, § 1º]")
    result, _ = run([hit(IN_2)], chat=chat)
    assert result.invalid_citations == [] and result.unretrieved_citations == []


def test_citation_with_paragraph_of_a_missing_article_is_still_invalid():
    chat = FakeChat("Texto. [Fonte: IN RFB 2.091/2022, art. 99, § 1º]")
    result, _ = run([hit(IN_2)], chat=chat)
    assert result.invalid_citations == ["IN RFB 2.091/2022, art. 99, § 1º"]


def test_citation_without_the_ordinal_sign_counts_as_the_article():
    chat = FakeChat("Texto. [Fonte: IN RFB 2.091/2022, art. 2]")
    result, _ = run([hit(IN_2)], chat=chat)
    assert result.invalid_citations == []


def test_citation_with_capital_a_in_art_counts_as_the_article():
    chat = FakeChat("Texto. [Fonte: IN RFB 2.091/2022, Art. 2º]")
    result, _ = run([hit(IN_2)], chat=chat)
    assert result.invalid_citations == []


def test_citation_of_a_lettered_article_is_not_confused_with_the_plain_one():
    # "art. 64" não é "art. 64-A".
    chat = FakeChat("Texto. [Fonte: Lei 9.532/1997, art. 64]")
    result, _ = run([hit(LEI_64A)], chat=chat)
    assert result.invalid_citations == ["Lei 9.532/1997, art. 64"]


def test_citation_in_the_index_but_not_retrieved_is_only_recorded():
    chat = FakeChat("Texto. [Fonte: Lei 9.532/1997, art. 64-A]")
    result, _ = run([hit(IN_2)], chat=chat)
    assert result.invalid_citations == []
    assert result.unretrieved_citations == ["Lei 9.532/1997, art. 64-A"]


def test_valid_and_invalid_citations_are_separated():
    chat = FakeChat("A [Fonte: IN RFB 2.091/2022, art. 2º] B [Fonte: IN RFB 2.091/2022, art. 77]")
    result, _ = run([hit(IN_2)], chat=chat)
    assert result.invalid_citations == ["IN RFB 2.091/2022, art. 77"]
    assert result.unretrieved_citations == []


def test_answer_without_any_citation_is_flagged():
    result, _ = run([hit(IN_2)], chat=FakeChat("O arrolamento é feito acima de R$ 2 milhões."))
    assert result.uncited
    assert result.invalid_citations == []


# ---------- format_output (RF06, G3) ----------

def test_output_of_an_answer_lists_sources_and_ends_with_disclaimer():
    result, _ = run([hit(IN_2), hit(DECREE_1)])
    output = format_output(result)
    assert output.startswith(result.text)
    assert "Fontes consultadas:" in output
    assert f"- {IN_2.reference}" in output and f"- {DECREE_1.reference}" in output
    assert output.endswith(DISCLAIMER)
    assert output.count(DISCLAIMER) == 1


def test_output_of_a_refusal_has_no_sources_and_still_has_the_disclaimer():
    result, _ = run([])
    output = format_output(result)
    assert output.startswith(REFUSAL_MESSAGE)
    assert "Fontes consultadas" not in output
    assert output.endswith(DISCLAIMER)


def test_output_warns_about_an_invalid_citation_before_the_disclaimer():
    result, _ = run([hit(IN_2)], chat=FakeChat("Texto. [Fonte: IN RFB 2.091/2022, art. 99]"))
    output = format_output(result)
    assert "ATENÇÃO" in output and "IN RFB 2.091/2022, art. 99" in output
    assert output.index("ATENÇÃO") < output.index(DISCLAIMER)
    assert output.endswith(DISCLAIMER)


def test_output_warns_when_there_is_no_citation():
    result, _ = run([hit(IN_2)], chat=FakeChat("Sem citar nada."))
    output = format_output(result)
    assert "ATENÇÃO" in output and "[Fonte: ...]" in output
    assert output.endswith(DISCLAIMER)


def test_output_has_no_warning_for_a_clean_answer_or_an_unretrieved_citation():
    clean, _ = run([hit(IN_2)])
    assert "ATENÇÃO" not in format_output(clean)
    unretrieved, _ = run([hit(IN_2)], chat=FakeChat("X. [Fonte: Lei 9.532/1997, art. 64-A]"))
    assert "ATENÇÃO" not in format_output(unretrieved)


def test_answer_is_immutable():
    result, _ = run([hit(IN_2)])
    with pytest.raises(Exception):
        result.text = "outro"  # type: ignore[misc]
