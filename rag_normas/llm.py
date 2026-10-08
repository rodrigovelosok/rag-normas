"""Ponte com o Ollama. É o ÚNICO módulo que conhece a biblioteca `ollama` (docs/arquitetura.md, D4).

Os outros módulos recebem as funções `embed` e `chat` prontas; nos testes, recebem funções falsas.
"""

from collections.abc import Callable

import httpx  # já vem junto com a biblioteca ollama
import ollama

from rag_normas.config import Settings


class LLMError(Exception):
    """Falha ao falar com o Ollama. A mensagem diz o que fazer."""


def make_llm(
    settings: Settings,
    client: ollama.Client | None = None,
) -> tuple[Callable[[list[str]], list[list[float]]], Callable[[list[dict[str, str]]], str]]:
    """Cria as duas funções que o resto do sistema usa.

    Args:
        settings: Configuração (modelos, host, contexto, tempo limite).
        client: Cliente do Ollama. Os testes passam um falso; em produção, fica `None` e é criado aqui.

    Returns:
        Uma tupla `(embed, chat)`:
        - `embed(texts)` devolve um vetor por texto;
        - `chat(messages)` devolve o texto da resposta. A temperatura é 0, para a mesma pergunta dar a mesma
          resposta (os testes de avaliação ficam comparáveis), e o `num_ctx` vem da configuração.
    """
    client = client or ollama.Client(host=settings.ollama_host, timeout=settings.timeout)

    def embed(texts: list[str]) -> list[list[float]]:
        response = _call(lambda: client.embed(model=settings.embed_model, input=texts), settings, settings.embed_model)
        vectors = response["embeddings"]
        if len(vectors) != len(texts):
            raise LLMError(f"O Ollama devolveu {len(vectors)} vetores para {len(texts)} textos.")
        return vectors

    def chat(messages: list[dict[str, str]]) -> str:
        options = {"temperature": 0, "num_ctx": settings.num_ctx}
        response = _call(
            lambda: client.chat(model=settings.chat_model, messages=messages, options=options),
            settings,
            settings.chat_model,
        )
        return response["message"]["content"]

    return embed, chat


def _call(action: Callable[[], dict], settings: Settings, model: str) -> dict:
    """Executa uma chamada ao Ollama, trocando os erros técnicos por mensagens do tipo 'o que fazer'."""
    try:
        return action()
    except ConnectionError:
        raise LLMError(
            f"Não consegui falar com o Ollama em {settings.ollama_host}. "
            "Ele está rodando? Abra o aplicativo Ollama ou execute: ollama serve"
        ) from None
    except httpx.TimeoutException:
        raise LLMError(
            f"O Ollama não respondeu em {settings.timeout:g} s. "
            "Na primeira chamada o modelo precisa ser carregado; tente de novo ou aumente RAG_TIMEOUT."
        ) from None
    except ollama.ResponseError as error:
        if error.status_code == 404:
            raise LLMError(
                f"O modelo '{model}' não está instalado no Ollama. Instale com: ollama pull {model}"
            ) from None
        raise LLMError(f"O Ollama respondeu com erro ({error.status_code}): {error.error}") from None
