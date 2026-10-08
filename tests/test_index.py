"""Testes do índice (RF03): construção em lotes, gravação atômica e leitura com checagens."""

import json
from datetime import datetime

import pytest

from rag_normas.ingest import Chunk
from rag_normas.index import Index, IndexFileError, build_index, load_index, save_index

CHUNKS = [
    Chunk("Norma X", str(n), "Capítulo I — Gerais" if n % 2 else "", f"Art. {n}º Texto número {n}, com ação.")
    for n in range(1, 6)
]
NOW = datetime(2026, 10, 8, 10, 30, 0)


def fake_embed_factory(batches=None):
    """embed falso: o vetor de cada texto é [tamanho do texto, 1.0]. Guarda o tamanho de cada lote."""

    def embed(texts):
        if batches is not None:
            batches.append(len(texts))
        return [[float(len(text)), 1.0] for text in texts]

    return embed


# ---------- build_index ----------

def test_build_index_gives_one_vector_per_chunk_in_order():
    index = build_index(CHUNKS, fake_embed_factory(), "bge-m3", now=NOW)
    assert index.chunks == CHUNKS
    assert index.vectors == [[float(len(c.search_text)), 1.0] for c in CHUNKS]
    assert index.embedding_model == "bge-m3"
    assert index.created_at == "2026-10-08T10:30:00"


def test_build_index_embeds_the_search_text_with_the_section():
    seen = []
    build_index(CHUNKS[:1], lambda texts: seen.extend(texts) or [[0.0]], "m", now=NOW)
    assert seen == [CHUNKS[0].search_text]
    assert seen[0].startswith("Capítulo I — Gerais")


def test_build_index_works_in_batches():
    batches = []
    build_index(CHUNKS, fake_embed_factory(batches), "bge-m3", now=NOW, batch_size=2)
    assert batches == [2, 2, 1]


def test_build_index_reports_progress():
    progress = []
    build_index(CHUNKS, fake_embed_factory(), "bge-m3", now=NOW, batch_size=2, on_progress=lambda d, t: progress.append((d, t)))
    assert progress == [(2, 5), (4, 5), (5, 5)]


def test_build_index_without_chunks_raises():
    with pytest.raises(ValueError, match="nenhum artigo"):
        build_index([], fake_embed_factory(), "bge-m3", now=NOW)


def test_build_index_detects_embed_returning_the_wrong_amount():
    with pytest.raises(ValueError, match="vetores"):
        build_index(CHUNKS, lambda texts: [[1.0]], "bge-m3", now=NOW)


# ---------- save_index / load_index ----------

@pytest.fixture
def index():
    return build_index(CHUNKS, fake_embed_factory(), "bge-m3", now=NOW)


def test_roundtrip_keeps_everything_including_accents(tmp_path, index):
    path = tmp_path / "data" / "index.json"  # a pasta "data" ainda não existe
    save_index(index, path)
    loaded = load_index(path)
    assert loaded == index
    assert "ação" in path.read_text(encoding="utf-8")  # sem escapes \uXXXX


def test_saved_file_has_the_documented_layout(tmp_path, index):
    path = tmp_path / "index.json"
    save_index(index, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data) == {"embedding_model", "created_at", "chunks"}
    assert set(data["chunks"][0]) == {"norm", "article", "section", "text", "vector"}


def test_save_leaves_no_temporary_file_behind(tmp_path, index):
    save_index(index, tmp_path / "index.json")
    assert [p.name for p in tmp_path.iterdir()] == ["index.json"]


def test_save_replaces_an_existing_index(tmp_path, index):
    path = tmp_path / "index.json"
    path.write_text("lixo antigo", encoding="utf-8")
    save_index(index, path)
    assert load_index(path) == index


def test_load_missing_file_tells_how_to_create_it(tmp_path):
    with pytest.raises(IndexFileError, match="python -m rag_normas index"):
        load_index(tmp_path / "nao-existe.json")


def test_load_broken_json_tells_to_reindex(tmp_path):
    path = tmp_path / "index.json"
    path.write_text("{ isto não é json", encoding="utf-8")
    with pytest.raises(IndexFileError, match="python -m rag_normas index"):
        load_index(path)


def test_load_json_with_missing_fields_tells_to_reindex(tmp_path):
    path = tmp_path / "index.json"
    path.write_text(json.dumps({"embedding_model": "bge-m3"}), encoding="utf-8")
    with pytest.raises(IndexFileError, match="python -m rag_normas index"):
        load_index(path)


def test_load_with_a_different_embedding_model_tells_to_reindex(tmp_path, index):
    path = tmp_path / "index.json"
    save_index(index, path)
    with pytest.raises(IndexFileError, match="outro-modelo") as info:
        load_index(path, expected_model="outro-modelo")
    assert "bge-m3" in str(info.value)
    assert "reindex" in str(info.value).lower() or "index" in str(info.value)


def test_load_with_the_same_embedding_model_is_fine(tmp_path, index):
    path = tmp_path / "index.json"
    save_index(index, path)
    assert load_index(path, expected_model="bge-m3") == index


def test_index_is_a_plain_value_object(index):
    assert isinstance(index, Index)
