"""Testes da configuração (RF08)."""

from pathlib import Path

import pytest

from rag_normas.config import ConfigError, Settings


def test_defaults():
    s = Settings.from_env({})
    assert s.ollama_host == "http://localhost:11434"
    assert s.chat_model == "qwen2.5:3b"
    assert s.embed_model == "bge-m3"
    assert s.top_k == 4
    assert s.rrf_k == 5  # calibrado na Fase 4 (eval/relatorios/busca*.md)
    assert s.min_similarity == pytest.approx(0.56)  # meio da faixa 0,54 a 0,58, sem erros nas 21 perguntas
    assert s.num_ctx == 8192
    assert s.index_path == Path("data/index.json")
    assert s.corpus_dir == Path("data/normas")


def test_environment_overrides_the_defaults():
    s = Settings.from_env(
        {
            "RAG_OLLAMA_HOST": "http://outra:11434",
            "RAG_CHAT_MODEL": "qwen2.5:7b",
            "RAG_EMBED_MODEL": "outro-embed",
            "RAG_TOP_K": "6",
            "RAG_RRF_K": "20",
            "RAG_MIN_SIMILARITY": "0.6",
            "RAG_NUM_CTX": "4096",
            "RAG_TIMEOUT": "90",
            "RAG_INDEX_PATH": "meu/indice.json",
            "RAG_CORPUS_DIR": "minhas/normas",
        }
    )
    assert s.ollama_host == "http://outra:11434"
    assert s.chat_model == "qwen2.5:7b"
    assert s.embed_model == "outro-embed"
    assert s.top_k == 6
    assert s.rrf_k == 20
    assert s.min_similarity == pytest.approx(0.6)
    assert s.num_ctx == 4096
    assert s.timeout == pytest.approx(90.0)
    assert s.index_path == Path("meu/indice.json")
    assert s.corpus_dir == Path("minhas/normas")


def test_blank_variable_falls_back_to_the_default():
    assert Settings.from_env({"RAG_TOP_K": "  "}).top_k == 4


def test_with_overrides_returns_a_new_object():
    base = Settings.from_env({})
    other = base.with_overrides(chat_model="qwen2.5:7b", top_k=None)
    assert other.chat_model == "qwen2.5:7b"
    assert other.top_k == base.top_k  # None não sobrescreve
    assert base.chat_model == "qwen2.5:3b"


@pytest.mark.parametrize(
    ("variable", "value", "expected_in_message"),
    [
        ("RAG_TOP_K", "muitos", "RAG_TOP_K"),
        ("RAG_TOP_K", "0", "RAG_TOP_K"),
        ("RAG_RRF_K", "pouco", "RAG_RRF_K"),
        ("RAG_RRF_K", "0", "RAG_RRF_K"),
        ("RAG_MIN_SIMILARITY", "alto", "RAG_MIN_SIMILARITY"),
        ("RAG_MIN_SIMILARITY", "1.5", "RAG_MIN_SIMILARITY"),
        ("RAG_NUM_CTX", "-1", "RAG_NUM_CTX"),
        ("RAG_TIMEOUT", "0", "RAG_TIMEOUT"),
    ],
)
def test_invalid_values_raise_config_error_naming_the_variable(variable, value, expected_in_message):
    with pytest.raises(ConfigError, match=expected_in_message):
        Settings.from_env({variable: value})


def test_with_overrides_validates_too():
    with pytest.raises(ConfigError, match="top_k"):
        Settings.from_env({}).with_overrides(top_k=0)
    with pytest.raises(ConfigError, match="rrf_k"):
        Settings.from_env({}).with_overrides(rrf_k=0)
