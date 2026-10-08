"""Índice: gera os vetores dos artigos e grava/lê o arquivo JSON (RF03)."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from rag_normas.ingest import Chunk

REINDEX_HINT = "python -m rag_normas index"


class IndexFileError(Exception):
    """Problema ao ler o arquivo de índice. A mensagem diz como resolver."""


@dataclass(frozen=True)
class Index:
    """Os artigos do corpus e o vetor de cada um, na mesma ordem.

    Attributes:
        embedding_model: Modelo que gerou os vetores. Vetores de modelos diferentes não podem ser comparados.
        created_at: Data e hora da criação, em formato ISO ("2026-10-08T10:30:00").
        chunks: Os artigos.
        vectors: Um vetor por artigo (`vectors[i]` pertence a `chunks[i]`).
    """

    embedding_model: str
    created_at: str
    chunks: list[Chunk]
    vectors: list[list[float]]


def build_index(
    chunks: list[Chunk],
    embed: Callable[[list[str]], list[list[float]]],
    embedding_model: str,
    now: datetime | None = None,
    batch_size: int = 8,
    on_progress: Callable[[int, int], None] | None = None,
) -> Index:
    """Gera o vetor de cada artigo, em lotes, e devolve o índice pronto para gravar.

    Em lotes porque o cálculo é lento nesta máquina (~60 s para os 31 artigos): assim o usuário
    acompanha o andamento em vez de olhar uma tela parada.

    Args:
        chunks: Artigos lidos por `ingest.load_corpus`.
        embed: Função que transforma textos em vetores.
        embedding_model: Nome do modelo de `embed`, gravado no índice.
        now: Data/hora de criação (os testes fixam um valor). Padrão: agora.
        batch_size: Quantos artigos por chamada.
        on_progress: Chamada como `on_progress(feitos, total)` depois de cada lote.

    Raises:
        ValueError: Se não houver artigos ou se `embed` devolver quantidade errada de vetores.
    """
    if not chunks:
        raise ValueError("Não há nenhum artigo para indexar: confira a pasta do corpus (data/normas).")

    texts = [chunk.search_text for chunk in chunks]  # mesmo texto que a busca por palavras usa
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        batch_vectors = embed(batch)
        if len(batch_vectors) != len(batch):
            raise ValueError(f"embed devolveu {len(batch_vectors)} vetores para {len(batch)} textos")
        vectors.extend(batch_vectors)
        if on_progress:
            on_progress(len(vectors), len(texts))

    created_at = (now or datetime.now()).isoformat(timespec="seconds")
    return Index(embedding_model, created_at, list(chunks), vectors)


def save_index(index: Index, path: Path) -> None:
    """Grava o índice em JSON. Escreve num arquivo temporário e só então troca o definitivo:
    se algo falhar no meio, o índice antigo continua inteiro."""
    path = Path(path)
    data = {
        "embedding_model": index.embedding_model,
        "created_at": index.created_at,
        "chunks": [
            {"norm": c.norm, "article": c.article, "section": c.section, "text": c.text, "vector": v}
            for c, v in zip(index.chunks, index.vectors, strict=True)  # strict: quantidades diferentes viram erro
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")  # ensure_ascii: mantém "ação"
    temporary.replace(path)


def load_index(path: Path, expected_model: str | None = None) -> Index:
    """Lê o índice gravado por `save_index`.

    Args:
        path: Arquivo do índice.
        expected_model: Se informado, o índice precisa ter sido criado com esse modelo de embedding.

    Raises:
        IndexFileError: Arquivo ausente, corrompido ou criado com outro modelo de embedding.
    """
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise IndexFileError(f"Índice não encontrado em {path}. Crie com: {REINDEX_HINT}") from None

    try:
        data = json.loads(raw)
        chunks = [Chunk(c["norm"], c["article"], c["section"], c["text"]) for c in data["chunks"]]
        vectors = [c["vector"] for c in data["chunks"]]
        model, created_at = data["embedding_model"], data["created_at"]
    except (json.JSONDecodeError, KeyError, TypeError):
        raise IndexFileError(
            f"O índice em {path} está corrompido ou em formato antigo. Recrie com: {REINDEX_HINT}"
        ) from None

    if expected_model and model != expected_model:
        raise IndexFileError(
            f"O índice foi criado com o modelo '{model}', mas a configuração usa '{expected_model}'. "
            f"Recrie o índice: {REINDEX_HINT}"
        )
    return Index(model, created_at, chunks, vectors)
