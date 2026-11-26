# YBY Glass v0.1 — especificação canônica (camada G0)

> **Status:** G0 = especificação + contrato simulado offline. **Não há hardware, captura real, STT/TTS real, inferência multimodal, rede nem renderização de HUD.**
> Código do contrato: [`src/yby/glass/`](../src/yby/glass/) · Testes: `tests/yby/test_glass_contract.py`, `tests/yby/test_glass_simulator.py`.
> Fora do caminho do `ask`: nada em `src/engine`, `src/main.py`, `src/safety`, `src/actions` ou `src/memory` importa `src/yby/glass`.

Este é o único documento canônico do YBY Glass. Planejamento wearable anterior (T-Watch, gateway, rede): [future/PLANO_ECOSISTEMA_WEARABLE.md](future/PLANO_ECOSISTEMA_WEARABLE.md) — não repetido aqui.

---

## a) Objetivo e limites do v0.1

**Objetivo:** definir o contrato entre um wearable fino de captura/exibição (YBY Glass) e o PC Hub, e provar o fluxo com simuladores determinísticos, antes de qualquer hardware.

**Princípio:** YBY Glass = sensor fino + HUD limitado. PC Hub = STT local, planner, safety, memória, ferramentas autorizadas e logs.

**O que G0 entrega (fato):**

- Estados de captura e transições (`FakeGlassSession`).
- Contrato das ferramentas de percepção (`PerceptionResult` + 5 tools opcionais, `glass_tool_specs`).
- Contrato do HUD por 8 primitivas (`validate_hud_payload`).
- Simuladores `FakeGlassCapture`, `FakeGlassHUD`, `FakeGlassSession`, `InMemoryRetentionSink`, `GlassMetrics`.
- Testes offline.

**O que G0 não entrega:** câmera, microfone, ESP32, BLE/Bluetooth, Wi‑Fi, captura contínua, STT/TTS real, modelo multimodal, MediaPipe, app Android/iOS, interface gráfica, sincronização, gravação no vault, novas permissões no núcleo, integração com `yby ask` ou `yby agent`.

**Sem promessas:** este documento não afirma desempenho, latência real, autonomia, modelo, privacidade total ou ausência de rede. Qualquer número abaixo é **limite de contrato** (validação), não medição.

---

## b) Arquitetura

```text
[YBY Glass — thin client]                    [PC Hub — cérebro]
  captura discreta (frame/áudio)  ──────▶    processamento local (futuro: STT D11, visão D14)
  indicador de captura + parada              planner / agente (src/agent_loop, opcional)
  HUD por primitivas pequenas     ◀──────    safety (src/safety) — única porta de execução
  zero decisão local                         memória (vault, src/memory) — só com retenção explícita
                                             logs e métricas
```

- O óculos **não** decide, não chama nuvem, não executa comandos e não guarda memória. Só captura sob ativação, mostra primitivas e envia eventos.
- O PC Hub concentra estado, planejamento e inteligência. Transporte (HTTP, MQTT, BLE etc.) **não** está definido em G0.
- Reuso no YBY (sem duplicar):
  - Ferramentas: `ToolSpec` / `ToolRegistry` de [`src/agent_loop/tools.py`](../src/agent_loop/tools.py). As tools Glass são `ToolSpec` comuns, **não** registradas em `default_tool_registry`.
  - Execução: só `src/safety` (decisão) + `src/actions` (subprocesso). Glass não importa nenhum dos dois.
  - Memória: `Vault.write_note` ([`src/memory/vault.py`](../src/memory/vault.py)) é o destino futuro da retenção (G2). Em G0 a retenção vai para um sink em memória.
  - Voz: [`src/voice`](../src/voice) (D11) e contratos T-Watch em [`src/yby/audio/schemas.py`](../src/yby/audio/schemas.py) (D15) continuam independentes; Glass não os reimplementa.

---

## c) Fluxo de captura

```text
ativação explícita (arm) → captura temporária → processamento → decisão de retenção → vault (futuro)
                                                              └→ descarte (padrão)
```

1. **Ativação explícita:** o usuário chama `arm()`. Uma ativação vale para **uma** captura e expira (`ARM_TTL_SECONDS = 60`).
2. **Captura temporária:** um frame ou um clipe de áudio sintético. Limite de bytes brutos (`MAX_CAPTURE_BYTES = 262144`).
3. **Processamento:** o hub deriva resumo/itens limitados. Os **bytes brutos são descartados ao fim do processamento** (sucesso ou falha).
4. **Decisão de retenção:** o HUD recebe uma `confirmation`. O derivado fica pendente por `CAPTURE_TTL_SECONDS = 30`.
5. **Retenção:** só por decisão explícita do usuário. Sem decisão → descarte.

---

## d) Regra de privacidade: captura não é memória

- Nada capturado vira memória sem **confirmação do usuário** (`via="user_confirmation"`) ou **comando explícito de retenção do usuário** (`via="user_command"`).
- Retenção por **política explícita** (ex.: "reter textos de etiquetas da oficina") é prevista para G2 e **não está implementada**: o padrão de G0 é nunca reter automaticamente.
- O que é retido: resumo derivado + metadados (`capture_id`, tipo, horário, via). **Nunca** imagem ou áudio bruto.
- Não existe tool de retenção: o planner não consegue reter nada.
- Não há envio para nuvem. Upload de imagem/áudio exigiria política explícita + confirmação + log local (D12/D13) em camada futura — não existe em G0.
- Este contrato reduz exposição por padrão; **não** é garantia formal de privacidade. Qualquer dado retido pode conter informação sensível (pessoas, telas, documentos, endereços).

## e) Sem captura contínua

- Proibida captura contínua por padrão: sem vídeo, sem stream, sem gravação em segundo plano.
- Cada captura exige `arm()` prévio; depois da captura a sessão volta a exigir nova ativação.
- Só uma captura pendente por vez.

## f) Indicador de captura e parada imediata

- Ao iniciar captura, o HUD recebe `status` com `state="capturing"` e `capture_indicator=true`. O contrato **rejeita** `status` com `state="capturing"` e indicador desligado.
- `session.capture_indicator` é verdadeiro em `capturing` e `processing`.
- `stop()` funciona em qualquer estado: impede novas capturas, descarta o derivado pendente e desliga o indicador.
- `stop()` **não** promete cancelar trabalho já iniciado (ex.: processamento em curso); apenas impede novas capturas e descarta o pendente.
- Sair de `stopped` exige nova ativação explícita (`arm()`).

## g) Permissões separadas

- A sessão Glass tem só `glass.perceive` (`GLASS_PERMISSIONS`). Não existe permissão de execução no módulo.
- Percepção **não concede** execução: as tools Glass não chamam `src/safety`, `src/actions`, subprocesso nem rede.
- Qualquer ação derivada de algo percebido passa pelo caminho normal do YBY (planner → `src/safety` → confirmação humana → `src/actions`), sem atalho.

## h) Conteúdo percebido é dado não confiável

- Todo `PerceptionResult` carrega `trust: "untrusted"` (campo fixo).
- Texto lido em placas, telas ou falas ("ignore as regras", "execute…", "salve isto") é **dado**, nunca instrução autorizada. Não altera permissões, não dispara retenção e não registra tools.
- Testado com conteúdo injetado em `tests/yby/test_glass_simulator.py`.

---

## i) Contrato das ferramentas de percepção

Opcionais, isoladas e com saída estruturada. Criadas por `glass_tool_specs(session)` e registradas **manualmente** num `ToolRegistry` novo. Argumentos validados por Pydantic (`extra="forbid"`).

| Tool | Argumentos | Saída (`content.kind`) | Observação |
|---|---|---|---|
| `glass_capture_frame` | `{}` | `frame` | Exige sessão `armed` (ativação do usuário). Não existe tool de captura de áudio: áudio é push-to-talk do usuário (`session.capture_audio()`). |
| `glass_transcribe_audio` | `capture_id` | `audio` | Transcrição derivada (sintética em G0). |
| `glass_describe_frame` | `capture_id` | `description` | Descrição derivada. |
| `glass_read_visible_text` | `capture_id` | `text` | Linhas de texto visíveis (não confiáveis). |
| `glass_find_object` | `capture_id`, `label` (≤ 40) | `objects` | Itens cujo rótulo contém `label`. |

`capture_id` segue `^cap-[0-9]{4,}$`.

**Saída (`PerceptionResult`, todos os campos obrigatórios, sem campos extras):**

```json
{
  "source": "glass_capture_frame",
  "capture_id": "cap-0001",
  "captured_at": "2026-11-26T12:00:00+00:00",
  "content": {"kind": "frame", "summary": "frame sintético 320x240", "items": []},
  "trust": "untrusted",
  "retention": "pending_user_decision",
  "payload_bytes": 1024
}
```

| Limite | Valor |
|---|---|
| `content.summary` | ≤ 280 caracteres |
| `content.items` | ≤ 8 itens de ≤ 60 caracteres |
| Resultado serializado (UTF‑8) | ≤ 2048 bytes |
| `payload_bytes` | só o tamanho do bruto; o bruto nunca entra no resultado |

**Retenção na saída:** em G0 as tools só respondem sobre a captura **pendente**, então a saída é sempre `pending_user_decision`. Depois da decisão (ou do TTL) a captura deixa de estar disponível e a tool retorna erro. `retained`/`discarded` ficam reservados no contrato para leitura futura (G2).
**Erros (claros, sem truncar silenciosamente):** `GlassStateError` (estado inválido, captura desconhecida/de outro tipo), `GlassExpiredError` (TTL), `GlassPayloadError` (limite excedido), `GlassCaptureError` (falha simulada de captura/processamento). Excedeu limite = erro, não corte.

## j) Contrato do HUD por primitivas

Primitivas pequenas, texto puro. Discriminadas por `kind`, `extra="forbid"`, cada uma com `sensitivity: "public" | "private"` (padrão `public`).

| `kind` | Campos | Limites |
|---|---|---|
| `text` | `text` | ≤ 120 |
| `title` | `text` | ≤ 40 |
| `list` | `items` | 1–5 itens de ≤ 40 |
| `status` | `state`, `capture_indicator`, `label?` | `state` ∈ estados; `capturing` exige indicador |
| `confirmation` | `title`, `options`, `expires_at` | título ≤ 60; 2–3 opções únicas de `yes`/`no`/`cancel`; `expires_at` com fuso |
| `marker` | `x`, `y`, `label?` | `x`,`y` ∈ [0,1] normalizados; rótulo ≤ 24 |
| `progress` | `value`, `label?` | `value` ∈ [0,100] |
| `error` | `code`, `message` | `code` `^[a-z_]{1,32}$`; mensagem ≤ 120 |

Regras (`validate_hud_payload`):

- Payload serializado ≤ **512 bytes**.
- Sem HTML/JS: rejeita `<tag`, `</`, `<!`, `<?`.
- Sem URLs clicáveis por padrão: rejeita `http://`, `https://`, `www.`.
- Sem caracteres de controle (inclui quebra de linha).
- `sensitivity="private"` é rejeitado salvo `HudPolicy(allow_private_display=True)` explícito.
- HUD não executa nada; não há primitiva de comando.
- Confirmação só é respondida por interação do usuário (`decide_retention`); o HUD apenas exibe.
- Violação = erro (`HudPayloadError`), nunca limpeza silenciosa.

Exemplo:

```json
{"kind": "confirmation", "title": "Salvar observação?", "options": ["yes", "no"], "expires_at": "2026-11-26T12:00:30+00:00"}
```

---

## Estados da captura

| Estado | Significado | Sai para |
|---|---|---|
| `idle` | Sem ativação | `armed` (`arm`), `stopped` |
| `armed` | Ativado para uma captura | `capturing`, `idle` (TTL do arm), `stopped` |
| `capturing` | Captura em curso (indicador ligado) | `processing`, `error`, `stopped` |
| `processing` | Derivando resumo; bruto descartado ao fim | `awaiting_retention_decision`, `error`, `stopped` |
| `awaiting_retention_decision` | Derivado pendente, TTL curto | `retained`, `discarded`, `stopped` |
| `retained` | Usuário decidiu reter (só derivado) | `armed` (`arm`), `stopped` |
| `discarded` | Descartado (decisão ou TTL) | `armed` (`arm`), `stopped` |
| `stopped` | Parada: sem novas capturas | `armed` (`arm`) |
| `error` | Falha; pendente descartado, nunca retido | `armed` (`arm`), `stopped` |

---

## k) Modo simulador e testes offline

- `FakeGlassCapture`: devolve `SyntheticFrame` / `SyntheticAudio` roteirizados pelo teste (bytes sintéticos + resumo, texto visível, objetos, transcrição). Permite injetar falha de captura ou de processamento e um gancho `on_capture` para observar o estado durante a captura.
- `FakeGlassHUD`: valida cada primitiva e registra as aceitas; conta rejeições.
- `FakeGlassSession`: coordena estados, TTLs (relógio injetável `FakeClock`), retenção e métricas.
- `InMemoryRetentionSink`: registra só observações derivadas retidas.
- Nenhum acesso a câmera, microfone, rede, Bluetooth ou dispositivo real. Os testes verificam os imports do pacote (AST) e executam o fluxo com `socket` e `subprocess` bloqueados.

## l) Métricas mínimas (`GlassMetrics`)

| Métrica | Campo |
|---|---|
| Latência captura → fim do processamento (relógio injetado) | `latencies_ms` |
| Tamanho de payload (máx. bruto e máx. HUD) | `max_capture_bytes`, `max_hud_bytes` |
| Chamadas de tool | `tool_calls` |
| Falhas | `failures` |
| Retenção | `retained`, `discarded`, `expired` |
| Capturas | `captures_started`, `captures_completed` |
| HUD | `hud_accepted`, `hud_rejected` |

Em G0 as latências vêm do relógio simulado; **não** representam desempenho real.

---

## m) Roadmap G0–G6

| Fase | Entrega | Estado | Gate |
|---|---|---|---|
| **G0** | Esta spec + contrato simulado + testes offline | **Feito nesta camada** | `make check` |
| G1 | Tools Glass opcionais no `yby agent` (só simulador, flag explícita) | Futuro | Aprovação do dono (muda superfície do agente) |
| G2 | Retenção para o vault (`Vault.write_note`, só derivado) + política explícita de retenção | Futuro | Aprovação (privacidade/memória) |
| G3 | Contrato de transporte hub↔óculos (mensagens versionadas, autenticação, loopback/LAN) com simulador de dispositivo | Futuro | Aprovação (rede/permissões) |
| G4 | Spike de hardware em repo externo (YBY / FRANK_ZER0, D1/D7) — captura sob botão, indicador físico | Futuro | Aprovação + hardware |
| G5 | Percepção local no PC Hub (STT D11, visão D14) atrás do mesmo contrato, com métricas reais | Futuro | Aprovação + medição no PC Hub |
| G6 | HUD real no dispositivo + avaliação de campo (latência, falhas, retenção) | Futuro | Aprovação + evidência medida |

Nenhuma fase futura é dependência do `ask` ou do núcleo.

## n) Riscos, pendências e critérios de aceite

**Riscos:**

- Câmera em primeira pessoa capta terceiros, telas, documentos e locais sensíveis; retenção mal desenhada vira vigilância.
- Prompt injection por texto visível ou fala (mitigado em contrato: `trust="untrusted"`, sem tool de retenção, sem execução).
- Indicador de captura só é real com hardware (G4+); em G0 é contrato + simulador.
- `stop()` não cancela processamento já iniciado (limitação declarada).
- Latência e qualidade reais desconhecidas até G5/G6.

**Pendências:**

- Transporte, autenticação e formato no fio (G3).
- Política explícita de retenção e gravação no vault (G2).
- Escolha de hardware e firmware (G4, fora deste repositório).
- Modelos de STT/visão no PC Hub (G5; D11/D14 já existentes, não ligados ao Glass).

**Critérios de aceite G0 (verificados por teste):**

1. Nenhuma captura sem ativação explícita.
2. Captura só após `arm()`; uma ativação = uma captura.
3. Pendente descartado por padrão (TTL) e bruto descartado após processamento.
4. Retenção só por decisão explícita do usuário.
5. `stop()` impede novas capturas.
6. Erro nunca vira retenção.
7. Tools retornam JSON estruturado e limitado, sem bruto.
8. Conteúdo percebido não altera permissões nem retenção.
9. HUD aceita só as 8 primitivas válidas.
10. Payload do HUD ≤ 512 bytes.
11. Sem rede, câmera, microfone ou dependência externa nova.

---

## Referências externas (padrões, não código copiado)

Registro com nível de leitura em [SOURCE_SURVEY.md](SOURCE_SURVEY.md) (rodada 3).

- **OpenSQZ Glass / OpenGlass** — divisão sensor no óculos ↔ inferência no host próximo; captura sob demanda de um frame; recomendações de minimizar retenção de brutos e de nuvem só como opção explícita. Nenhum código copiado.
- **lstk-eye** (MIT) — óculos como thin client; servidor dono do estado; HUD por cenas JSON pequenas e limitadas; modo mock + simulador de dispositivo. Nenhum código copiado; as primitivas do YBY são próprias.
