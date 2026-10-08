"""Gabarito da avaliação: lê e valida as perguntas e confere quais itens uma resposta traz.

É a base do avaliador: não importa nenhum outro módulo de `eval/`.
"""

import json
import re
import unicodedata
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from pathlib import Path

GROUPS = ("fact", "list", "combined", "hard", "out_of_corpus")
KINDS = ("answer", "refuse")


class QuestionsError(ValueError):
    """Problema no arquivo de perguntas. A mensagem diz qual pergunta e o que corrigir."""


@dataclass(frozen=True)
class Item:
    """Um ponto que a resposta deve trazer. Basta casar UMA das expressões de `any_of`."""

    label: str
    any_of: tuple[str, ...]


@dataclass(frozen=True)
class Question:
    """Uma pergunta com o gabarito.

    Attributes:
        id: Identificador ("Q01").
        group: Um de `GROUPS`.
        text: A pergunta.
        kind: "answer" (o corpus responde) ou "refuse" (deve ser recusada).
        articles: Referências dos artigos que deveriam ser recuperados e citados.
        items: Pontos que a resposta deve conter (expressões regulares sem acento, em minúsculas).
    """

    id: str
    group: str
    text: str
    kind: str
    articles: tuple[str, ...]
    items: tuple[Item, ...]


def load_questions(path: Path, valid_articles: Collection[str] | None = None) -> list[Question]:
    """Lê e valida o arquivo de perguntas.

    Args:
        path: Arquivo JSON.
        valid_articles: Se informado, todo artigo esperado precisa estar aqui (referências do corpus/índice).

    Raises:
        QuestionsError: Arquivo ausente, JSON inválido ou pergunta mal formada (a mensagem cita o id).
    """
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise QuestionsError(f"arquivo de perguntas não encontrado: {path}") from None
    except json.JSONDecodeError as error:
        raise QuestionsError(f"o arquivo de perguntas não é um JSON válido ({error})") from None
    if not isinstance(raw, list):
        raise QuestionsError("o arquivo de perguntas deve conter uma lista de perguntas")

    questions: list[Question] = []
    seen: set[str] = set()
    for position, entry in enumerate(raw, 1):
        name = entry.get("id", f"#{position}") if isinstance(entry, dict) else f"#{position}"
        question = _parse_question(name, entry)
        if question.id in seen:
            raise QuestionsError(f"{question.id}: id duplicado")
        seen.add(question.id)
        if valid_articles is not None:
            for article in question.articles:
                if article not in valid_articles:
                    raise QuestionsError(f"{question.id}: artigo esperado inexistente no corpus: {article!r}")
        questions.append(question)
    return questions


def _parse_question(name: str, entry: object) -> Question:
    if not isinstance(entry, dict):
        raise QuestionsError(f"{name}: cada pergunta deve ser um objeto JSON")
    for key in ("id", "group", "kind", "question", "articles", "items"):
        if key not in entry:
            raise QuestionsError(f"{name}: falta a chave '{key}'")
    if entry["kind"] not in KINDS:
        raise QuestionsError(f"{name}: kind inválido ({entry['kind']!r}); use 'answer' ou 'refuse'")
    if entry["group"] not in GROUPS:
        raise QuestionsError(f"{name}: group inválido ({entry['group']!r}); use um de {', '.join(GROUPS)}")
    if entry["kind"] == "answer" and not entry["articles"]:
        raise QuestionsError(f"{name}: pergunta 'answer' precisa de 'articles' (artigos esperados)")
    if entry["kind"] == "answer" and not entry["items"]:
        raise QuestionsError(f"{name}: pergunta 'answer' precisa de 'items' (o que a resposta deve conter)")
    if entry["kind"] == "refuse" and (entry["articles"] or entry["items"]):
        raise QuestionsError(f"{name}: pergunta 'refuse' não pode ter 'articles' nem 'items'")

    items: list[Item] = []
    for raw_item in entry["items"]:
        label, patterns = raw_item["label"], raw_item["any_of"]
        if not patterns:
            raise QuestionsError(f"{name}: o item {label!r} precisa de 'any_of' com ao menos um padrão")
        for pattern in patterns:
            try:
                re.compile(pattern)
            except re.error as error:
                raise QuestionsError(f"{name}: regex inválida {pattern!r} no item {label!r}: {error}") from None
        items.append(Item(label, tuple(patterns)))
    return Question(
        entry["id"], entry["group"], entry["question"], entry["kind"], tuple(entry["articles"]), tuple(items)
    )


def select_questions(questions: Sequence[Question], ids: str) -> list[Question]:
    """Filtra as perguntas pelos ids separados por vírgula ("Q01,Q05"), mantendo a ordem do gabarito.

    Raises:
        QuestionsError: Se algum id não existir no gabarito.
    """
    wanted = [name.strip() for name in ids.split(",") if name.strip()]
    unknown = [name for name in wanted if name not in {q.id for q in questions}]
    if unknown:
        raise QuestionsError(f"id desconhecido em --only: {', '.join(unknown)}")
    return [q for q in questions if q.id in wanted]


def fold(text: str) -> str:
    """Minúsculas e sem acentos, para comparar "Extinção" com "extincao"."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def strip_citations(text: str) -> str:
    """Tira os `[Fonte: ...]`. Sem isso, "Decreto" dentro da citação contaria como se o modelo explicasse o decreto."""
    return re.sub(r"\[Fonte:[^\]]*\]", " ", text)


def match_items(text: str, items: Sequence[Item]) -> tuple[list[str], list[str]]:
    """Separa os itens em presentes e ausentes no texto da resposta (ignorando acentos, maiúsculas e citações)."""
    folded = fold(strip_citations(text))
    found, missing = [], []
    for item in items:
        present = any(re.search(pattern, folded, re.DOTALL) for pattern in item.any_of)
        (found if present else missing).append(item.label)
    return found, missing
