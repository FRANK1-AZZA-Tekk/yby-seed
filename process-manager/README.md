# Process Manager (experimentale — não usar em produção)

Este diretório é um **protótipo legado**. Não faz parte do MVP exocórtex (`yby skill`) nem do núcleo `src/yby_seed`.

- Caminho SQLite fixo (`/opt/yby/registry/yby_seeds.db`) — não portátil.
- Execução dinâmica de código do banco **sem** passar pela allowlist de `src/safety`.

**Substituto canônico:** `yby skill` + `src/orchestration/exocortex.py` + confirmação explícita.

Não integre este processo ao host sem revisão de segurança dedicada.
