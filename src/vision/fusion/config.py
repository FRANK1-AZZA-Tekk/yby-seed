"""Configuração do modelo FUSION-X para análise de imagens."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import load_dotenv

DEFAULT_MODEL_PATH = "starriver030515/FUSION-X-Phi3.5-3B-Stage1"
DEFAULT_DEVICE = "auto"
DEFAULT_QUANTIZATION = "none"
DEFAULT_MAX_NEW_TOKENS = 256
DEFAULT_LANGUAGE = "pt-BR"


def _text(source: Mapping[str, str], name: str, default: str) -> str:
    raw = source.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip()


def _int(source: Mapping[str, str], name: str, default: int) -> int:
    raw = source.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    return int(str(raw).strip())


@dataclass(frozen=True)
class FusionConfig:
    """Parâmetros de inferência FUSION. Sem segredos embutidos."""

    model_path: str
    device: str
    quantization: str
    max_new_tokens: int
    language: str = DEFAULT_LANGUAGE

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> FusionConfig:
        if environ is None:
            load_dotenv(override=False)
            source: Mapping[str, str] = os.environ
        else:
            source = environ

        max_tokens = _int(source, "FUSION_MAX_NEW_TOKENS", DEFAULT_MAX_NEW_TOKENS)
        if max_tokens < 1:
            raise ValueError("FUSION_MAX_NEW_TOKENS deve ser >= 1.")

        quantization = _text(source, "FUSION_QUANTIZATION", DEFAULT_QUANTIZATION).lower()
        if quantization not in {"none", "4bit", "8bit"}:
            raise ValueError("FUSION_QUANTIZATION deve ser none, 4bit ou 8bit.")

        return cls(
            model_path=_text(source, "FUSION_MODEL_PATH", DEFAULT_MODEL_PATH),
            device=_text(source, "FUSION_DEVICE", DEFAULT_DEVICE),
            quantization=quantization,
            max_new_tokens=max_tokens,
            language=DEFAULT_LANGUAGE,
        )