# Especificações de Hardware - YBY SEED MVP

## PC Desktop (Núcleo de Inferência)

### Hardware Confirmado

| Componente | Especificação | Impacto no YBY SEED |
|---|---|---|
| **CPU** | AMD Ryzen 5 4600G (6 cores, 12 threads, 3.7-4.2GHz) | Inferência CPU para modelos 7B+ |
| **RAM** | 16GB DDR4 (3000-3200MHz, dual-channel) | Limite: não usar ChromaDB/Weaviate (2-4GB RAM) |
| **GPU** | NVIDIA GTX 1650 (4GB VRAM, compute 7.5) | **Restrição crítica**: modelos 3B cabem, 7B+ causam offloading |
| **Storage** | 1TB SSD NVMe | Suficiente para SQLite + logs + áudios |
| **OS** | Ubuntu 26.04 LTS | Docker, Ollama, Node-RED nativos |

### Limites de VRAM (GTX 1650 4GB)

| Modelo | Quantização | VRAM Necessária | Cabe na GTX 1650? |
|---|---|---|---|
| **Llama 3.2 3B** | Q4_K_M | ~2.5GB | ✅ 100% em VRAM |
| **Qwen2.5-Coder 3B** | Q4_K_M | ~2.5GB | ✅ 100% em VRAM |
| **Qwen2.5-Coder 7B** | Q4_K_M | ~4.5GB | ⚠️ Offloading parcial para RAM |
| **Llama 3.1 8B** | Q4_K_M | ~5.2GB | ❌ Offloading pesado |

### Estratégias de Otimização

1. **KV Cache Quantizado (Q8_0):** Reduz contexto pela metade (8KB → 4KB por token)
2. **Flash Attention:** Elimina crescimento quadrático de memória no prefill
3. **Roteamento Híbrido:**
   - Modelos 3B (entrevista, RAG) → 100% VRAM, 28-100 t/s
   - Modelos 7B (codificação) → Offloading parcial, 21-62 t/s

### Contexto Máximo por Modelo

```bash
# Llama 3.2 3B (Q4_K_M) na GTX 1650:
- Contexto máximo: 8192 tokens (KV cache Q8_0 + Flash Attention)
- VRAM usada: ~3.8GB (modelo + cache)

# Qwen2.5-Coder 7B (Q4_K_M) na GTX 1650:
- Contexto máximo: 4096 tokens (offloading para RAM)
- VRAM usada: ~4GB (saturado)
- RAM usada: ~2GB (offloading)
```

---

## Próximos Passos

1. ✅ Instalar Ollama + modelos 3B (Llama 3.2, Qwen2.5-Coder 3B)
2. ✅ Configurar KV cache Q8_0 + Flash Attention
3. ✅ Testar modelos 7B com offloading controlado
4. ✅ Implementar roteamento automático baseado na tarefa

**Princípio:** _Function Over Form_ 🚀
