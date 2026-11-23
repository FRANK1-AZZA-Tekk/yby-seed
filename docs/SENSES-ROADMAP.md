# Roadmap de sentidos — exocórtex YBY (scan pós-visão)

**Tipo:** mapeamento e recomendação — **sem implementação**.  
**Contexto:** visão integrada (D14, `src/vision/fusion/`, rota LiteLLM `yby-vision`).  
**Hardware de referência:** PC Hub (D9) — Ryzen 5, 16 GB RAM, **GTX 1650 4 GB** (D4).  
**Última revisão:** 2026-11-23.

## Objetivo

Priorizar os próximos “sentidos” do exocórtex YBY depois da visão, com foco em valor prático, custo em VRAM/RAM, encaixe na stack atual (Ollama, LiteLLM, Mem0/Supabase, LangGraph, voz local) e privacidade local-first (D3).

### Stack já disponível (núcleo v1)

| Camada | Componentes | Notas |
| :--- | :--- | :--- |
| Linguagem | Ollama `qwen2.5-coder:3b`, LiteLLM, roteamento `src/engine` | D4 — único LLM local 3B no v1 |
| Voz | faster-whisper + Piper (`requirements-voice.txt`, D11) | Sob demanda (`listen`, `ask --voice`), não always-on |
| Visão | FUSION-3B 4-bit / plano B Qwen3-VL-2B (D14) | VRAM dominante; não compartilhar GPU com outros modelos grandes |
| Memória | Vault Markdown + índice (`src/memory`), Mem0 + Supabase | Eventos de sensor podem virar notas/recall |
| Plataforma | Hub systemd (`src/platform.hub`), D9 | MQTT **não** sobe com o hub hoje |
| Segurança | `src/safety` / D10 | Automações e atuadores exigem confirmação |

---

## Inventário de sentidos mapeados

### 1. Áudio ambiente (mic always-on, wake word, detecção de sons)

- **O quê:** VAD contínuo, wake word local (“YBY”), opcional classificação de eventos (campainha, vidro, choro).
- **Valor:** acessibilidade, mãos livres, alertas de segurança sem olhar para a tela.
- **VRAM:** ~0 (wake word + VAD em CPU; STT só após gatilho, reusa D11).
- **Privacidade:** **alta tensão** — microfone sempre ligado; mitigar com indicador visual, retenção zero de áudio bruto, opt-in explícito.

### 2. Gestos (câmera + MediaPipe)

- **O quê:** mãos/pose para comandos discretos (confirmar, cancelar, volume, “captura e descreve”).
- **Valor:** acessibilidade e produtividade quando teclado/mouse estão ocupados.
- **VRAM:** ~0 (MediaPipe em CPU/GPU leve integrada).
- **Privacidade:** câmera ativa; mesmas salvaguardas que visão (LED, zona morta, não gravar por padrão).

### 3. Sensores IoT (MQTT)

- **O quê:** presença, temperatura, portas/janelas, luminosidade, botões físicos; broker local (Mosquitto / Zigbee2MQTT → MQTT).
- **Valor:** contexto doméstico para o agente (“está quente?”, “porta aberta?”, rotinas).
- **VRAM:** 0.
- **Privacidade:** excelente se broker só em LAN; não enviar leituras à nuvem por padrão.

### 4. Outros sentidos relevantes

| Sentido | Valor | VRAM / RAM | Complexidade | Privacidade | Nota |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Eventos do SO** (foco de janela, notificações, idle) | Produtividade | 0 / baixo | Baixa | Alta (só local) | Complementa IoT sem hardware extra |
| **Presença** (mmWave / PIR → MQTT ou BLE) | Automação + segurança | 0 | Baixa–média | Alta | Frequently bundled com IoT |
| **Classificação de som** (YAMNet / ONNX CPU) | Segurança, acessibilidade | 0 | Média | Média–alta | Pode ser fase 1b do áudio ambiente |
| **OCR / tela** (mss + Tesseract / docling leve) | Produtividade | 0 | Média | Alta | Não compete com FUSION se for texto puro |
| **Biometria** (FC, SpO2, wearable) | Saúde | Fora do PC Hub v1 (D1) | Alta | Alta | Histórico em `docs/HYBRID_ARCHITECTURE.md`; mobile fora do v1 |
| **Toque / haptics** | Wearable | Fora do v1 (D1) | Alta | Alta | ESP32/mobile arquivados na árvore |
| **Teclado global / hotkey** | Controle rápido | 0 | Baixa | Alta | “Sentido” mínimo; bom quick win isolado |

---

## Tabela comparativa (resumo acionável)

Escala: **Valor** e **Privacidade** (1–5, maior melhor) · **Custo GPU** (0 = só CPU) · **Complexidade** (1 baixa – 5 alta) · **Integração** (1 difícil – 5 encaixa na stack).

| Sentido | Valor | Custo GPU | Complexidade | Privacidade | Integração stack | Veredicto v1 (GTX 1650 4 GB) |
| :--- | ---: | ---: | ---: | ---: | ---: | :--- |
| **IoT (MQTT)** | 5 | 0 | 3 | 5 | 4 | **Recomendado — #1** |
| **Áudio ambiente (wake + VAD)** | 4 | 0 | 3 | 3 | 5 | **Recomendado — #2** |
| **Gestos (MediaPipe)** | 3 | 0 | 3 | 3 | 4 | **Recomendado — #3** |
| Classificação de sons | 3 | 0 | 3 | 3 | 4 | Fase 1b após wake word |
| Eventos do SO | 4 | 0 | 2 | 4 | 3 | Paralelo ou antes de gestos |
| OCR / captura de tela | 3 | 0 | 3 | 4 | 3 | Depois de IoT; evita VRAM |
| Presença (hardware) | 4 | 0 | 2 | 5 | 4 | Subconjunto de IoT |
| Biometria / toque wearable | 3 | — | 5 | 4 | 1 | **Fora do v1** (D1) |
| Visão contínua (stream) | 3 | **4–5** | 4 | 2 | 5 | Só sob demanda (D14); não always-on |

**Regra de ouro de VRAM (D4, D12, D14):** no PC Hub 4 GB, tratar **FUSION / VLM como recurso exclusivo** — carregar sob demanda, liberar após `analyze`, ou usar **Qwen3-VL-2B** em Ollama (~2–3 GB Q4) se precisar alternar com outras cargas. Nenhum novo sentido no top 3 deve exigir segundo modelo na GPU.

---

## Ordem de integração recomendada (top 3)

### Por que esta ordem

1. **IoT primeiro** — maior ganho de “consciência situacional” com **custo zero de VRAM**, alinhado ao servidor doméstico (D9), alimenta Mem0/LangGraph e não compete com FUSION.
2. **Áudio ambiente em seguida** — estende D11 (já existe pipeline STT/TTS) com wake word + VAD em CPU; transforma o Hub em interface mãos livres sem novo modelo 3B.
3. **Gestos depois** — reutiliza webcam e padrões de privacidade da visão (D14), mas valor diário menor que contexto doméstico + voz para o perfil PC-first (D1).

```
[ Próximo v1 ]  IoT (MQTT)  →  Áudio (wake/VAD)  →  Gestos (MediaPipe)
                     ↓                ↓                      ↓
              Mem0 / vault      src/voice           mesma câmera que visão
              LangGraph         LiteLLM ask         comandos + safety (D10)
```

---

## Detalhamento — top 3

### 1. Sensores IoT (MQTT)

| Item | Detalhe |
| :--- | :--- |
| **Caso de uso YBY** | “Se a porta da sala abrir depois das 23h, anote no vault e me avise.” / “Qual a temperatura do quarto?” / contexto para `ask` e automações LangGraph com dry-run (D6, D10). |
| **Hardware mínimo** | PC Hub na LAN; broker MQTT local (Mosquitto em Docker **opcional**, fora do núcleo D5); 1–3 sensores (PIR presença, contact sensor porta, DHT22 ou equivalente via ESPHome/Zigbee2MQTT). |
| **Dependências** | `paho-mqtt` ou cliente asyncio; tópicos convenção `yby/sensor/{room}/{metric}`; opcional Node-RED só se o usuário já usa (evitar obrigatoriedade). **Não** acoplar ao `yby-hub` até decisão de produto (D9 hoje só checa Ollama). |
| **Esforço** | **M** — ingestão + normalização + escrita em Mem0/vault; atuadores passam por `src/safety`. |
| **Riscos** | Broker sem auth na LAN (mitigar VLAN/senha); comandos perigosos ligados a atuadores (D10); duplicar legado `src/gateway` sem critério — preferir módulo novo `src/senses/iot/` quando implementar (futuro). |

**Alinhamento:** **D1** (PC Hub) · **D3** (broker local) · **D4** (sem modelo extra) · **D9** (servidor casa) · **D11** (alertas podem usar Piper) · **D12** (zero tokens) · **D14** (independente da GPU).

---

### 2. Áudio ambiente (wake word + VAD)

| Item | Detalhe |
| :--- | :--- |
| **Caso de uso YBY** | Wake word “YBY” → ativa o mesmo fluxo de `yby listen` (transcrição + `HybridEngine` + Piper). VAD evita gravar silêncio. Opcional: evento sonoro dispara nota no vault sem gravar conversa. |
| **Hardware mínimo** | Microfone USB ou headset no PC Hub; CPU-only para wake (ex.: openWakeWord / Porcupine **só se licença local permitir** — preferir OSS). |
| **Dependências** | `webrtcvad` ou Silero VAD; wake word OSS; integração com `src/voice`; fila de áudio anelar; `requirements-voice.txt` estendido ou `requirements-audio-ambient.txt` futuro. LiteLLM inalterado até haver texto. |
| **Esforço** | **M** — sempre-on exige systemd user unit separada, opt-in, e UX de privacidade. |
| **Riscos** | Falsos positivos de wake; gravação acidental (mitigar: limite de duração, LED, comando “parar escuta”); competição por CPU com Whisper `small` (manter `base`/`int8` D11). |

**Alinhamento:** **D1** · **D3** (sem enviar áudio à nuvem) · **D4** · **D9** (daemon leve no Hub) · **D11** (reusa STT/TTS) · **D12** · **D14** (sem VRAM).

---

### 3. Gestos (MediaPipe)

| Item | Detalhe |
| :--- | :--- |
| **Caso de uso YBY** | Gesto “OK” confirma `ask` destrutivo (D10); “mão aberta” cancela; “pinça” captura frame e chama `yby-vision` com prompt pt-BR; gestos como atalhos sem falar. |
| **Hardware mínimo** | Webcam 720p USB (compartilhada com visão); iluminação adequada. |
| **Dependências** | `mediapipe` (Hands ou Gesture Recognizer); OpenCV para captura; mutex de câmera com `FusionClient` (não analisar gesto e FUSION ao mesmo tempo). |
| **Esforço** | **L** — calibração por usuário, falsos positivos, UX; menor prioridade que IoT/áudio. |
| **Riscos** | Privacidade da câmera always-on; conflito de dispositivo de vídeo com servidor FUSION; diversidade de pele/iluminação (testar antes de productizar). |

**Alinhamento:** **D1** · **D3** · **D4** (CPU) · **D9** · **D11** opcional (gesto + TTS de confirmação) · **D12** · **D14** (orquestrar fila: gesto → snapshot → `analyze` sob demanda).

---

## Sentidos adiados ou condicionais

| Sentido | Motivo do adiamento |
| :--- | :--- |
| Biometria / toque (wearable) | **D1** — mobile/ESP32 fora do v1 |
| Visão contínua / vigilância | VRAM e privacidade; manter visão **on-demand** (D14) |
| Modelos multimodais extra na GPU | Violam **D4** / **D12** no hardware 4 GB |
| STT always-on completo (sem wake) | Custo CPU e privacidade; inferior a wake + D11 |

**Quick win opcional (não conta no top 3):** hotkey global no PC Hub para abrir `listen` — esforço **S**, valor **médio-alto**, zero VRAM.

---

## Alinhamento com decisões vigentes

| Decisão | Implicação para o roadmap de sentidos |
| :--- | :--- |
| **D1 — PC-first** | Sentidos implementados no **PC Hub**; wearables ficam como fonte MQTT futura, não como runtime v1. |
| **D3 — Local-first** | Brokers, wake word, MediaPipe, MQTT e logs só em LAN; nuvem não processa áudio/vídeo/sensor por padrão. |
| **D4 — Modelo local 3B** | Novos sentidos **não** adicionam LLM/VLM na GPU; contexto sensorial vai como texto para `qwen2.5-coder:3b`. |
| **D9 — Servidor doméstico** | Daemons leves (MQTT subscriber, wake listener) como units systemd **separadas** do `yby-hub`; documentar em `docs/PLATFORM.md` quando existir código. |
| **D11 — Voz local** | Áudio ambiente **estende** o pipeline existente; não substituir faster-whisper/Piper. |
| **D12 — Economia** | Priorizar CPU e regras determinísticas; evitar chamadas OpenRouter só por eventos de sensor. |
| **D14 — Visão FUSION-3B** | Gestos e snapshots devem **serializar** uso de câmera e GPU; plano B Qwen3-VL-2B se precisar de VLM frequente com menos VRAM. |

---

## Próximos passos (somente planejamento)

1. Validar inventário de dispositivos MQTT que o usuário já possui (ou ESPHome).
2. Definir convenção de tópicos e schema JSON para eventos (`docs/` ou ADR futuro — **não** `DECISIONS.md` sem aprovação D15+).
3. Prototipar ingestão IoT → nota no vault (`yby note`) antes de LangGraph.
4. PoC wake word + VAD em CPU com opt-in e teste de falsos positivos 24h.
5. PoC gestos com captura única encadeada a `yby-vision` (medir latência e conflito de VRAM).

---

## Referências no repositório

- [DECISIONS.md](../DECISIONS.md) — D1, D3, D4, D9, D11, D12, D14  
- [PLATFORM.md](PLATFORM.md) — hub e escopo v1  
- [src/vision/fusion/README.md](../src/vision/fusion/README.md) — visão e VRAM  
- [OFFLINE_FIRST.md](OFFLINE_FIRST.md) — padrões históricos MQTT (mobile fora do v1)  
- [HYBRID_ARCHITECTURE.md](HYBRID_ARCHITECTURE.md) — sensores em wearable (futuro)