# Decisões — YBY SEED

## D1 — PC-first

A fase atual foca exclusivamente no PC Hub. Mobile e ESP32 ficam para depois.

## D2 — Documentação antes de código

Inventário real de repositórios e arquitetura por domínios antes de qualquer código novo.

## D3 — Local-first

Ollama local primeiro; OpenRouter apenas como fallback.

## D4 — Modelo 3B

Usar llama3.2:3b na GTX 1650 de 4 GB; um modelo por vez.

## D5 — MVP sem Docker no núcleo

O núcleo (yby.py + RouterAgent) funciona sem containers. Serviços entram em fases posteriores.

## D6 — Automações seguras

Toda skill começa em dry-run e só executa após confirmação do usuário.

## D7 — Consolidação de repositórios

Materiais de YBY, YBY Zero e outros projetos são revisados e unificados no YBY SEED quando fizer sentido técnico.

## D8 — Framework em camadas (Camada A)

Núcleo fino em `src/app/` + camadas empilháveis A–D. Entrypoint canônico: `yby_seed.py` (fachada; sem args = REPL, com args = CLI Click). Scaffold largo (mobile/firmware/grafana/gateway) fica congelado fora do MVP.

## D9 — Defaults de produto (até override explícito)

- LLM: OpenRouter se houver chave; senão Ollama local.
- Interface: só terminal.
- Skills: dry-run + confirmação humana (sem exec automática).
- Memória: adiada (`YBY_MEMORY_BACKEND=none`) até briefing/skills estabilizarem.
- UX em português; identificadores de código em inglês.
