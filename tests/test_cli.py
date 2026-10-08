"""Testes da linha de comando (RF03, RF04, RF08). Nenhum usa o Ollama: o `llm_factory` entrega funções falsas."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from rag_normas import cli
from rag_normas.cli import main
from rag_normas.generate import DISCLAIMER, REFUSAL_MESSAGE
from rag_normas.index import load_index
from rag_normas.llm import LLMError

VOCABULARY = ["arrolamento", "cancelamento", "imovel"]
CORPUS_TEXT = "Art. 1º Texto sobre arrolamento.\nArt. 2º Texto sobre cancelamento.\n"
REPLY = "Resposta de teste. [Fonte: norma-teste, art. 1º]"


def fake_embed(texts: list[str]) -> list[list[float]]:
    """Vetor de contagem de palavras: a pergunta "arrolamento" é idêntica ao art. 1º e ortogonal ao art. 2º."""
    vectors = []
    for text in texts:
        words = text.lower().replace(".", " ").replace("º", " ").split()
        vectors.append([float(words.count(word)) for word in VOCABULARY])
    return vectors


class FakeLLM:
    """llm_factory falso: guarda as Settings recebidas e as mensagens enviadas ao chat."""

    def __init__(self, reply: str = REPLY, embed=fake_embed, chat_error: Exception | None = None):
        self.reply = reply
        self.embed = embed
        self.chat_error = chat_error
        self.settings_seen: list = []
        self.chat_calls: list = []

    def __call__(self, settings):
        self.settings_seen.append(settings)
        return self.embed, self.chat

    def chat(self, messages):
        self.chat_calls.append(messages)
        if self.chat_error:
            raise self.chat_error
        return self.reply


@pytest.fixture
def paths(tmp_path):
    corpus = tmp_path / "normas"
    corpus.mkdir()
    (corpus / "norma-teste.txt").write_text(CORPUS_TEXT, encoding="utf-8")
    return {"corpus": corpus, "index": tmp_path / "index.json", "tmp": tmp_path}


def where(paths) -> list[str]:
    return ["--corpus", str(paths["corpus"]), "--index", str(paths["index"])]


def run_index(paths, extra=(), env=None, llm=None) -> int:
    return main(["index", *where(paths), *extra], environ=env or {}, llm_factory=llm or FakeLLM())


def run_ask(paths, question, extra=(), env=None, llm=None) -> int:
    return main(["ask", question, "--index", str(paths["index"]), *extra], environ=env or {}, llm_factory=llm or FakeLLM())


@pytest.fixture
def indexed(paths):
    assert run_index(paths) == 0
    return paths


# ---------- index ----------

def test_index_writes_the_index_and_reports(paths, capsys):
    assert run_index(paths) == 0
    index = load_index(paths["index"])
    assert [chunk.article for chunk in index.chunks] == ["1", "2"]
    assert index.embedding_model == "bge-m3"
    out = capsys.readouterr()
    assert "2 artigos" in out.out and "bge-m3" in out.out
    assert "2/2" in out.err  # progresso


def test_index_uses_the_embed_model_option(paths):
    llm = FakeLLM()
    assert run_index(paths, ["--embed-model", "outro-modelo"], llm=llm) == 0
    assert load_index(paths["index"]).embedding_model == "outro-modelo"
    assert llm.settings_seen[0].embed_model == "outro-modelo"


def test_index_with_empty_corpus_fails_before_calling_ollama(paths, capsys):
    empty = paths["tmp"] / "vazia"
    empty.mkdir()
    llm = FakeLLM()
    code = main(["index", "--corpus", str(empty), "--index", str(paths["index"])], environ={}, llm_factory=llm)
    assert code == 1
    err = capsys.readouterr().err
    assert err.startswith("Erro:") and "--corpus" in err
    assert llm.settings_seen == []
    assert not paths["index"].exists()


def test_index_reports_an_ollama_failure_without_traceback(paths, capsys):
    def broken_embed(texts):
        raise LLMError("Não consegui falar com o Ollama. Execute: ollama serve")

    assert run_index(paths, llm=FakeLLM(embed=broken_embed)) == 1
    out = capsys.readouterr()
    assert "Erro: Não consegui falar com o Ollama" in out.err
    assert "Traceback" not in out.err and out.out == ""
    assert not paths["index"].exists()


# ---------- ask ----------

def test_ask_prints_answer_sources_and_disclaimer(indexed, capsys):
    llm = FakeLLM()
    assert run_ask(indexed, "arrolamento", llm=llm) == 0
    out = capsys.readouterr().out
    assert "Resposta de teste." in out
    assert "Fontes consultadas:" in out and "- norma-teste, art. 1º" in out
    assert out.rstrip().endswith(DISCLAIMER)
    assert len(llm.chat_calls) == 1
    assert "Texto sobre arrolamento" in llm.chat_calls[0][1]["content"]  # o artigo foi enviado ao modelo


def test_ask_refuses_without_calling_the_chat(indexed, capsys):
    llm = FakeLLM()
    assert run_ask(indexed, "imovel", llm=llm) == 0  # recusar é um resultado válido
    out = capsys.readouterr().out
    assert out.startswith(REFUSAL_MESSAGE) and out.rstrip().endswith(DISCLAIMER)
    assert llm.chat_calls == []


def test_min_similarity_option_changes_the_decision(indexed, capsys):
    # "imovel arrolamento" tem cosseno 0,707 com o art. 1º.
    assert run_ask(indexed, "imovel arrolamento", ["--min-similarity", "0.6"]) == 0
    assert REFUSAL_MESSAGE not in capsys.readouterr().out
    assert run_ask(indexed, "imovel arrolamento", ["--min-similarity", "0.8"]) == 0
    assert REFUSAL_MESSAGE in capsys.readouterr().out


def test_ask_flags_a_citation_that_is_not_in_the_index(indexed, capsys):
    llm = FakeLLM(reply="Texto. [Fonte: norma-teste, art. 99]")
    assert run_ask(indexed, "arrolamento", llm=llm) == 0
    assert "ATENÇÃO" in capsys.readouterr().out  # a conferência usa os artigos do índice


def test_citation_of_an_indexed_article_that_was_not_retrieved_is_not_flagged(indexed, capsys):
    # Com --top-k 1 só o art. 1º é recuperado; citar o art. 2º é citar um artigo que existe no índice.
    llm = FakeLLM(reply="Texto. [Fonte: norma-teste, art. 2º]")
    assert run_ask(indexed, "arrolamento", ["--top-k", "1"], llm=llm) == 0
    assert "ATENÇÃO" not in capsys.readouterr().out


def test_ask_with_missing_index_fails_before_calling_ollama(paths, capsys):
    llm = FakeLLM()
    assert run_ask(paths, "arrolamento", llm=llm) == 1
    err = capsys.readouterr().err
    assert err.startswith("Erro:") and "python -m rag_normas index" in err
    assert llm.settings_seen == []


def test_ask_with_index_from_another_embed_model_fails(paths, capsys):
    assert run_index(paths, ["--embed-model", "modelo-a"]) == 0
    llm = FakeLLM()
    assert run_ask(paths, "arrolamento", ["--embed-model", "modelo-b"], llm=llm) == 1
    err = capsys.readouterr().err
    assert "modelo-a" in err and "modelo-b" in err
    assert llm.settings_seen == []


def test_ask_reports_a_chat_failure_without_traceback(indexed, capsys):
    llm = FakeLLM(chat_error=LLMError("O modelo 'x' não está instalado. Instale com: ollama pull x"))
    assert run_ask(indexed, "arrolamento", llm=llm) == 1
    out = capsys.readouterr()
    assert out.err.startswith("Erro: O modelo 'x'") and "Traceback" not in out.err
    assert out.out == ""


def test_ask_with_blank_question_is_a_usage_error(indexed, capsys):
    llm = FakeLLM()
    assert run_ask(indexed, "   ", llm=llm) == 2
    assert "pergunta" in capsys.readouterr().err.lower()
    assert llm.settings_seen == []


# ---------- opções, ambiente e precedência (RF08) ----------

def sources_in(output: str) -> list[str]:
    return [line for line in output.splitlines() if line.startswith("- ")]


def test_top_k_option_limits_the_sources(indexed, capsys):
    assert run_ask(indexed, "arrolamento cancelamento", ["--top-k", "1"]) == 0
    assert len(sources_in(capsys.readouterr().out)) == 1
    assert run_ask(indexed, "arrolamento cancelamento", ["-k", "2"]) == 0
    assert len(sources_in(capsys.readouterr().out)) == 2


def test_environment_variable_is_used_and_the_option_wins(indexed, capsys):
    env = {"RAG_TOP_K": "1"}
    assert run_ask(indexed, "arrolamento cancelamento", env=env) == 0
    assert len(sources_in(capsys.readouterr().out)) == 1
    assert run_ask(indexed, "arrolamento cancelamento", ["--top-k", "2"], env=env) == 0
    assert len(sources_in(capsys.readouterr().out)) == 2


def spy_on_the_search(monkeypatch) -> dict:
    """Troca a busca por uma cópia que anota com quais argumentos foi chamada."""
    seen: dict = {}
    real = cli.hybrid_search

    def spy(*args, **kwargs):
        seen.update(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(cli, "hybrid_search", spy)
    return seen


def test_rrf_k_option_reaches_the_search(indexed, monkeypatch):
    seen = spy_on_the_search(monkeypatch)
    assert run_ask(indexed, "arrolamento", ["--rrf-k", "7"]) == 0
    assert seen["rrf_k"] == 7 and seen["k"] == 4


def test_rrf_k_comes_from_the_environment_and_the_option_wins(indexed, monkeypatch):
    seen = spy_on_the_search(monkeypatch)
    assert run_ask(indexed, "arrolamento", env={"RAG_RRF_K": "9"}) == 0
    assert seen["rrf_k"] == 9
    assert run_ask(indexed, "arrolamento", ["--rrf-k", "3"], env={"RAG_RRF_K": "9"}) == 0
    assert seen["rrf_k"] == 3


def test_model_and_host_options_reach_the_settings(indexed):
    llm = FakeLLM()
    assert run_ask(indexed, "arrolamento", ["--model", "qwen2.5:7b", "--host", "http://outro:11434"], llm=llm) == 0
    settings = llm.settings_seen[0]
    assert settings.chat_model == "qwen2.5:7b" and settings.ollama_host == "http://outro:11434"


def test_defaults_are_used_when_nothing_is_given(indexed):
    llm = FakeLLM()
    assert run_ask(indexed, "arrolamento", llm=llm) == 0
    settings = llm.settings_seen[0]
    assert settings.chat_model == "qwen2.5:3b" and settings.top_k == 4


def test_invalid_option_value_is_reported_with_the_field(indexed, capsys):
    assert run_ask(indexed, "arrolamento", ["--top-k", "0"]) == 1
    assert "top_k" in capsys.readouterr().err


def test_invalid_environment_variable_names_the_variable(indexed, capsys):
    assert run_ask(indexed, "arrolamento", env={"RAG_TOP_K": "abc"}) == 1
    assert "RAG_TOP_K" in capsys.readouterr().err


def test_non_numeric_option_is_rejected_by_argparse(indexed):
    with pytest.raises(SystemExit) as stop:
        run_ask(indexed, "arrolamento", ["--top-k", "abc"])
    assert stop.value.code == 2


# ---------- --scores ----------

def test_scores_option_shows_threshold_and_similarities_on_stderr(indexed, capsys):
    assert run_ask(indexed, "arrolamento", ["--scores"]) == 0
    err = capsys.readouterr().err
    assert "limiar" in err.lower() and "0.56" in err
    assert "1.000" in err and "norma-teste, art. 1º" in err


def test_without_scores_option_stderr_stays_quiet(indexed, capsys):
    assert run_ask(indexed, "arrolamento") == 0
    assert capsys.readouterr().err == ""


# ---------- uso e ponto de entrada ----------

@pytest.mark.parametrize("argv", [[], ["inexistente"], ["ask"]])
def test_bad_usage_exits_with_code_2(argv):
    with pytest.raises(SystemExit) as stop:
        main(argv, environ={}, llm_factory=FakeLLM())
    assert stop.value.code == 2


def test_module_entry_point_shows_help():
    root = Path(__file__).resolve().parent.parent
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}  # sem isso o Windows redireciona a saída em cp1252
    result = subprocess.run(
        [sys.executable, "-m", "rag_normas", "--help"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0
    assert "index" in result.stdout and "ask" in result.stdout
