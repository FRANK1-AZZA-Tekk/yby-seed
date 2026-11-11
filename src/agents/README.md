# Agentes (fora do caminho do `ask`)

Estes módulos (`RouterAgent`, `PlanningAgent`, `GovernanceAgent`, …) **existem no disco** e **não** são chamados por `python yby.py ask|run|gate`.

O fluxo ativo do v1 é `engine` + `safety` + `actions` (+ `memory`). Não reescreva nem remova este diretório sem nota de arquivo e decisão explícita.

Referência de escopo: [docs/REPOS.md](../../docs/REPOS.md), [docs/archive/FORA-DO-V1.md](../../docs/archive/FORA-DO-V1.md).
