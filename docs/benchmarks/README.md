# Benchmarks locais (GTX 1650 4 GB)

Origem: repositório `yby-seed-local`, absorvido na Fase 0.

## Resumo

| Modelo | eval rate | prompt eval rate | GPU (approx) |
|---|---|---|---|
| qwen2.5-coder:3b | 48.4 t/s | 176 t/s | 100% |
| qwen2.5:3b | 48.3 t/s | 168 t/s | 100% |
| gemma3:4b | 21.2 t/s | 88 t/s | misto |
| qwen3:4b | 18.0 t/s | 113 t/s | misto |
| llama3.1:8b | 11.5 t/s | 54 t/s | offload |

## Modelo-padrão do hub

`qwen2.5-coder:3b` — melhor velocidade e qualidade para código/RAG nesta GPU.

## Como repetir

```bash
./scripts/benchmark_ollama.sh
```

Resultados brutos: arquivos `*.txt` nesta pasta.
Open WebUI de referência: `open-webui.docker-compose.yml`.
