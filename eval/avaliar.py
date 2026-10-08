"""Avaliação do sistema (RF09): linha de comando do avaliador.

Comandos:
    python -m eval.avaliar retrieval   mede só a BUSCA (sem modelo de chat) e ajuda a calibrar k e o limiar de recusa
    python -m eval.avaliar answers     roda as perguntas com o modelo de chat e mede a resposta de ponta a ponta
    python -m eval.avaliar rescore     reavalia respostas já gravadas com o gabarito atual (sem Ollama)
    python -m eval.avaliar compare     compara rodadas gravadas lado a lado

O avaliador está dividido por assunto, e cada módulo só importa os anteriores:
    gabarito.py  perguntas, validação e conferência dos itens
    metricas.py  o que se mede, varreduras de calibração e resumo
    rodada.py    execução: busca, chat e arquivos .jsonl
    markdown.py  relatórios
    avaliar.py   linha de comando (este arquivo)
"""

import argparse
import re
import sys
from collections.abc import Callable, Mapping
from datetime import date
from pathlib import Path

from eval.gabarito import Question, QuestionsError, load_questions, select_questions
from eval.markdown import render_comparison, render_report, render_retrieval_report
from eval.metricas import AnswerScore, ResultsError, sweep_rrf_k
from eval.rodada import load_scores, make_search, rescore, retrieve, run_answers, save_scores
from rag_normas.config import ConfigError, Settings
from rag_normas.generate import ChatFn
from rag_normas.index import Index, IndexFileError, load_index
from rag_normas.llm import LLMError, make_llm
from rag_normas.search import EmbedFn

DEFAULT_QUESTIONS = Path("eval/perguntas.json")
REPORTS_DIR = Path("eval/relatorios")
DEFAULT_THRESHOLDS = [round(0.40 + 0.02 * step, 2) for step in range(16)]  # 0,40 a 0,70
DEFAULT_RRF_KS = [1, 5, 10, 20, 30, 60, 100]  # constantes do RRF testadas na varredura
RRF_SWEEP_KS = [3, 4, 5, 6]  # k em que a varredura mede a recuperação


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--questions", type=Path, default=DEFAULT_QUESTIONS, help="arquivo de perguntas (padrão: eval/perguntas.json)"
    )
    common.add_argument("--index", type=Path, help="arquivo do índice (padrão: data/index.json)")
    common.add_argument("--host", help="endereço do Ollama")
    common.add_argument("--embed-model", help="modelo de embedding")
    common.add_argument("-k", "--top-k", type=int, help="quantos artigos entram na resposta (padrão: 4)")
    common.add_argument("--rrf-k", type=int, help="constante do RRF (padrão: 5)")

    parser = argparse.ArgumentParser(
        prog="python -m eval.avaliar", description="Avalia a busca e as respostas do rag-normas."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    retrieval = commands.add_parser(
        "retrieval", parents=[common], help="avalia só a busca e a varredura do limiar (rápido, sem chat)"
    )
    retrieval.add_argument("--max-k", type=int, default=8, help="maior k da tabela de recuperação (padrão: 8)")
    retrieval.add_argument("--report", type=Path, default=REPORTS_DIR / "busca.md", help="onde gravar o relatório")

    answers = commands.add_parser("answers", parents=[common], help="roda as perguntas com o modelo de chat (lento)")
    answers.add_argument("--model", help="modelo de chat (padrão: qwen2.5:3b)")
    answers.add_argument("--min-similarity", type=float, help="limiar de recusa (padrão: 0.56)")
    answers.add_argument("--only", help="ids separados por vírgula, por exemplo Q01,Q05")
    answers.add_argument(
        "--resume", action="store_true", help="não repete as perguntas já gravadas no arquivo de saída"
    )
    answers.add_argument(
        "--output",
        type=Path,
        help="arquivo .jsonl de resultados (padrão: eval/relatorios/respostas-<modelo>-k<k>.jsonl)",
    )
    answers.add_argument(
        "--report", type=Path, help="relatório em Markdown (padrão: o mesmo nome do --output, com .md)"
    )

    again = commands.add_parser(
        "rescore", help="reavalia respostas já gravadas com o gabarito atual (sem Ollama nem índice)"
    )
    again.add_argument(
        "--questions", type=Path, default=DEFAULT_QUESTIONS, help="arquivo de perguntas (padrão: eval/perguntas.json)"
    )
    again.add_argument("--input", type=Path, required=True, help="arquivo .jsonl gravado por 'answers'")
    again.add_argument(
        "--output", type=Path, help="onde gravar os resultados reavaliados (padrão: reescreve o --input)"
    )
    again.add_argument(
        "--report", type=Path, help="relatório em Markdown (padrão: o mesmo nome do arquivo de saída, com .md)"
    )
    again.add_argument("--model", required=True, help="nome do modelo, só para o cabeçalho do relatório")
    again.add_argument("-k", "--top-k", type=int, help="k usado na rodada original, para o cabeçalho (padrão: 4)")
    again.add_argument(
        "--rrf-k", type=int, help="constante do RRF usada na rodada original, para o cabeçalho (padrão: 5)"
    )
    again.add_argument(
        "--min-similarity", type=float, help="limiar usado na rodada original, para o cabeçalho (padrão: 0.56)"
    )

    compare = commands.add_parser(
        "compare", help="compara rodadas gravadas das mesmas perguntas (por exemplo, 3b e 7b)"
    )
    compare.add_argument("--inputs", type=Path, nargs="+", required=True, help="arquivos .jsonl de resultados")
    compare.add_argument("--names", nargs="+", required=True, help="um nome para cada arquivo, na mesma ordem")
    compare.add_argument("--report", type=Path, default=REPORTS_DIR / "comparacao.md", help="onde gravar o relatório")
    return parser


def main(
    argv: list[str] | None = None,
    environ: Mapping[str, str] | None = None,
    llm_factory: Callable[[Settings], tuple[EmbedFn, ChatFn]] = make_llm,
) -> int:
    """Executa um comando e devolve o código de saída: 0 sucesso, 1 erro, 2 erro de uso."""
    args = build_parser().parse_args(argv)
    try:
        if args.command == "compare":  # só lê resultados gravados
            return _run_compare(args)
        settings = Settings.from_env(environ).with_overrides(
            ollama_host=getattr(args, "host", None),
            embed_model=getattr(args, "embed_model", None),
            top_k=args.top_k,
            rrf_k=args.rrf_k,
            index_path=getattr(args, "index", None),
            chat_model=getattr(args, "model", None),
            min_similarity=getattr(args, "min_similarity", None),
        )
        if args.command == "rescore":  # só relê o que já foi gravado: não precisa do índice nem do Ollama
            return _run_rescore(args, settings)
        index = load_index(settings.index_path, expected_model=settings.embed_model)
        questions = load_questions(args.questions, valid_articles={chunk.reference for chunk in index.chunks})
        if args.command == "retrieval":
            return _run_retrieval(args, settings, index, questions, llm_factory)
        return _run_answers(args, settings, index, questions, llm_factory)
    except (ConfigError, LLMError, IndexFileError, QuestionsError, ResultsError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1


def _run_compare(args) -> int:
    for path in args.inputs:
        if not path.exists():
            raise ResultsError(f"arquivo de resultados não encontrado: {path}")
    report = render_comparison(args.names, [load_scores(path) for path in args.inputs], date.today().isoformat())
    _write(args.report, report)
    print(report, end="")
    return 0


def _run_rescore(args, settings: Settings) -> int:
    if not args.input.exists():
        raise ResultsError(f"arquivo de resultados não encontrado: {args.input}")
    questions = load_questions(args.questions)
    scores = rescore(questions, load_scores(args.input))
    output = args.output or args.input
    save_scores(output, scores)
    report = render_report(
        settings.chat_model, settings.top_k, settings.min_similarity, scores, date.today().isoformat(), settings.rrf_k
    )
    _write(args.report or output.with_suffix(".md"), report)
    print(report, end="")
    return 0


def _memoized(embed: EmbedFn) -> EmbedFn:
    """Guarda o resultado de cada chamada: o mesmo texto não é enviado ao Ollama duas vezes."""
    cache: dict[tuple[str, ...], list[list[float]]] = {}

    def wrapper(texts: list[str]) -> list[list[float]]:
        key = tuple(texts)
        if key not in cache:
            cache[key] = embed(texts)
        return cache[key]

    return wrapper


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run_retrieval(args, settings: Settings, index: Index, questions: list[Question], llm_factory) -> int:
    raw_embed, _ = llm_factory(settings)
    embed = _memoized(raw_embed)  # a pergunta é a mesma em todas as buscas da varredura: um embedding por pergunta
    max_k = max(args.max_k, settings.top_k)
    hits = retrieve(questions, index, embed, max_k, settings.rrf_k)
    rrf_rows = sweep_rrf_k(questions, make_search(index, embed), DEFAULT_RRF_KS, RRF_SWEEP_KS)
    report = render_retrieval_report(
        questions,
        hits,
        settings.top_k,
        list(range(1, max_k + 1)),
        DEFAULT_THRESHOLDS,
        date.today().isoformat(),
        rrf_rows,
        settings.rrf_k,
    )
    _write(args.report, report)
    print(report, end="")
    return 0


def _run_answers(args, settings: Settings, index: Index, questions: list[Question], llm_factory) -> int:
    if args.only:
        questions = select_questions(questions, args.only)

    slug = re.sub(r"[^a-z0-9.]+", "-", settings.chat_model.lower()).strip("-")
    output = args.output or REPORTS_DIR / f"respostas-{slug}-k{settings.top_k}.jsonl"
    report_path = args.report or output.with_suffix(".md")

    embed, chat = llm_factory(settings)
    hits = retrieve(questions, index, embed, settings.top_k, settings.rrf_k)

    def progress(number: int, total: int, score: AnswerScore) -> None:
        print(
            f"[{number}/{total}] {score.id} {'ok' if score.correct else 'falhou'} ({score.seconds:.0f} s)",
            file=sys.stderr,
        )

    scores = run_answers(
        questions,
        hits,
        chat,
        index.chunks,
        settings.min_similarity,
        output=output,
        resume=args.resume,
        on_progress=progress,
    )
    report = render_report(
        settings.chat_model, settings.top_k, settings.min_similarity, scores, date.today().isoformat(), settings.rrf_k
    )
    _write(report_path, report)
    print(report, end="")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
    sys.exit(main())
