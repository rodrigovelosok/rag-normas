"""Configuração do sistema, lida de variáveis de ambiente com valores padrão (RF08)."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path


class ConfigError(ValueError):
    """Valor de configuração inválido."""


# Regras de validação dos campos numéricos: (tipo, condição, explicação mostrada no erro).
# Ficam num só lugar para valer tanto para variável de ambiente quanto para valor passado no código.
_RULES = {
    "top_k": (int, lambda v: v >= 1, "deve ser um número inteiro maior que 0"),
    "rrf_k": (int, lambda v: v >= 1, "deve ser um número inteiro maior que 0"),
    "min_similarity": (float, lambda v: 0.0 <= v <= 1.0, "deve ser um número entre 0 e 1"),
    "num_ctx": (int, lambda v: v >= 1, "deve ser um número inteiro maior que 0"),
    "timeout": (float, lambda v: v > 0, "deve ser um número maior que 0"),
}

# Variável de ambiente -> campo de Settings.
_ENV = {
    "RAG_OLLAMA_HOST": "ollama_host",
    "RAG_CHAT_MODEL": "chat_model",
    "RAG_EMBED_MODEL": "embed_model",
    "RAG_TOP_K": "top_k",
    "RAG_RRF_K": "rrf_k",
    "RAG_MIN_SIMILARITY": "min_similarity",
    "RAG_NUM_CTX": "num_ctx",
    "RAG_TIMEOUT": "timeout",
    "RAG_INDEX_PATH": "index_path",
    "RAG_CORPUS_DIR": "corpus_dir",
}
_PATH_FIELDS = {"index_path", "corpus_dir"}


@dataclass(frozen=True)
class Settings:
    """Tudo o que o usuário pode ajustar. Imutável: para mudar algo, use `with_overrides`.

    Attributes:
        ollama_host: Endereço do servidor Ollama.
        chat_model: Modelo que escreve a resposta.
        embed_model: Modelo que transforma textos em vetores.
        top_k: Quantos artigos entram no contexto da resposta.
        rrf_k: Constante do RRF, que junta o ranking por vetor com o ranking por palavras. Menor dá mais peso
            às primeiras posições de cada lista. 5 em vez dos 60 da literatura: na avaliação com 21 perguntas
            a recuperação em k = 4 subiu de 84% para 97% (eval/relatorios/busca.md e busca-rrf5.md).
        min_similarity: Similaridade mínima para tentar responder; abaixo disso o sistema recusa.
            0,56 = meio da faixa 0,54 a 0,58, a única sem erro nas 21 perguntas de avaliação (a pergunta recusável
            mais parecida com o corpus tem 0,536 e a respondível menos parecida, 0,584). Folga pequena: reavaliar
            ao mudar o corpus, o modelo de embedding ou as perguntas.
        num_ctx: Tamanho da janela de contexto do modelo, em tokens. O padrão do Ollama (4096) é pequeno
            demais para vários artigos longos; o art. 4º da IN 2.091 sozinho tem ~4.100 caracteres.
        timeout: Segundos de espera pela resposta do Ollama. A primeira chamada carrega o modelo e demora.
        index_path: Onde o índice é gravado e lido.
        corpus_dir: Pasta com os textos das normas.
    """

    ollama_host: str = "http://localhost:11434"
    chat_model: str = "qwen2.5:3b"
    embed_model: str = "bge-m3"
    top_k: int = 4
    rrf_k: int = 5
    min_similarity: float = 0.56
    num_ctx: int = 8192
    timeout: float = 300.0
    index_path: Path = Path("data/index.json")
    corpus_dir: Path = Path("data/normas")

    def __post_init__(self) -> None:
        for field, (_, is_valid, explanation) in _RULES.items():
            value = getattr(self, field)
            if not is_valid(value):
                raise ConfigError(f"{field} {explanation}; recebi {value!r}")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        """Monta a configuração a partir das variáveis RAG_*. Variável ausente ou vazia usa o padrão.

        Args:
            environ: Variáveis de ambiente. Se omitido, usa as do sistema (`os.environ`).

        Raises:
            ConfigError: Se algum valor for inválido; a mensagem cita o nome da variável.
        """
        environ = os.environ if environ is None else environ
        values: dict[str, object] = {}
        for variable, field in _ENV.items():
            raw = environ.get(variable, "").strip()
            if not raw:
                continue
            if field in _RULES:
                cast, is_valid, explanation = _RULES[field]
                try:
                    value = cast(raw)
                except ValueError:
                    raise ConfigError(f"{variable} {explanation}; recebi {raw!r}") from None
                if not is_valid(value):
                    raise ConfigError(f"{variable} {explanation}; recebi {raw!r}")
                values[field] = value
            elif field in _PATH_FIELDS:
                values[field] = Path(raw)
            else:
                values[field] = raw
        return cls(**values)

    def with_overrides(self, **changes: object) -> Settings:
        """Devolve uma cópia com os campos trocados. Valor `None` é ignorado (útil para opções da linha de comando)."""
        return replace(self, **{name: value for name, value in changes.items() if value is not None})
