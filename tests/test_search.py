"""Testes da busca híbrida (RF04): tokenização, BM25, cosseno, RRF e a junção de tudo.

Nenhum teste aqui usa o Ollama: o `embed` é uma função falsa que devolve vetores fixos (RNF03).
"""

from pathlib import Path

import pytest

from rag_normas.ingest import Chunk, load_corpus
from rag_normas.search import Hit, bm25_scores, cosine, hybrid_search, rrf, tokenize

CORPUS_DIR = Path(__file__).resolve().parent.parent / "data" / "normas"


# ---------- tokenize ----------


def test_tokenize_lowercases_and_removes_accents():
    assert tokenize("Alienação, ONERAÇÃO!") == ["alienacao", "oneracao"]


def test_tokenize_splits_article_numbers_with_letter():
    assert tokenize("art. 64-A") == ["art", "64", "a"]


def test_tokenize_drops_symbols_and_ordinal_signs():
    assert tokenize("§ 1º R$ 2.000,00") == ["1", "r", "2", "000", "00"]


def test_tokenize_empty_text_gives_empty_list():
    assert tokenize("") == []


# ---------- cosine ----------


def test_cosine_of_identical_vectors_is_one():
    assert cosine([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)


def test_cosine_of_orthogonal_vectors_is_zero():
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_of_opposite_vectors_is_minus_one():
    assert cosine([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_cosine_ignores_vector_length():
    assert cosine([1.0, 1.0], [10.0, 10.0]) == pytest.approx(1.0)


def test_cosine_with_zero_vector_is_zero():
    assert cosine([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_cosine_with_different_sizes_raises():
    with pytest.raises(ValueError, match="tamanho"):
        cosine([1.0, 2.0], [1.0])


# ---------- bm25 ----------

DOCS = [
    ["arrolamento", "bens", "imoveis"],
    ["credito", "tributario", "bens"],
    ["recurso", "administrativo"],
]


def test_bm25_scores_only_documents_that_contain_the_term():
    scores = bm25_scores(["arrolamento"], DOCS)
    assert scores[0] > 0
    assert scores[1] == 0
    assert scores[2] == 0


def test_bm25_rare_term_weighs_more_than_common_term():
    rare = bm25_scores(["arrolamento"], DOCS)[0]  # só no documento 0
    common = bm25_scores(["bens"], DOCS)[0]  # nos documentos 0 e 1
    assert rare > common


def test_bm25_prefers_the_shorter_document_when_term_count_is_equal():
    docs = [["x", "a"], ["x", "a", "b", "c", "d", "e"]]
    scores = bm25_scores(["x"], docs)
    assert scores[0] > scores[1]


def test_bm25_repeated_query_term_counts_once():
    assert bm25_scores(["bens", "bens"], DOCS) == bm25_scores(["bens"], DOCS)


def test_bm25_term_in_no_document_gives_all_zero():
    assert bm25_scores(["inexistente"], DOCS) == [0.0, 0.0, 0.0]


def test_bm25_without_documents_gives_empty_list():
    assert bm25_scores(["x"], []) == []


# ---------- rrf ----------


def test_rrf_single_list_uses_one_over_k_plus_position():
    assert rrf([[5, 7]], k=10) == {5: pytest.approx(1 / 11), 7: pytest.approx(1 / 12)}


def test_rrf_item_first_in_both_lists_adds_both_contributions():
    assert rrf([[0, 1], [0, 1]], k=60)[0] == pytest.approx(2 / 61)


def test_rrf_item_in_both_lists_beats_item_in_only_one():
    scores = rrf([[1, 2], [2, 3]], k=60)
    assert scores[2] > scores[1]
    assert scores[2] > scores[3]


def test_rrf_without_rankings_gives_empty_dict():
    assert rrf([]) == {}


# ---------- hybrid_search (com embed falso) ----------

A = Chunk("Norma X", "1", "", "Art. 1º Texto sem relação com a palavra procurada.")
C = Chunk("Norma X", "3", "", "Art. 3º Nada a ver com o assunto.")
B = Chunk("Norma X", "2", "", "Art. 2º O termo raro xilofone aparece somente aqui.")
CHUNKS = [A, C, B]
# Vetores de 2 dimensões: A aponta para a pergunta, C é neutro e B aponta para o lado oposto.
VECTORS = [[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]]


def make_embed(query_vector, calls=None):
    """Cria um embed falso que devolve sempre o mesmo vetor e guarda o que recebeu."""

    def embed(texts):
        if calls is not None:
            calls.append(list(texts))
        return [query_vector for _ in texts]

    return embed


def test_hybrid_lexical_match_rescues_chunk_the_vector_ranks_last():
    # Pelo vetor, B é o ÚLTIMO (cosseno -1). Mas só B contém "xilofone": o BM25 o traz para o topo.
    hits = hybrid_search("xilofone", CHUNKS, VECTORS, make_embed([1.0, 0.0]), k=3)
    assert hits[0].chunk is B


def test_hybrid_without_lexical_match_follows_the_vector():
    hits = hybrid_search("zzz", CHUNKS, VECTORS, make_embed([1.0, 0.0]), k=3)
    assert [h.chunk for h in hits] == [A, C, B]


def test_hybrid_tie_in_rrf_is_broken_by_the_higher_similarity():
    # P e Q se alternam: P é 1º no vetor e 2º nas palavras; Q é 2º no vetor e 1º nas palavras.
    # Os dois somam exatamente 1/61 + 1/62 (empate). Q vem antes na lista, então sem desempate ele ganharia.
    q = Chunk("Norma X", "1", "", "Art. 1º alfa beta gama.")
    p = Chunk("Norma X", "2", "", "Art. 2º alfa delta epsilon.")
    hits = hybrid_search("alfa beta", [q, p], [[0.0, 1.0], [1.0, 0.0]], make_embed([1.0, 0.0]), k=2)
    assert hits[0].score == hits[1].score
    assert [h.chunk for h in hits] == [p, q]


def test_hybrid_rrf_k_sets_the_scale_of_the_scores():
    # Só o ranking por vetor existe ("zzz" não aparece em nenhum artigo): o 1º lugar vale 1 / (rrf_k + 1).
    default = hybrid_search("zzz", CHUNKS, VECTORS, make_embed([1.0, 0.0]), k=1)
    small = hybrid_search("zzz", CHUNKS, VECTORS, make_embed([1.0, 0.0]), k=1, rrf_k=10)
    assert default[0].score == pytest.approx(1 / 61)
    assert small[0].score == pytest.approx(1 / 11)


@pytest.mark.parametrize("bad", [0, -5])
def test_hybrid_rejects_an_rrf_k_below_one(bad):
    with pytest.raises(ValueError, match="rrf_k"):
        hybrid_search("x", CHUNKS, VECTORS, make_embed([1.0, 0.0]), rrf_k=bad)


def test_hybrid_respects_k():
    hits = hybrid_search("xilofone", CHUNKS, VECTORS, make_embed([1.0, 0.0]), k=2)
    assert len(hits) == 2


def test_hybrid_hits_carry_similarity_bm25_and_score():
    hits = hybrid_search("xilofone", CHUNKS, VECTORS, make_embed([1.0, 0.0]), k=3)
    by_chunk = {h.chunk: h for h in hits}
    assert isinstance(hits[0], Hit)
    assert by_chunk[A].similarity == pytest.approx(1.0)
    assert by_chunk[B].similarity == pytest.approx(-1.0)
    assert by_chunk[B].bm25 > 0
    assert by_chunk[A].bm25 == 0
    assert hits[0].score >= hits[1].score >= hits[2].score


def test_hybrid_embeds_the_query_exactly_once():
    calls = []
    hybrid_search("xilofone", CHUNKS, VECTORS, make_embed([1.0, 0.0], calls))
    assert calls == [["xilofone"]]


def test_hybrid_with_vectors_of_a_different_count_raises():
    with pytest.raises(ValueError, match="vetores"):
        hybrid_search("x", CHUNKS, VECTORS[:2], make_embed([1.0, 0.0]))


def test_hybrid_without_chunks_gives_empty_list():
    assert hybrid_search("x", [], [], make_embed([1.0, 0.0])) == []


# ---------- BM25 sobre o corpus real ----------


def test_bm25_finds_the_article_that_introduced_the_selo_confia_rule():
    # O art. 10 ganhou os §§ 4º a 8º (Selo Confia/Sintonia) pela IN 2.338/2026.
    chunks = load_corpus(CORPUS_DIR)
    scores = bm25_scores(tokenize("Selo Confia Selo Sintonia"), [tokenize(c.search_text) for c in chunks])
    best = chunks[scores.index(max(scores))]
    assert best.reference == "IN RFB 2.091/2022, art. 10"
