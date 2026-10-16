# Scripts

## Benchmark

```bash
chmod +x bench.sh
./bench.sh qwen3:4b 4096 3
```

O script não baixa modelos. Execute antes:

```bash
ollama pull qwen3:4b
```

Resultados ficam em `data/bench/`.

## Testes

```bash
python -m pytest tests/test_gatekeeper.py tests/test_budget_policy.py
```

Os testes do Gatekeeper e do orçamento não exigem Ollama, rede ou GPU.
