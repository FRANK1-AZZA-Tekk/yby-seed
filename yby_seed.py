#!/usr/bin/env python3
"""YBY SEED — terminal local-first (Function Over Form).

Passo 2: loop de comandos + LiteLLM (OpenRouter → fallback Ollama).

Uso:
    python yby_seed.py
    # digite um comando, Enter
    # sair: quit / exit / :q
"""

from __future__ import annotations

import sys

from modules.llm_brain import ask_llm, load_llm_config


def _print_banner(provider: str, model: str) -> None:
    print("YBY SEED — Function Over Form")
    print(f"Provedor: {provider} | Modelo: {model}")
    print("Comandos: texto livre | sair: quit / exit / :q")
    print("-" * 40)


def main() -> int:
    try:
        config = load_llm_config()
    except Exception as exc:  # noqa: BLE001
        print(f"Erro ao carregar configuração: {exc}", file=sys.stderr)
        return 1

    _print_banner(config.provider, config.model)

    while True:
        try:
            user_text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not user_text:
            continue
        if user_text.lower() in {"quit", "exit", ":q", "sair"}:
            return 0

        try:
            answer = ask_llm(user_text, config)
        except Exception as exc:  # noqa: BLE001
            print(f"Erro: {exc}", file=sys.stderr)
            continue

        print(answer)
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
