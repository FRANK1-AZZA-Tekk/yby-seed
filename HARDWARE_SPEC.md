# Especificações de Hardware - YBY SEED MVP

> **Atualização (2026-11):** dois perfis na mesma GTX 1650 4 GB — CLI `ask` usa **3B**; stack LiteLLM/`yby_seed` usa **7B Q3_K_M** com `num_ctx: 4096` e `gpu_gate` (um modelo por vez). Ver D4 e D12 em [DECISIONS.md](DECISIONS.md).

## PC Desktop (Núcleo de Inferência)

### Hardware Confirmado

| Componente | Especificação | Impacto no YBY SEED |
|---|---|---|
| **CPU** | AMD Ryzen 5 4600G (6 cores, 12 threads, 3.7-4.2GHz) | Inferência do modelo 3B |
| **RAM** | 16GB DDR4 (3000-3200MHz, dual-channel) | Limite: não usar ChromaDB/Weaviate (2-4GB RAM) |
| **GPU** | NVIDIA GTX 1650 (4GB VRAM, compute 7.5) | **Restrição crítica**: modelos 3B cabem, 7B+ causam offloading |
| **Storage** | 1TB SSD NVMe | Suficiente para SQLite + logs + áudios |
| **OS** | Ubuntu 26.04 LTS | Docker, Ollama, Node-RED nativos |

### Limites de VRAM (GTX 1650 4GB)

| Modelo | Quantização | VRAM Necessária | Cabe na GTX 1650? |
|---|---|---|---|
| **Qwen2.5-Coder 3B** | Q4_K_M | ~2.5GB | Sim — CLI `yby ask` |
| **Qwen2.5-Coder 7B** | Q3_K_M | ~3.5GB | Sim — alias `yby-local` (Docker / Vibe Coding) |

### Estratégias de Otimização

1. **KV Cache Quantizado (Q8_0):** Reduz contexto pela metade (8KB → 4KB por token)
2. **Flash Attention:** Elimina crescimento quadrático de memória no prefill
3. **Um modelo por vez:** `qwen2.5-coder:3b` na VRAM

### Contexto

```bash
# Qwen2.5-Coder 3B na GTX 1650:
ollama pull qwen2.5-coder:3b
```

---

## Próximos Passos

1. Instalar Ollama e puxar `qwen2.5-coder:3b`
2. Configurar KV cache Q8_0 + Flash Attention
3. Não puxar modelos 7B nesta GPU

**Princípio:** _Function Over Form_ 🚀
