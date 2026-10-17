# Índice de documentação — fonte da verdade

> Regra: se um assunto aparecer em mais de um documento, vale o documento listado aqui.
> Os demais devem ser consolidados, marcados como históricos ou movidos para `attic/`.

| Assunto | Documento oficial | Status |
|---|---|---|
| Visão geral e início rápido | `README.md` | Vigente |
| Arquitetura do MVP | `ARCHITECTURE.md` | Vigente |
| Roadmap F0–F6 | `ROADMAP.md` | Vigente |
| Decisões técnicas | `DECISIONS.md` | Vigente |
| Hardware | `HARDWARE_SPEC.md` | Vigente |
| Modelo de IA | `MODEL_CARD.md` | Vigente |
| Segurança geral | `SECURITY.md` | Vigente |
| Permissões | `docs/policies/PERMISSIONS.md` | Vigente |
| Custo de IA | `docs/policies/COST_POLICY.md` | Vigente |
| Memória | `docs/policies/MEMORY_POLICY.md` | Vigente |
| Execução de código | `docs/policies/EXECUTION_POLICY.md` | Vigente |
| Mobile, Android e Termux | `attic/` | Congelado |
| Wearable, ESP32 e firmware | `attic/` | Congelado |
| Blueprint LangGraph v3.1 | PR #26 | Congelado até decisão |

## Regras anti-drift

1. Não criar novo roadmap, arquitetura ou plano paralelo.
2. Não criar política sem teste que a aplique.
3. Não prometer no README algo que não existe no código.
4. Material futuro vai para `attic/`, não para a documentação do MVP.
5. Toda mudança de decisão técnica deve gerar ou atualizar um ADR em `DECISIONS.md`.
