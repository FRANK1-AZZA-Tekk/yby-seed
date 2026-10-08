# Matriz de Modelos de IA

> **Status:** v1.1.0
> **Última atualização:** 2026-10-08
> **Hardware:** GTX 1650 (4GB VRAM) + 16GB RAM

## 🎯 Restrições de Hardware

| Componente | Especificação | Limite |
|------------|---------------|--------|
| **GPU** | NVIDIA GTX 1650 | 4GB VRAM, compute 7.5 |
| **RAM** | 16GB DDR4 | Dual-channel 3200MHz |
| **CPU** | AMD Ryzen 5 4600G | 6 núcleos, 12 threads |

**Consequência:** Modelos >4GB VRAM exigem **offloading para RAM** (5-20x mais lento).

---

## 📊 Modelos Recomendados por Camada

### **Camada 1: Entrevista / Planejamento / RAG Retrieval**

| Modelo | Tamanho | Quantização | VRAM | Tokens/s | Uso |
|--------|---------|-------------|------|----------|-----|
| **Llama 3.2 3B** | 3B | Q4_K_M | 1.3GB | 28-100 t/s | ✅ **Recomendado** |
| **Gemma 3 4B** | 4B | Q4_K_M | 3.3GB | 20-50 t/s | Alternativa |
| **Phi-3 Mini** | 3.8B | Q4_K_M | 2.1GB | 35-80 t/s | Alternativa |

**Características:**
- Cabem **100% em VRAM** (sem offloading)
- Latência imperceptível (<500ms)
- Ideais para: entrevista, classificação, RAG retrieval, re-ranking

---

### **Camada 2: Geração de Código / Execução**

| Modelo | Tamanho | Quantização | VRAM | Tokens/s | Uso |
|--------|---------|-------------|------|----------|-----|
| **Qwen2.5 7B** | 7B | Q4_K_M | 4.1GB | 21-62 t/s | ✅ **Recomendado** |
| **Llama 3.1 8B** | 8B | Q4_K_M | 5.2GB | 15-45 t/s | Alternativa |
| **Olmo Hybrid 7B** | 7B | Q4_K_M | 4.1GB | 25-55 t/s | ✅ **Mais eficiente** |
| **Mistral 7B** | 7B | Q4_K_M | 4.5GB | 18-50 t/s | Alternativa |

**Características:**
- Exigem **offloading parcial para RAM** (4.1-5.2GB > 4GB VRAM)
- Latência moderada (1-5s)
- Ideais para: geração de código, raciocínio complexo, síntese

---

### **Camada 3: Cloud Fallback (Quando Local Falha)**

| Modelo | Provider | Tokens/s | Custo | Uso |
|--------|----------|----------|-------|-----|
| **GPT-5.4 Thinking** | OpenAI | 50 t/s | $0.002/1K | Raciocínio profundo |
| **Claude 3.5 Sonnet** | Anthropic | 80 t/s | $0.003/1K | Code review |
| **Groq Llama 3.1 70B** | Groq | 500 t/s | $0.0004/1K | Fallback rápido |
| **OpenRouter Mix** | OpenRouter | 100 t/s | $0.0001/1K | Fallback barato |

**Sanitização obrigatória antes de enviar:**

```python
def sanitize(text: str) -> str:
    # Remove nomes próprios
    text = re.sub(r"[A-Z][a-z]+ [A-Z][a-z]+", "[NOME]", text)
    # Remove locais
    text = re.sub(r"(São Paulo|Rio de Janeiro)", "[LOCAL]", text)
    # Remove dados financeiros
    text = re.sub(r"R\$ \d+,\d+", "[VALOR]", text)
    return text
```

---

## 🏆 Campeão: Olmo Hybrid 7B

### **Por que é o melhor para YBY SEED:**

| Característica | Olmo Hybrid 7B | Llama 3.1 8B | Ganho |
|----------------|----------------|--------------|-------|
| **Arquitetura** | 75% DeltaNet + 25% Attention | 100% Attention | -49% tokens |
| **VRAM** | 4.1GB (Q4_K_M) | 5.2GB (Q4_K_M) | -21% |
| **Tokens/s** | 25-55 t/s | 15-45 t/s | +22% |
| **Contexto** | 128K nativo | 8K nativo | +16x |
| **Licença** | Apache 2.0 (aberto) | Llama 3.1 (restrita) | ✅ |

### **Como usar no Ollama:**

```bash
# Baixar Olmo Hybrid 7B
ollama pull olmo-hybrid:7b-q4_k_m

# Configurar no YBY SEED
export DEFAULT_MODEL="olmo-hybrid:7b-q4_k_m"
```

---

## 🔄 Roteamento Dinâmico de Modelos

```python
def route_task(task: str, context_size: int) -> str:
    """
    Decide qual modelo usar baseado na tarefa e tamanho do contexto.
    """
    # Tarefas simples + contexto curto → Modelo 3B (VRAM)
    if context_size < 4096 and task in ["classify", "retrieve", "summarize"]:
        return "llama3.2:3b"
    
    # Geração de código + contexto médio → Modelo 7B (offloading)
    if task in ["generate_code", "reasoning", "synthesize"]:
        return "olmo-hybrid:7b"
    
    # Contexto muito longo (>8K) → Cloud fallback
    if context_size > 8192:
        return "openrouter/mistralai/mixtral-8x7b-instruct"
    
    # Fallback padrão
    return "qwen2.5:7b"
```

---

## 📊 Benchmark GTX 1650 (4GB VRAM)

| Modelo | VRAM | RAM Offload | Tokens/s | Contexto Máx |
|--------|------|-------------|----------|--------------|
| **Llama 3.2 3B** | 1.3GB | 0GB | 28-100 t/s | 8192 |
| **Qwen2.5 7B** | 4.1GB | 1.5GB | 21-62 t/s | 6144 |
| **Olmo Hybrid 7B** | 4.1GB | 1.2GB | 25-55 t/s | 8192 |
| **Llama 3.1 8B** | 5.2GB | 2.8GB | 15-45 t/s | 4096 |

---

## 🔗 Referências

- [Ollama Model Library](https://ollama.ai/library)
- [Olmo Hybrid Paper (Allen Institute)](https://allenai.org/olmo)
- [llama.cpp Benchmarks](https://github.com/ggerganov/llama.cpp/discussions/4922)
- [Groq Cloud Pricing](https://groq.com/pricing/)
