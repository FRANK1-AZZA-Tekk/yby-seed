# Documentação

## Comece por aqui (v1 ativo)

| Doc | Conteúdo |
|---|---|
| [REPOS.md](REPOS.md) | Onde programar; checklist de camadas; repos separados |
| [DEV.md](DEV.md) | Setup, CLI, env, testes, pastas |
| [CI.md](CI.md) | Gate CI, revisão automática de PRs, Bugbot |
| [PLATFORM.md](PLATFORM.md) | Hub systemd, Syncthing, nuvem (OpenRouter; D12) |
| [MEMORY.md](MEMORY.md) | Vault Obsidian |
| [../DECISIONS.md](../DECISIONS.md) | D1–D13 (vigentes) |
| [../ARCHITECTURE.md](../ARCHITECTURE.md) | Arquitetura do v1 (`ask` / safety / engine) |
| [../ROADMAP.md](../ROADMAP.md) | Fases (atualizar com o checklist em REPOS) |
| [LAYER_ADMISSION.md](LAYER_ADMISSION.md) | Política de admissão de camadas (ficha, estados, proibição de expansão sem aceite) e classificação atual |
| [archive/FORA-DO-V1.md](archive/FORA-DO-V1.md) | Mobile/firmware removidos da árvore |
| [future/PLANO_ECOSISTEMA_WEARABLE.md](future/PLANO_ECOSISTEMA_WEARABLE.md) | Wearable, gateway, métricas, execução (fora do v1) |
| [YBY_GLASS_SPEC.md](YBY_GLASS_SPEC.md) | YBY Glass v0.1 — spec canônica G0–G1 (contrato simulado offline, roteiro dev `scripts/glass_sim.py`; sem hardware; fora do `ask`) |
| [OPENCODE_INTEGRATION.md](OPENCODE_INTEGRATION.md) | OpenCode como ferramenta de engenharia (não runtime) — perfil `yby-engineer`, permissões e testes da config |
| [future/EVO_NIGHT_WATCH.md](future/EVO_NIGHT_WATCH.md) | Evo / Night Watch — design de auto-evolução supervisionada (fora do caminho `ask` até implementação pedida) |
| [future/](future/) | Índice mobile/ESP / Evo |
| [HISTORY.md](HISTORY.md) | Histórico de camadas concluídas (movido de `PROGRESS.md`); estado atual em [../PROGRESS.md](../PROGRESS.md) |

## Histórico / contexto (não é o caminho do `ask`)

Textos úteis como referência, mas desatualizados em relação a D3–D11. Não use como guia de implementação do v1:

- Arquiteturas e matrizes antigas: `ARCHITECTURE.md`, `ARCHITECTURE_RAG.md`, `HYBRID_ARCHITECTURE.md`, `MODEL_MATRIX.md`, `docs/architecture/`
- Mobile na raiz de docs: `MOBILE_SETUP.md`, `ANDROID_OPTIMIZATIONS.md` (preferir `future/`)
- Custos / quickstart / planejamento amplo: `PLANEJAMENTO-CUSTOS-IA.md`, `QUICKSTART.md`, `PLANO-PC-FIRST.md`, `PC_DEPLOYMENT.md`
- Processo Drive / instituto / financiamento: `FLUXO-TRABALHO.md`, `GOVERNMENT_FUNDING.md`, `EXECUTIVE_SUMMARY.md`, `AGENTIC_SDLC.md`, `cybertupa/`
- Checklists e otimizações gerais: `OPTIMIZATION_CHECKLIST.md`, `OTIMIZACOES.md`, `OFFLINE_FIRST.md`, `OBSERVABILITY.md`, `AUTO_EVOLUTION.md` (histórico; direção Evo vigente em `future/EVO_NIGHT_WATCH.md`)
- Segurança auxiliar: `SECURITY_BEST_PRACTICES.md`; Strix removida: `SECURITY_SCANNING_STRIX.md`
- Roadmap antigo MQTT-centrado: `docs/ROADMAP.md` (o vigente é `ROADMAP.md` na raiz)

Não é preciso reescrever esses arquivos agora: o índice acima basta para não confundir.
