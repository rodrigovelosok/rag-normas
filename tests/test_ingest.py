"""Testes da leitura das normas (CA01 e CA02).

Há dois grupos:
- testes com textos pequenos inventados, que provam as regras de divisão;
- testes com o corpus real em data/normas/, que provam o gabarito (31 artigos).
"""

from pathlib import Path

import pytest

from rag_normas.ingest import Chunk, load_corpus, parse_norm

CORPUS_DIR = Path(__file__).resolve().parent.parent / "data" / "normas"

SAMPLE = """Norma de Exemplo nº 1
Ementa da norma de exemplo.

O MINISTRO, resolve:

CAPÍTULO I
DISPOSIÇÕES GERAIS

Seção I
Das Definições

Art. 1º Esta norma trata de exemplos.
§ 1º O exemplo é simples.
I - primeiro inciso;
II - segundo inciso, conforme o art. 12., com ressalvas. [Redação dada pela IN RFB nº 2338/2026]

Art. 2º Segundo artigo.
Parágrafo único. Vale também o Art. 7º do regulamento citado.

CAPÍTULO II
DISPOSIÇÕES FINAIS

Art. 10. Décimo artigo.
Art. 11-A. Artigo com letra.
"""


# ---------- textos pequenos ----------

def test_splits_one_chunk_per_article():
    chunks = parse_norm(SAMPLE, "Norma X")
    assert [c.article for c in chunks] == ["1", "2", "10", "11-A"]


def test_ignores_preamble_before_first_article():
    chunks = parse_norm(SAMPLE, "Norma X")
    assert all("MINISTRO" not in c.text for c in chunks)
    assert all("Ementa" not in c.text for c in chunks)


def test_paragraphs_and_items_stay_with_their_article():
    first = parse_norm(SAMPLE, "Norma X")[0]
    assert "§ 1º O exemplo é simples." in first.text
    assert "II - segundo inciso" in first.text
    assert "Segundo artigo" not in first.text


def test_reference_inside_a_line_does_not_start_an_article():
    # "Art. 7º" (com maiúscula) aparece no MEIO de uma linha do art. 2º: não pode criar um chunk "7"
    chunks = parse_norm(SAMPLE, "Norma X")
    assert [c.article for c in chunks] == ["1", "2", "10", "11-A"]
    assert "Art. 7º do regulamento citado" in chunks[1].text


def test_amendment_note_stays_in_the_text():
    first = parse_norm(SAMPLE, "Norma X")[0]
    assert "[Redação dada pela IN RFB nº 2338/2026]" in first.text


def test_headings_are_not_part_of_any_text():
    for chunk in parse_norm(SAMPLE, "Norma X"):
        assert "CAPÍTULO" not in chunk.text
        assert "Seção" not in chunk.text
        assert "DISPOSIÇÕES" not in chunk.text


def test_section_tracks_chapter_and_section():
    chunks = parse_norm(SAMPLE, "Norma X")
    assert chunks[0].section == "Capítulo I — Disposições gerais / Seção I — Das Definições"
    assert chunks[1].section == chunks[0].section
    # novo capítulo zera a seção anterior
    assert chunks[2].section == "Capítulo II — Disposições finais"


def test_text_without_any_article_gives_empty_list():
    assert parse_norm("Só um título\nSem artigos.", "Norma X") == []


@pytest.mark.parametrize(
    ("article", "expected"),
    [
        ("5", "Norma X, art. 5º"),
        ("9", "Norma X, art. 9º"),
        ("10", "Norma X, art. 10"),
        ("64-A", "Norma X, art. 64-A"),
    ],
)
def test_reference_format(article, expected):
    assert Chunk("Norma X", article, "", "texto").reference == expected


# ---------- corpus real ----------

@pytest.fixture(scope="module")
def corpus():
    return load_corpus(CORPUS_DIR)


def of(corpus, norm):
    return [c for c in corpus if c.norm == norm]


def test_corpus_has_31_chunks(corpus):
    assert len(corpus) == 31


def test_corpus_chunks_per_norm(corpus):
    assert len(of(corpus, "IN RFB 2.091/2022")) == 27
    assert len(of(corpus, "Lei 9.532/1997")) == 2
    assert len(of(corpus, "Decreto 7.573/2011")) == 2


def test_in_articles_are_numbered_1_to_27(corpus):
    assert [c.article for c in of(corpus, "IN RFB 2.091/2022")] == [str(n) for n in range(1, 28)]


def test_law_has_articles_64_and_64a(corpus):
    assert [c.article for c in of(corpus, "Lei 9.532/1997")] == ["64", "64-A"]


def test_in_article_2_keeps_its_items_and_paragraphs(corpus):
    art2 = next(c for c in of(corpus, "IN RFB 2.091/2022") if c.article == "2")
    assert "II - R$ 2.000.000,00" in art2.text
    assert "§ 6º Para fins de cálculo" in art2.text
    assert "Art. 3º" not in art2.text


def test_law_article_64_goes_up_to_paragraph_13(corpus):
    art64 = next(c for c in corpus if c.reference == "Lei 9.532/1997, art. 64")
    assert "§ 13." in art64.text
    assert "Art. 64-A" not in art64.text


def test_in_article_15_is_in_the_substitution_section(corpus):
    art15 = next(c for c in of(corpus, "IN RFB 2.091/2022") if c.article == "15")
    assert "Substituição" in art15.section


def test_no_chunk_is_empty_and_none_contains_headings(corpus):
    for chunk in corpus:
        assert chunk.text.startswith("Art. ")
        assert len(chunk.text) > 50
        assert "CAPÍTULO" not in chunk.text


def test_unknown_file_uses_its_name_as_the_norm_label(tmp_path):
    (tmp_path / "minha-norma.txt").write_text("Título\nArt. 1º Texto.\n", encoding="utf-8")
    chunks = load_corpus(tmp_path)
    assert [c.norm for c in chunks] == ["minha-norma"]
