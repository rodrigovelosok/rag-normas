"""Busca híbrida: BM25 (palavras) + similaridade vetorial (significado), fundidas por RRF (RF04).

Este módulo não importa o Ollama: quem chama entrega a função `embed` (ver docs/arquitetura.md, D4 e D5).
Assim os testes usam um `embed` falso, sem Ollama instalado.
"""

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from rag_normas.ingest import Chunk

# Recebe uma lista de textos e devolve um vetor (lista de números) para cada um.
EmbedFn = Callable[[list[str]], list[list[float]]]

WORD = re.compile(r"[a-z0-9]+")  # só letras sem acento e dígitos


@dataclass(frozen=True)
class Hit:
    """Um artigo encontrado, com as três medidas que explicam por que ele apareceu.

    Attributes:
        chunk: O artigo.
        similarity: Cosseno entre a pergunta e o artigo (de -1 a 1; quanto maior, mais parecido).
        bm25: Pontuação por palavras (0 se nenhuma palavra da pergunta aparece no artigo).
        score: Pontuação final do RRF, que decide a ordem.
    """

    chunk: Chunk
    similarity: float
    bm25: float
    score: float


def tokenize(text: str) -> list[str]:
    """Quebra o texto em palavras minúsculas e sem acento: "Alienação, 64-A" -> ["alienacao", "64", "a"]."""
    decomposed = unicodedata.normalize("NFD", text.lower())  # "ç" vira "c" + cedilha solta
    without_accents = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")  # Mn = marca de acento
    return WORD.findall(without_accents)


def cosine(a: list[float], b: list[float]) -> float:
    """Similaridade de cosseno: 1 = mesma direção, 0 = sem relação, -1 = direções opostas.

    Raises:
        ValueError: Se os vetores tiverem tamanhos diferentes.
    """
    if len(a) != len(b):
        raise ValueError(f"Vetores de tamanho diferente: {len(a)} e {len(b)}")
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0  # vetor nulo não tem direção: evita dividir por zero
    return sum(x * y for x, y in zip(a, b, strict=True)) / (norm_a * norm_b)


def bm25_scores(
    query_tokens: list[str],
    documents: list[list[str]],
    k1: float = 1.5,
    b: float = 0.75,
) -> list[float]:
    """Pontua cada documento pela raridade das palavras da pergunta que ele contém (BM25).

    Args:
        query_tokens: Palavras da pergunta (saída de `tokenize`).
        documents: Um item por documento, cada um já separado em palavras.
        k1: Quanto repetir a mesma palavra continua valendo. Padrão da literatura.
        b: Quanto o tamanho do documento reduz a pontuação (0 = nada, 1 = total). Padrão da literatura.

    Returns:
        Uma pontuação por documento, na mesma ordem. Zero se nenhuma palavra da pergunta aparece.
    """
    n_docs = len(documents)
    if n_docs == 0:
        return []
    avg_length = sum(len(doc) for doc in documents) / n_docs or 1.0

    # Em quantos documentos cada palavra aparece (set: conta o documento uma vez só)
    doc_freq: Counter[str] = Counter()
    for doc in documents:
        doc_freq.update(set(doc))

    scores = []
    for doc in documents:
        counts = Counter(doc)
        score = 0.0
        for term in set(query_tokens):  # set: palavra repetida na pergunta não vale em dobro
            tf = counts.get(term, 0)
            if tf == 0:
                continue
            # O "1 +" mantém o IDF positivo até para palavra que aparece em quase todos os documentos
            idf = math.log(1 + (n_docs - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            length_factor = 1 - b + b * len(doc) / avg_length  # documento longo "dilui" a palavra
            score += idf * tf * (k1 + 1) / (tf + k1 * length_factor)
        scores.append(score)
    return scores


def rrf(rankings: list[list[int]], k: int = 60) -> dict[int, float]:
    """Reciprocal Rank Fusion: junta várias listas ordenadas olhando só a POSIÇÃO de cada item.

    Cada lista dá a cada item `1 / (k + posição)`; quem aparece bem em mais listas soma mais. Usar a
    posição (e não a nota) evita misturar escalas diferentes, como cosseno (-1 a 1) e BM25 (0 a 10+).
    O `k = 60` é o valor padrão da literatura; vamos calibrá-lo na avaliação (Fase 4).

    Args:
        rankings: Cada lista traz os índices dos itens, do melhor para o pior.
        k: Suaviza a diferença entre as primeiras posições.

    Returns:
        Pontuação de cada item que apareceu em alguma lista.
    """
    scores: dict[int, float] = {}
    for ranking in rankings:
        for position, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1 / (k + position)
    return scores


def hybrid_search(
    query: str,
    chunks: list[Chunk],
    vectors: list[list[float]],
    embed: EmbedFn,
    k: int = 4,
    rrf_k: int = 60,
) -> list[Hit]:
    """Acha os `k` artigos mais relevantes para a pergunta, combinando vetor e palavras.

    Args:
        query: A pergunta do usuário.
        chunks: Os artigos do índice.
        vectors: Um vetor por artigo, na mesma ordem de `chunks`.
        embed: Função que transforma textos em vetores (o Ollama, ou um falso nos testes).
        k: Quantos artigos devolver.
        rrf_k: Constante do RRF (veja `rrf`). Menor dá mais peso às primeiras posições de cada lista.

    Returns:
        Até `k` Hit, do mais relevante para o menos.

    Raises:
        ValueError: Se `chunks` e `vectors` tiverem quantidades diferentes ou se `rrf_k` for menor que 1.
    """
    if rrf_k < 1:
        raise ValueError(f"rrf_k deve ser pelo menos 1; recebi {rrf_k}")
    if len(chunks) != len(vectors):
        raise ValueError(f"{len(chunks)} artigos para {len(vectors)} vetores: reindexe o corpus")
    if not chunks:
        return []

    query_vector = embed([query])[0]  # a pergunta é "embutida" uma única vez
    similarities = [cosine(query_vector, vector) for vector in vectors]
    lexical = bm25_scores(tokenize(query), [tokenize(chunk.search_text) for chunk in chunks])

    positions = range(len(chunks))
    by_vector = sorted(positions, key=lambda i: similarities[i], reverse=True)
    # No ranking por palavras só entra quem tem alguma palavra em comum: nota zero não é "relevante"
    by_words = [i for i in sorted(positions, key=lambda i: lexical[i], reverse=True) if lexical[i] > 0]

    fused = rrf([by_vector, by_words], k=rrf_k)
    best = sorted(positions, key=lambda i: (fused[i], similarities[i]), reverse=True)[:k]
    return [Hit(chunks[i], similarities[i], lexical[i], fused[i]) for i in best]
