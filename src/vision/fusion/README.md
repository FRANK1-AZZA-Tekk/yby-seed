# FUSION-X-Phi3.5 — visão computacional (YBY SEED)

Módulo opcional para análise de imagens com o modelo Hugging Face
[`starriver030515/FUSION-X-Phi3.5-3B-Stage1`](https://huggingface.co/starriver030515/FUSION-X-Phi3.5-3B-Stage1),
exposto via API compatível com OpenAI e rota LiteLLM `yby-vision`.

## Requisitos de hardware

| Modo | VRAM | RAM | CUDA |
|------|------|-----|------|
| Quantizado (4/8 bit) | ~8 GB | 16 GB+ | 11.8+ recomendado |
| FP16 | 12–16 GB | 16 GB+ | 11.8+ |

CPU-only não é suportado para uso sério; use quantização em GPU modesta.

## Dependências

```bash
pip install -r requirements-vision.txt
```

`bitsandbytes` é opcional (descomente no arquivo para 4/8 bit).

## Baixar pesos

```bash
huggingface-cli download starriver030515/FUSION-X-Phi3.5-3B-Stage1
```

Ou defina `FUSION_MODEL_PATH` para um diretório local já baixado.

## Variáveis de ambiente

| Variável | Padrão |
|----------|--------|
| `FUSION_MODEL_PATH` | `starriver030515/FUSION-X-Phi3.5-3B-Stage1` |
| `FUSION_DEVICE` | `auto` |
| `FUSION_QUANTIZATION` | `none` (`4bit`, `8bit`) |
| `FUSION_MAX_NEW_TOKENS` | `256` |
| `FUSION_SERVER_HOST` | `127.0.0.1` |
| `FUSION_SERVER_PORT` | `8100` |

## Inferência direta (Python)

```python
from src.vision.fusion import FusionClient, FusionConfig

client = FusionClient(FusionConfig.from_env())
texto = client.analyze("/caminho/foto.jpg", "O que há nesta imagem?")
print(texto)
```

## Servidor FastAPI

```bash
python -m src.vision.fusion.server
```

Exemplo JSON (imagem em base64 no campo `image_url`):

```bash
curl -s http://127.0.0.1:8100/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"yby-vision","messages":[{"role":"user","content":[
    {"type":"text","text":"Descreva a cena."},
    {"type":"image_url","image_url":{"url":"data:image/png;base64,..."}}
  ]}]}'
```

Multipart:

```bash
curl -s http://127.0.0.1:8100/v1/chat/completions \
  -F "prompt=Descreva a imagem." \
  -F "image=@foto.jpg"
```

## LiteLLM

```python
from src.vision.fusion.litellm_adapter import register_fusion_route
import yaml

with open("litellm_config.yaml") as f:
    cfg = yaml.safe_load(f)
cfg = register_fusion_route(cfg)  # adiciona yby-vision em :8100, sem fallback
```

## Limitações

- Respostas em **pt-BR** são solicitadas no prompt, mas **não são garantidas** pelo modelo base.
- Modelo pesado: primeira carga pode demorar vários minutos.
- Timeout padrão do servidor: 120 s por requisição.

## Alternativa mais leve

Se a VRAM for insuficiente, considere **Qwen3-VL-2B** (ou outro VLM 2B) como fallback
manual — não está integrado neste módulo v1.