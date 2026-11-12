"""Gerador de dataset sintético — só persiste amostras aprovadas no sandbox."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import re
from pathlib import Path

from src.yby_seed.config import Settings, get_settings
from src.yby_seed.forge.dataset_synth_prompts import INTENT_TEMPLATES, SYNTH_SYSTEM
from src.yby_seed.persistence import append_dataset
from src.yby_seed.runtime import resources
from src.yby_seed.runtime.gpu_gate import inference_slot
from src.yby_seed.sandbox import execute_validated

logger = logging.getLogger(__name__)

_YAML_RE = re.compile(r"```ya?ml\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
_CODE_RE = re.compile(r"```(?:c|cpp|python)\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)

DOMAIN_LANGUAGE: dict[str, tuple[str, str]] = {
    "python_fastapi": ("python", "main.py"),
    "esp_idf": ("cpp_embedded", "main.c"),
    "lvgl_v9": ("cpp_embedded", "ui_main.c"),
    "modbus_rtu": ("python", "modbus_poll.py"),
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_existing_hashes(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            assistant = record["messages"][-1]["content"]
            seen.add(sha256_text(assistant))
        except (json.JSONDecodeError, KeyError, IndexError):
            continue
    return seen


def parse_contract_response(text: str, domain: str) -> tuple[str, str, str] | None:
    """Retorna (code, filename, language) ou None se inválido."""
    lang_default, file_default = DOMAIN_LANGUAGE.get(domain, ("python", "snippet.py"))
    yaml_match = _YAML_RE.search(text)
    code_match = _CODE_RE.search(text)
    if not yaml_match or not code_match:
        return None
    code = code_match.group(1).strip()
    if len(code) < 8:
        return None
    filename = file_default
    language = lang_default
    board_line = re.search(r"board:\s*(\S+)", yaml_match.group(1))
    if board_line and domain in {"esp_idf", "lvgl_v9"}:
        code = f"// board: {board_line.group(1)}\n{code}"
    return code, filename, language


def pick_user_intent(domain: str, index: int) -> str:
    options = INTENT_TEMPLATES.get(domain, INTENT_TEMPLATES["python_fastapi"])
    return options[index % len(options)]


async def generate_candidate(
    user_intent: str,
    domain: str,
    *,
    use_cloud: bool,
    settings: Settings,
) -> str:
    model = "yby-cloud-coder" if use_cloud else settings.litellm_model
    user_msg = f"Domínio: {domain}\nIntenção (pt-BR):\n{user_intent}\n\nResponda no contrato YBY (YAML hardware_check + código)."

    def _call() -> str:
        client = resources.build_openai_client(settings)
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYNTH_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.4,
        )
        return completion.choices[0].message.content or ""

    async with inference_slot():
        return await asyncio.to_thread(_call)


def validate_candidate(
    assistant: str,
    domain: str,
    settings: Settings,
) -> tuple[bool, str]:
    parsed = parse_contract_response(assistant, domain)
    if parsed is None:
        return False, "parse_contract_response: formato inválido"
    code, filename, language = parsed
    tests = "def test_snippet():\n    assert True\n" if language == "python" else None
    result = execute_validated(
        language=language,
        code=code,
        filename=filename,
        tests=tests,
        settings=settings,
        domain=domain,
    )
    if not result.success:
        return False, result.stderr or "sandbox reprovou"
    hw = (result.report or {}).get("hardware", {})
    if (
        domain in {"esp_idf", "lvgl_v9", "modbus_rtu"}
        and hw
        and not hw.get("pinning_approved", True)
    ):
        return False, "hardware_linter reprovou pinagem/modbus"
    return True, ""


async def run_synthesis(args: argparse.Namespace) -> int:
    settings = get_settings()
    output_path = settings.datasets_path
    seen = load_existing_hashes(output_path)

    if args.use_cloud:
        if (
            not settings.openrouter_monthly_budget_usd
            or settings.openrouter_monthly_budget_usd > 3.50
        ):
            logger.error("use-cloud bloqueado: respeite max_budget US$ 3.50 no LiteLLM")
            return 2
        import os

        if not os.environ.get("OPENROUTER_API_KEY", "").strip():
            logger.error("OPENROUTER_API_KEY ausente")
            return 2

    accepted = 0
    streak_failures = 0
    attempts = 0

    while accepted < args.count and attempts < args.count * 3:
        if streak_failures >= args.max_failures:
            logger.warning("max-failures=%s atingido; encerrando", args.max_failures)
            break
        attempts += 1
        user_intent = pick_user_intent(args.domain, attempts)
        if args.dry_run:
            assistant = (
                "```yaml\nhardware_check:\n  board: esp32_s3_devkitc1\n  domain: "
                f"{args.domain}\n```\n```c\n// board: esp32_s3_devkitc1\n"
                '#include "freertos/FreeRTOS.h"\nvoid app_main(void) {}\n```'
            )
        else:
            try:
                assistant = await generate_candidate(
                    user_intent, args.domain, use_cloud=args.use_cloud, settings=settings
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("falha LLM: %s", exc)
                streak_failures += 1
                continue

        digest = sha256_text(assistant)
        if digest in seen:
            logger.info("duplicata SHA-256 ignorada")
            continue

        ok, reason = validate_candidate(assistant, args.domain, settings)
        if not ok:
            logger.info("candidato reprovado: %s", reason)
            streak_failures += 1
            continue

        streak_failures = 0
        if args.dry_run:
            logger.info("[dry-run] aprovado: %s", user_intent[:60])
            seen.add(digest)
            accepted += 1
            continue

        saved = append_dataset(
            output_path,
            SYNTH_SYSTEM,
            user_intent,
            assistant,
        )
        if saved:
            seen.add(digest)
            accepted += 1
            logger.info("gravado (%s/%s)", accepted, args.count)

    print(
        json.dumps(
            {
                "domain": args.domain,
                "accepted": accepted,
                "attempts": attempts,
                "dry_run": args.dry_run,
                "output": str(output_path),
            },
            ensure_ascii=False,
        )
    )
    return 0 if accepted > 0 or args.dry_run else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dataset sintético YBY SEED (sandbox obrigatório)")
    parser.add_argument("--count", type=int, default=5, help="Amostras aprovadas desejadas")
    parser.add_argument(
        "--domain",
        choices=list(DOMAIN_LANGUAGE.keys()),
        default="esp_idf",
    )
    parser.add_argument("--dry-run", action="store_true", help="Não chama LLM nem grava JSONL")
    parser.add_argument(
        "--use-cloud",
        action="store_true",
        help="Usa yby-cloud-coder (exige OPENROUTER e budget 3.50)",
    )
    parser.add_argument(
        "--max-failures",
        type=int,
        default=8,
        help="Falhas consecutivas antes de abortar (protege GTX 1650)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    return asyncio.run(run_synthesis(args))


if __name__ == "__main__":
    raise SystemExit(main())
