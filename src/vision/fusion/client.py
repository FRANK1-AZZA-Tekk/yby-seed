"""Cliente de inferência FUSION-X-Phi3.5 (Context-Aware Recursive Alignment Decoding)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.vision.fusion.config import FusionConfig

logger = logging.getLogger(__name__)


class FusionClient:
    """
    Carrega o modelo FUSION uma vez e analisa imagens com prompt em pt-BR.

    O FUSION usa **Context-Aware Recursive Alignment Decoding** para alinhar
    contexto visual e textual antes da geração.
    """

    def __init__(
        self,
        config: FusionConfig,
        *,
        processor: Any | None = None,
        model: Any | None = None,
        eager_load: bool = True,
    ) -> None:
        self._config = config
        self._processor = processor
        self._model = model
        self._loaded = processor is not None and model is not None
        if eager_load and not self._loaded:
            self._load_model()

    @property
    def config(self) -> FusionConfig:
        return self._config

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self._load_model()

    def _load_model(self) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoProcessor

        quantization = self._config.quantization
        model_kwargs: dict[str, Any] = {"trust_remote_code": True}
        if quantization in ("4bit", "8bit"):
            from transformers import BitsAndBytesConfig

            if quantization == "4bit":
                model_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True)
            else:
                model_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)

        device = self._config.device
        if device != "auto":
            model_kwargs["torch_dtype"] = torch.float16 if device.startswith("cuda") else torch.float32

        logger.info("Carregando FUSION: %s", self._config.model_path)
        self._processor = AutoProcessor.from_pretrained(
            self._config.model_path,
            trust_remote_code=True,
        )
        self._model = AutoModelForCausalLM.from_pretrained(
            self._config.model_path,
            **model_kwargs,
        )
        if device != "auto" and quantization == "none":
            self._model = self._model.to(device)
        self._loaded = True

    def analyze(self, image_path: str | Path, prompt: str) -> str:
        """
        Analisa uma imagem com o prompt dado. Resposta em texto (idealmente pt-BR).

        Args:
            image_path: Caminho local para a imagem.
            prompt: Instrução ou pergunta sobre a imagem (use pt-BR quando possível).
        """
        self._ensure_loaded()
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(f"Imagem não encontrada: {path}")

        from PIL import Image

        image = Image.open(path).convert("RGB")
        language_hint = (
            f"\nResponda em {self._config.language}."
            if self._config.language
            else ""
        )
        full_prompt = f"{prompt.strip()}{language_hint}"

        inputs = self._processor(
            text=full_prompt,
            images=image,
            return_tensors="pt",
        )
        device = next(self._model.parameters()).device
        inputs = {key: value.to(device) for key, value in inputs.items()}

        generated = self._model.generate(
            **inputs,
            max_new_tokens=self._config.max_new_tokens,
            do_sample=False,
        )
        text = self._processor.batch_decode(generated, skip_special_tokens=True)[0]
        return text.strip()