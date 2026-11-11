# Especificações de Hardware - YBY SEED MVP

> Decisão D4 (2026-11-11): o único modelo local é `qwen2.5-coder:3b`. Modelos 7B não cabem na GTX 1650 e saíram do v1.

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
| **Qwen2.5-Coder 3B** | Q4_K_M | ~2.5GB | Sim. É o único modelo local do v1 |

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
