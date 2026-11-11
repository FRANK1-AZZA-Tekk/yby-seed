# Fase P — PC Hub sempre ligado

Especificação mínima da fase **P** (plataforma), alinhada a **D9** em [DECISIONS.md](../DECISIONS.md). Complementa [PLATFORM.md](PLATFORM.md) e [DEV.md](DEV.md) sem substituí-los.

## Objetivo

Transformar o YBY SEED em um serviço local confiável no PC Hub, sem adicionar mobile, firmware, Docker obrigatório ou nuvem automática.

## Escopo do v1

- Serviço systemd do YBY SEED.
- Início automático após boot.
- Reinício automático em falha.
- Logs locais.
- Syncthing sincronizando apenas o vault Obsidian.
- Backup local do vault e da configuração.
- Verificação de saúde do serviço.

## Fora do escopo

- Mobile.
- ESP32/firmware.
- Docker obrigatório.
- Kubernetes.
- Gateway exposto à internet.
- Voz em nuvem.
- OpenRouter automático.
- Execução automática de comandos destrutivos.

## Arquitetura mínima

- Serviço **systemd de usuário** executa o keepalive do hub no PC Hub (`python yby.py hub` / `src.platform.hub`), conforme `scripts/install-hub-service.sh` e [PLATFORM.md](PLATFORM.md). O núcleo `ask` continua sob demanda no CLI; a fase P não exige daemon HTTP.
- O vault Obsidian é sincronizado pelo **Syncthing** (serviço separado do hub; ver `examples/syncthing/`).
- Backups locais são feitos em horário definido (agendador do SO ou timer systemd).
- O gateway HTTP, se habilitado, **não** expõe além de `127.0.0.1` (`FASTAPI_HOST`); o hub keepalive não abre porta de aplicação.
- Nenhuma chamada de nuvem sem **D12** (confirmação, log local planejado na issue #42, sem TTY = sem nuvem).

## Hardware de referência

PC Hub alvo: Ryzen 5, 16 GB RAM, GTX 1650 4 GB, Ubuntu — ver [HARDWARE_SPEC.md](../HARDWARE_SPEC.md). Modelo local único: `qwen2.5-coder:3b` (D4).

## Critérios de aceite

1. `systemctl --user status yby-hub` (ou nome da unit acordada em [PHASE-P-DECISIONS.md](PHASE-P-DECISIONS.md)) mostra serviço ativo.
2. Após reboot, o serviço inicia automaticamente (`loginctl enable-linger` quando for unit de usuário).
3. Se o processo falhar, o systemd reinicia conforme política definida (`Restart=on-failure`, `RestartSec`).
4. O vault é sincronizado pelo Syncthing entre dispositivos configurados.
5. Existe backup local restaurável do vault (teste documentado no checklist).
6. Nenhuma porta além do loopback é exposta pelo YBY (gateway opcional só em `127.0.0.1`).
7. Nenhuma chamada de nuvem ocorre sem D12 (confirmação explícita; fail de Ollama não dispara nuvem automaticamente — alinhado ao plano #42).
8. Testes e ruff continuam passando no repositório (`pytest -q`, `ruff check .`).

## Riscos

- Perda de dados do vault.
- Syncthing sincronizando arquivos indesejados.
- Serviço iniciando antes da rede estar pronta.
- Backup sobrescrevendo dados bons.
- Porta exposta acidentalmente.
- Falha silenciosa do serviço (Ollama fora sem alerta visível).

## Artefatos relacionados

| Documento | Uso |
|-----------|-----|
| [PHASE-P-CHECKLIST.md](PHASE-P-CHECKLIST.md) | Execução passo a passo |
| [PHASE-P-DECISIONS.md](PHASE-P-DECISIONS.md) | Escolhas pendentes do dono |
| [PLATFORM.md](PLATFORM.md) | Hub systemd já descrito no repositório |
| [docs/syncthing/](../docs/syncthing/) | Exemplos de pasta do vault |

## Referências de decisão

- D1, D5, D8, D9, D10, D11, D12, D13 — [DECISIONS.md](../DECISIONS.md)
