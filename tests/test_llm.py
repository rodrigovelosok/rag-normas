"""Testes da ponte com o Ollama, usando um cliente falso (RNF03: nada aqui precisa do Ollama)."""

import httpx
import ollama
import pytest

from rag_normas.config import Settings
from rag_normas.llm import LLMError, make_llm

SETTINGS = Settings.from_env({})


class FakeClient:
    """Imita o ollama.Client: guarda o que recebeu e devolve respostas prontas (ou lança erro)."""

    def __init__(self, embeddings=None, answer="resposta", error=None):
        self.embeddings = embeddings if embeddings is not None else [[0.1, 0.2]]
        self.answer = answer
        self.error = error
        self.embed_calls = []
        self.chat_calls = []

    def embed(self, model, input):
        self.embed_calls.append({"model": model, "input": input})
        if self.error:
            raise self.error
        return {"embeddings": self.embeddings}

    def chat(self, model, messages, options):
        self.chat_calls.append({"model": model, "messages": messages, "options": options})
        if self.error:
            raise self.error
        return {"message": {"content": self.answer}}


def test_embed_sends_the_configured_model_and_returns_the_vectors():
    client = FakeClient(embeddings=[[1.0, 2.0], [3.0, 4.0]])
    embed, _ = make_llm(SETTINGS, client)
    assert embed(["a", "b"]) == [[1.0, 2.0], [3.0, 4.0]]
    assert client.embed_calls == [{"model": "bge-m3", "input": ["a", "b"]}]


def test_chat_sends_model_messages_temperature_zero_and_num_ctx():
    client = FakeClient(answer="olá")
    _, chat = make_llm(SETTINGS, client)
    messages = [{"role": "user", "content": "oi"}]
    assert chat(messages) == "olá"
    call = client.chat_calls[0]
    assert call["model"] == "qwen2.5:3b"
    assert call["messages"] == messages
    assert call["options"] == {"temperature": 0, "num_ctx": 8192}


def test_chat_uses_the_model_from_the_settings():
    client = FakeClient()
    _, chat = make_llm(SETTINGS.with_overrides(chat_model="qwen2.5:7b"), client)
    chat([{"role": "user", "content": "oi"}])
    assert client.chat_calls[0]["model"] == "qwen2.5:7b"


def test_connection_error_tells_how_to_start_ollama():
    embed, chat = make_llm(SETTINGS, FakeClient(error=ConnectionError("recusada")))
    for call in (lambda: embed(["x"]), lambda: chat([{"role": "user", "content": "x"}])):
        with pytest.raises(LLMError, match="ollama serve") as info:
            call()
        assert "http://localhost:11434" in str(info.value)


def test_missing_model_tells_how_to_pull_it():
    error = ollama.ResponseError("model not found", 404)
    _, chat = make_llm(SETTINGS, FakeClient(error=error))
    with pytest.raises(LLMError, match="ollama pull qwen2.5:3b"):
        chat([{"role": "user", "content": "x"}])


def test_missing_embedding_model_tells_how_to_pull_it():
    embed, _ = make_llm(SETTINGS, FakeClient(error=ollama.ResponseError("model not found", 404)))
    with pytest.raises(LLMError, match="ollama pull bge-m3"):
        embed(["x"])


def test_other_response_errors_keep_the_original_message():
    _, chat = make_llm(SETTINGS, FakeClient(error=ollama.ResponseError("falta de memória", 500)))
    with pytest.raises(LLMError, match="falta de memória"):
        chat([{"role": "user", "content": "x"}])


def test_embed_with_a_different_number_of_vectors_raises():
    embed, _ = make_llm(SETTINGS, FakeClient(embeddings=[[1.0]]))
    with pytest.raises(LLMError, match="2 textos"):
        embed(["a", "b"])


def test_timeout_mentions_the_setting_to_raise():
    _, chat = make_llm(SETTINGS, FakeClient(error=httpx.ReadTimeout("demorou")))
    with pytest.raises(LLMError, match="RAG_TIMEOUT"):
        chat([{"role": "user", "content": "x"}])
