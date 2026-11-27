"""Parser de JSON para saídas do AirLLM.

O AirLLM não suporta `response_format` (json_object/json_schema), então este
módulo extrai e valida JSON de texto livre, com retry opcional.
"""
import json
import re
import logging
from typing import Any, Callable

logger = logging.getLogger("yby.airllm.parser")


def extract_json(text: str) -> str | None:
    """Extrai o primeiro bloco JSON válido de um texto livre."""
    # Tenta JSON puro
    try:
        json.loads(text)
        return text
    except (json.JSONDecodeError, ValueError):
        pass
    # Tenta bloco em markdown ```json ... ```
    match = re.search(r"```json\s*([\s\S]*?)```", text)
    if match:
        candidate = match.group(1).strip()
        try:
            json.loads(candidate)
            return candidate
        except (json.JSONDecodeError, ValueError):
            pass
    # Tenta primeiro objeto/array balanceado
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start == -1:
            continue
        depth = 0
        for i in range(start, len(text)):
            if text[i] == opener:
                depth += 1
            elif text[i] == closer:
                depth -= 1
                if depth == 0:
                    candidate = text[start:i+1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except (json.JSONDecodeError, ValueError):
                        break
    return None


def parse_json(
    text: str,
    schema: dict | None = None,
    retry_fn: Callable[[], str] | None = None,
    max_retries: int = 2,
) -> Any:
    """Extrai e valida JSON de uma saída do AirLLM.

    Args:
        text: saída bruta do modelo (texto livre).
        schema: dicionário opcional com chaves obrigatórias para validar.
        retry_fn: função que gera nova saída do modelo em caso de falha.
        max_retries: número máximo de tentativas extras.

    Returns:
        Objeto Python (dict ou list) validado.

    Raises:
        ValueError: se não conseguir extrair/validar JSON após todas as tentativas.
    """
    attempts = [text]
    for _ in range(max_retries):
        if retry_fn:
            attempts.append(retry_fn())
    last_error = None
    for attempt in attempts:
        raw = extract_json(attempt)
        if raw is None:
            last_error = "Nenhum JSON válido encontrado"
            continue
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = str(exc)
            continue
        if schema:
            missing = [k for k in schema.get("required", []) if k not in obj]
            if missing:
                last_error = f"Campos obrigatórios ausentes: {missing}"
                continue
        return obj
    raise ValueError(f"Falha ao parsear JSON do AirLLM: {last_error}")
