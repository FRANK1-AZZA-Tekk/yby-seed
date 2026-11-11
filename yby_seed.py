#!/usr/bin/env python3
"""YBY SEED — fachada canônica (Camada A).

Sem argumentos → REPL do framework (chat + /brief /skills /status /layers).
Com argumentos → delega à CLI Click em src/main.py

    python yby_seed.py
    python yby_seed.py brief -r "Quero backup" -a "~/Docs" --approve
    python yby_seed.py skills
    python yby_seed.py doctor
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    if args:
        # Delega à CLI Click (doctor, setup, test, brief, status, run, …)
        from src.main import cli

        try:
            cli.main(args=args, prog_name="yby_seed")
        except SystemExit as exc:
            code = exc.code
            if code is None:
                return 0
            if isinstance(code, int):
                return code
            return 1
        return 0

    from src.app import create_app

    return create_app().repl()


if __name__ == "__main__":
    raise SystemExit(main())
