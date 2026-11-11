"""Kernel do app — despacho de comandos e REPL."""

from __future__ import annotations

import shlex
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TextIO

from src.app.config import AppSettings, load_settings
from src.app.layers import LayerRegistry

CommandHandler = Callable[["App", list[str]], int]


@dataclass
class App:
    """Hub local-first: um kernel, camadas empilháveis, CLI honesta."""

    settings: AppSettings
    layers: LayerRegistry = field(default_factory=LayerRegistry)
    stdin: TextIO = field(default_factory=lambda: sys.stdin)
    stdout: TextIO = field(default_factory=lambda: sys.stdout)
    stderr: TextIO = field(default_factory=lambda: sys.stderr)

    def __post_init__(self) -> None:
        self._commands: dict[str, CommandHandler] = {
            "help": _cmd_help,
            "h": _cmd_help,
            "?": _cmd_help,
            "status": _cmd_status,
            "layers": _cmd_layers,
            "brief": _cmd_brief,
            "chat": _cmd_chat,
            "ask": _cmd_chat,
        }

    def dispatch(self, argv: list[str]) -> int:
        """Despacha um comando do framework. Retorna código de saída."""
        if not argv:
            return self._commands["help"](self, [])
        name = argv[0].lower().lstrip("/")
        args = argv[1:]
        handler = self._commands.get(name)
        if handler is None:
            self.stderr.write(
                f"Comando desconhecido: {name!r}. Use /help.\n"
            )
            return 2
        return handler(self, args)

    def handle_line(self, line: str) -> int | None:
        """Processa uma linha do REPL.

        Retorna código de saída se deve encerrar, senão None.
        """
        text = line.strip()
        if not text:
            return None
        if text.lower() in {"quit", "exit", ":q", "sair", "/quit", "/exit"}:
            return 0
        if text.startswith("/"):
            try:
                parts = shlex.split(text)
            except ValueError as exc:
                self.stderr.write(f"ERRO parse: {exc}\n")
                return None
            code = self.dispatch(parts)
            if code not in (0, None):
                # comandos slash não encerram o REPL por erro de negócio
                return None
            return None
        # texto livre → chat
        self.dispatch(["chat", text])
        return None

    def repl(self) -> int:
        """Loop interativo: slash commands + chat LiteLLM."""
        from modules.llm_brain import load_llm_config

        try:
            llm = load_llm_config()
            provider, model = llm.provider, llm.model
        except Exception as exc:  # noqa: BLE001
            provider, model = "?", f"(erro: {exc})"

        self.stdout.write("YBY SEED — Function Over Form\n")
        self.stdout.write(f"Provedor: {provider} | Modelo: {model}\n")
        self.stdout.write(
            "Comandos: /help /status /layers /brief | texto livre = chat | sair: quit\n"
        )
        self.stdout.write("-" * 40 + "\n")

        while True:
            try:
                self.stdout.write("> ")
                self.stdout.flush()
                line = self.stdin.readline()
            except KeyboardInterrupt:
                self.stdout.write("\n")
                return 0
            if line == "":
                self.stdout.write("\n")
                return 0
            result = self.handle_line(line)
            if result is not None:
                return result


def create_app(project_root=None) -> App:
    """Factory do kernel com settings do ambiente."""
    return App(settings=load_settings(project_root))


def _cmd_help(app: App, _args: list[str]) -> int:
    app.stdout.write(
        "Comandos do framework:\n"
        "  /help              esta ajuda\n"
        "  /status            estado do hub e settings\n"
        "  /layers            camadas A–D e status\n"
        "  /brief [pedido]    briefing revisável (Camada B)\n"
        "  /chat <texto>      chat LiteLLM (OpenRouter→Ollama)\n"
        "  quit / exit / :q   sair\n"
        "Texto sem / vai para o chat.\n"
        "Skills (Camada C) ainda não executam código — só dry-run futuro.\n"
    )
    return 0


def _cmd_status(app: App, _args: list[str]) -> int:
    s = app.settings
    ready = [i.layer.value for i in app.layers.all() if i.status.value == "ready"]
    app.stdout.write("YBY SEED — status do framework\n")
    app.stdout.write(f"Root: {s.project_root}\n")
    app.stdout.write(f"Data: {s.data_dir}\n")
    app.stdout.write(f"LLM preference: {s.llm_provider_preference}\n")
    app.stdout.write(f"OpenRouter key: {'sim' if s.has_openrouter_key else 'não'}\n")
    app.stdout.write(f"Ollama: {s.ollama_base_url} ({s.ollama_model})\n")
    app.stdout.write(f"Skills mode: {s.skills_mode}\n")
    app.stdout.write(f"Memory: {s.memory_backend}\n")
    app.stdout.write(f"Camadas ready: {', '.join(ready) or '(nenhuma)'}\n")
    app.stdout.write("Não implementado: skills exec, MQTT, API, UI\n")
    return 0


def _cmd_layers(app: App, _args: list[str]) -> int:
    app.stdout.write(app.layers.format_table() + "\n")
    return 0


def _cmd_brief(app: App, args: list[str]) -> int:
    """Delega ao pipeline de briefing (Camada B)."""
    from src.agents.briefing_pipeline import BriefingPipeline
    from src.core.ollama_client import OllamaError

    request = " ".join(args).strip() or None
    pipeline = BriefingPipeline()
    try:
        briefing = pipeline.run_interactive(mode="basic", request=request)
        md_path, json_path = pipeline.export(
            briefing,
            None,
            project_root=app.settings.project_root,
        )
        app.stdout.write(f"Exportado: {md_path}\n")
        app.stdout.write(f"Exportado: {json_path}\n")
        app.stdout.write("Nenhuma execução automática de código.\n")
        return 0
    except ValueError as exc:
        app.stderr.write(f"ERRO {exc}\n")
        return 2
    except OllamaError as exc:
        app.stderr.write(f"ERRO Ollama: {exc}\n")
        return 1
    except Exception as exc:  # noqa: BLE001
        app.stderr.write(f"ERRO briefing: {exc}\n")
        return 1
    finally:
        pipeline.close()


def _cmd_chat(app: App, args: list[str]) -> int:
    from modules.llm_brain import ask_llm, load_llm_config

    text = " ".join(args).strip()
    if not text:
        app.stderr.write("Uso: /chat <texto>\n")
        return 2
    try:
        config = load_llm_config()
        answer = ask_llm(text, config)
    except Exception as exc:  # noqa: BLE001
        app.stderr.write(f"Erro: {exc}\n")
        return 1
    app.stdout.write(answer + "\n")
    return 0
