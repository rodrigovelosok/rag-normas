"""Ponto de entrada: `python -m rag_normas index` e `python -m rag_normas ask "pergunta"`."""

import sys

from rag_normas.cli import main

if __name__ == "__main__":
    # Texto que o console não saiba representar (símbolos que o modelo escreva) vira "?" em vez de derrubar o programa.
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
    sys.exit(main())
