"""Testes do cliente FUSION com mocks (sem pesos Hugging Face)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.vision.fusion.client import FusionClient
from src.vision.fusion.config import FusionConfig
from src.vision.fusion.litellm_adapter import (
    DEFAULT_VISION_PORT,
    VISION_MODEL_NAME,
    register_fusion_route,
)


def test_fusion_config_from_env_defaults() -> None:
    cfg = FusionConfig.from_env(
        {
            "FUSION_MODEL_PATH": "",
            "FUSION_DEVICE": "",
            "FUSION_QUANTIZATION": "",
            "FUSION_MAX_NEW_TOKENS": "",
        }
    )
    assert cfg.model_path == "starriver030515/FUSION-X-Phi3.5-3B-Stage1"
    assert cfg.device == "auto"
    assert cfg.quantization == "none"
    assert cfg.max_new_tokens == 256
    assert cfg.language == "pt-BR"


def test_fusion_config_from_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("FUSION_MODEL_PATH", "/models/fusion-local")
    monkeypatch.setenv("FUSION_DEVICE", "cuda:0")
    monkeypatch.setenv("FUSION_QUANTIZATION", "4bit")
    monkeypatch.setenv("FUSION_MAX_NEW_TOKENS", "128")
    cfg = FusionConfig.from_env()
    assert cfg.model_path == "/models/fusion-local"
    assert cfg.device == "cuda:0"
    assert cfg.quantization == "4bit"
    assert cfg.max_new_tokens == 128


def test_fusion_config_invalid_quantization() -> None:
    with pytest.raises(ValueError, match="FUSION_QUANTIZATION"):
        FusionConfig.from_env({"FUSION_QUANTIZATION": "fp32"})


class _FakeProcessor:
    def __call__(self, text: str, images: object, return_tensors: str) -> dict[str, MagicMock]:
        assert return_tensors == "pt"
        assert "Descreva" in text
        return {"input_ids": MagicMock()}

    def batch_decode(self, tokens: object, skip_special_tokens: bool) -> list[str]:
        assert skip_special_tokens is True
        return ["Um gato em cima do sofá."]


class _FakeModel:
    def __init__(self) -> None:
        self._device = MagicMock()
        self.generate = MagicMock(return_value=MagicMock())

    def parameters(self):
        yield MagicMock(device=self._device)


def test_fusion_client_analyze_with_mocks(tmp_path: Path) -> None:
    image = tmp_path / "foto.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")  # cabeçalho mínimo; PIL pode falhar sem PNG real

    # PIL precisa de imagem válida — gerar PNG 1x1
    try:
        from PIL import Image

        img = Image.new("RGB", (1, 1), color=(255, 0, 0))
        img.save(image)
    except ImportError:
        pytest.skip("Pillow não instalado")

    processor = _FakeProcessor()
    model = _FakeModel()
    cfg = FusionConfig(
        model_path="fake/model",
        device="cpu",
        quantization="none",
        max_new_tokens=64,
    )
    client = FusionClient(cfg, processor=processor, model=model, eager_load=False)
    result = client.analyze(image, "Descreva a imagem.")
    assert "gato" in result.lower()
    model.generate.assert_called_once()


def test_register_fusion_route_adds_entry() -> None:
    base = {
        "model_list": [{"model_name": "yby-local", "litellm_params": {"model": "ollama/x"}}],
        "router_settings": {"fallbacks": [{"yby-free": ["yby-local"]}]},
    }
    updated = register_fusion_route(base, port=DEFAULT_VISION_PORT)
    names = [m["model_name"] for m in updated["model_list"]]
    assert VISION_MODEL_NAME in names
    vision = next(m for m in updated["model_list"] if m["model_name"] == VISION_MODEL_NAME)
    assert vision["litellm_params"]["api_base"] == f"http://127.0.0.1:{DEFAULT_VISION_PORT}/v1"
    # fallbacks inalterados
    assert updated["router_settings"] == base["router_settings"]
    assert base["model_list"] == [{"model_name": "yby-local", "litellm_params": {"model": "ollama/x"}}]


def test_register_fusion_route_replaces_existing() -> None:
    cfg = {
        "model_list": [
            {
                "model_name": VISION_MODEL_NAME,
                "litellm_params": {"api_base": "http://old:9999/v1"},
            }
        ]
    }
    updated = register_fusion_route(cfg, host="10.0.0.2", port=8200)
    assert len(updated["model_list"]) == 1
    assert updated["model_list"][0]["litellm_params"]["api_base"] == "http://10.0.0.2:8200/v1"