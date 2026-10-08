"""Linha de comando: liga os módulos nos comandos `index` e `ask` (RF03, RF04, RF08).

Precedência das configurações: opção da linha de comando > variável de ambiente `RAG_*` > valor padrão.
"""

import argparse
import sys
from collections.abc import Callable, Mapping
from pathlib import Path

from rag_normas.config import ConfigError, Settings
from rag_normas.generate import ChatFn, answer, format_output
from rag_normas.index import IndexFileError, build_index, load_index, save_index
from rag_normas.ingest import load_corpus
from rag_normas.llm import LLMError, make_llm
from rag_normas.search import EmbedFn, hybrid_search

# Recebe a configuração e devolve (embed, chat). Em produção é `make_llm`; nos testes, uma função falsa.
LlmFactory = Callable[[Settings], tuple[EmbedFn, ChatFn]]


def build_parser() -> argparse.ArgumentParser:
    """Monta o interpretador dos comandos. Valor não informado fica `None`, para não sobrepor o ambiente."""
    options = argparse.ArgumentParser(add_help=False)  # opções comuns aos dois comandos
    options.add_argument("--host", help="endereço do Ollama (padrão: http://localhost:11434)")
    options.add_argument("--model", help="modelo de chat (padrão: qwen2.5:3b)")
    options.add_argument("--embed-model", help="modelo de embedding (padrão: bge-m3)")
    options.add_argument("-k", "--top-k", type=int, help="quantos artigos entram na resposta (padrão: 4)")
    options.add_argument("--min-similarity", type=float, help="similaridade mínima para responder (padrão: 0.52)")
    options.add_argument("--index", type=Path, help="arquivo do índice (padrão: data/index.json)")
    options.add_argument("--corpus", type=Path, help="pasta com os textos das normas (padrão: data/normas)")

    parser = argparse.ArgumentParser(
        prog="python -m rag_normas",
        description="Perguntas e respostas sobre a legislação de arrolamento de bens, citando o artigo.",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="{index,ask}")
    commands.add_parser("index", parents=[options], help="lê as normas e gera o índice (demora cerca de 1 minuto)")
    ask = commands.add_parser("ask", parents=[options], help="responde a uma pergunta")
    ask.add_argument("question", help="a pergunta, entre aspas")
    ask.add_argument("--scores", action="store_true", help="mostra o limiar e a similaridade de cada artigo")
    return parser


def main(
    argv: list[str] | None = None,
    environ: Mapping[str, str] | None = None,
    llm_factory: LlmFactory = make_llm,
) -> int:
    """Executa um comando e devolve o código de saída: 0 sucesso, 1 erro, 2 erro de uso.

    Args:
        argv: Argumentos (sem o nome do programa). Padrão: os da linha de comando.
        environ: Variáveis de ambiente. Padrão: as do sistema.
        llm_factory: Cria `(embed, chat)` a partir da configuração.
    """
    args = build_parser().parse_args(argv)
    if args.command == "ask" and not args.question.strip():
        return _fail('a pergunta está vazia. Exemplo: python -m rag_normas ask "Quando o arrolamento é feito?"', code=2)

    try:
        settings = Settings.from_env(environ).with_overrides(
            ollama_host=args.host,
            chat_model=args.model,
            embed_model=args.embed_model,
            top_k=args.top_k,
            min_similarity=args.min_similarity,
            index_path=args.index,
            corpus_dir=args.corpus,
        )
        if args.command == "index":
            return _run_index(settings, llm_factory)
        return _run_ask(args.question, settings, llm_factory, show_scores=args.scores)
    except (ConfigError, LLMError, IndexFileError) as error:
        return _fail(str(error))


def _run_index(settings: Settings, llm_factory: LlmFactory) -> int:
    chunks = load_corpus(settings.corpus_dir)
    if not chunks:  # falha antes de chamar o Ollama
        return _fail(
            f"nenhum artigo encontrado em {settings.corpus_dir}. "
            "Coloque os textos das normas (.txt) nessa pasta ou indique outra com --corpus."
        )

    embed, _ = llm_factory(settings)
    print(f"Indexando {len(chunks)} artigos com {settings.embed_model}...", file=sys.stderr)
    index = build_index(
        chunks,
        embed,
        settings.embed_model,
        on_progress=lambda done, total: print(f"  {done}/{total} artigos", file=sys.stderr),
    )
    save_index(index, settings.index_path)
    print(f"Índice gravado em {settings.index_path} ({len(index.chunks)} artigos, modelo {index.embedding_model}).")
    return 0


def _run_ask(question: str, settings: Settings, llm_factory: LlmFactory, show_scores: bool) -> int:
    # O índice é lido antes de criar o cliente do Ollama: índice ausente ou de outro modelo falha sem chamá-lo.
    index = load_index(settings.index_path, expected_model=settings.embed_model)
    embed, chat = llm_factory(settings)

    hits = hybrid_search(question, index.chunks, index.vectors, embed, k=settings.top_k)
    if show_scores:
        print(f"limiar de recusa: {settings.min_similarity:g}", file=sys.stderr)
        for hit in hits:
            print(f"similaridade {hit.similarity:.3f}  {hit.chunk.reference}", file=sys.stderr)

    result = answer(question, hits, chat, index.chunks, settings.min_similarity)
    print(format_output(result))
    return 0


def _fail(message: str, code: int = 1) -> int:
    print(f"Erro: {message}", file=sys.stderr)
    return code
