"""Leitura das normas: divide cada texto em fragmentos de um artigo (RF01, RF02)."""

import re
from dataclasses import dataclass
from pathlib import Path

# Nome curto de cada arquivo do corpus. Arquivo que não estiver aqui usa o próprio
# nome (sem a extensão) como rótulo, então dá para adicionar normas sem mexer no código.
NORM_LABELS = {
    "in-rfb-2091-2022": "IN RFB 2.091/2022",
    "lei-9532-1997-arts-64-64a": "Lei 9.532/1997",
    "decreto-7573-2011": "Decreto 7.573/2011",
}

# Uma expressão regular por tipo de linha. O "^" exige que o padrão esteja no INÍCIO da
# linha: é isso que impede "...prevista no art. 12., com..." (no meio da frase) de
# ser tomado como começo de artigo.
ARTICLE_LINE = re.compile(r"^Art\. (\d+(?:-[A-Z])?)[º.]")  # "Art. 1º", "Art. 10.", "Art. 64-A."
HEADING_LINE = re.compile(r"^(CAPÍTULO|Seção) ([IVXLC]+)$")  # "CAPÍTULO II", "Seção VII"


@dataclass(frozen=True)
class Chunk:
    """Um artigo de uma norma, com os parágrafos e incisos que pertencem a ele.

    Attributes:
        norm: Nome curto da norma, por exemplo "IN RFB 2.091/2022".
        article: Número do artigo como texto, por exemplo "5" ou "64-A".
        section: Capítulo e seção em que o artigo está (vazio se a norma não tiver).
        text: Texto completo do artigo, começando em "Art. N".
    """

    norm: str
    article: str
    section: str
    text: str

    @property
    def reference(self) -> str:
        """Referência no estilo jurídico: "IN RFB 2.091/2022, art. 5º" (art. 10 em diante, sem "º")."""
        ordinal = "º" if self.article.isdigit() and int(self.article) <= 9 else ""
        return f"{self.norm}, art. {self.article}{ordinal}"

    @property
    def search_text(self) -> str:
        """Texto usado para indexar e buscar: a seção (contexto) seguida do artigo.

        Fica aqui, e não em cada módulo, para o índice e a busca usarem exatamente o mesmo texto.
        """
        return f"{self.section}\n{self.text}" if self.section else self.text


def parse_norm(text: str, norm: str) -> list[Chunk]:
    """Divide o texto de uma norma em um Chunk por artigo.

    O que vem antes do primeiro artigo (título, ementa, preâmbulo) é ignorado. Os
    cabeçalhos de CAPÍTULO e Seção não entram no texto dos artigos: viram o campo `section`.

    Args:
        text: Conteúdo completo do arquivo da norma.
        norm: Nome curto da norma, copiado para cada Chunk.

    Returns:
        Lista de Chunk, na ordem em que os artigos aparecem. Vazia se não houver artigo.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    chunks: list[Chunk] = []
    chapter = ""
    section = ""
    article: str | None = None  # artigo que está sendo lido agora
    article_section = ""
    article_lines: list[str] = []
    skip_next = False  # a linha depois de "CAPÍTULO II" é o título dele

    def close_article() -> None:
        if article is not None:
            chunks.append(Chunk(norm, article, article_section, "\n".join(article_lines)))

    for index, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue

        heading = HEADING_LINE.match(line)
        if heading:
            kind, numeral = heading.groups()
            title = lines[index + 1] if index + 1 < len(lines) else ""
            skip_next = True
            if kind == "CAPÍTULO":
                chapter = f"Capítulo {numeral} — {title.capitalize()}"
                section = ""  # capítulo novo: a seção anterior deixa de valer
            else:
                section = f"Seção {numeral} — {title}"
            continue

        start = ARTICLE_LINE.match(line)
        if start:
            close_article()
            article = start.group(1)
            article_section = " / ".join(part for part in (chapter, section) if part)
            article_lines = [line]
        elif article is not None:
            article_lines.append(line)

    close_article()  # o último artigo não é fechado por nenhum "Art." seguinte
    return chunks


def load_corpus(folder: Path) -> list[Chunk]:
    """Lê todos os arquivos .txt da pasta (em ordem alfabética) e junta os chunks.

    Args:
        folder: Pasta com os textos das normas, normalmente `data/normas/`.

    Returns:
        Chunks de todas as normas, uma norma depois da outra.
    """
    chunks: list[Chunk] = []
    for path in sorted(Path(folder).glob("*.txt")):
        norm = NORM_LABELS.get(path.stem, path.stem)
        chunks.extend(parse_norm(path.read_text(encoding="utf-8"), norm))
    return chunks
