# Validação integrada FinOps (#42)

**Branch:** `cursor/cloud-usage-validate-ebc0` (sobre tip `cursor/cloud-usage-s5-doctor-f592` / #90).  
**Issue:** [#42](https://github.com/FRANK1-AZZA-Tekk/yby-seed/issues/42) — **permanece aberta** até merge validado em `main`.  
**Escopo:** não recria SQLite, relatório nem retenção; só matriz, testes integrados e lacunas mínimas.

## Estado vs `main`

| Item | Situação |
|---|---|
| Pilha | #82 → #83 → #85 → #87 → #89 → #90 (abertas; tip +10 vs `main`) |
| Na `main` | Baseline JSONL + budget de tokens |
| No tip | S1–S5: SQLite, USD, authz, report/prune |

## Matriz requisito → código → teste → lacuna

| Requisito | Código | Teste | Lacuna / fechamento |
|---|---|---|---|
| Registry antes de HTTP | `hybrid._cloud_gate_reply` / `_cloud_call` | `tests/test_cloud_usage_integration.py` | FakeProvider `calls==0` quando bloqueia |
| Import JSONL idempotente | `cloud_usage_db.import_jsonl` + dedupe | integration + `test_import_jsonl_twice_idempotent` | Dedupe na chave estável |
| Sem double-count JSONL+SQLite | `CloudBudget._usage` primary SQLite | `test_no_double_count_mirror_coexistence` | Budget ignora JSONL se DB existe |
| Query pós-gravação | stamp WAL (#87) | `test_usage_visible_immediately_after_write` | Totais atualizam após append |
| Tokens estimados vs reportados | meta `token_basis=estimated` | hybrid completed + doc SPEC §4.5 | Reportados = futuro |
| Custo known/free/unknown | `cloud_pricing.CostEstimate` | `test_cloud_pricing` + report note | Unknown ≠ $0 conhecido; floor p/ teto |
| Aviso vs bloqueio | `budget.evaluate` | `test_warn_allows_block_denies_provider` | Warn chama; block `calls==0` |
| Cache sem cobrança | `_cloud_call` via `cache` | `test_cache_hit_no_second_provider_call` | 2ª chamada não incrementa |
| Vault deny | `cloud_authz` | `test_vault_block_no_provider_call` | `calls==0` |
| Ollama fail ≠ nuvem | `_after_local_failure` | `test_ollama_fail_does_not_call_cloud` | D12 |
| `cloud report` ≡ budget | `cloud_usage_report` + budget | `test_report_matches_budget_same_history` | Mesmo hist |
| `prune --dry-run` | `cloud_cli` + `fingerprint` | `test_cli_prune_dry_run_fingerprint` | DB inalterado |

## Ordem de revisão / integração

1. #82 → #83 → #85 → #87 → #89 → #90 (bottom-up).
2. Depois este PR de validação.
3. Fechar #42 só após o conjunto em `main` e aceite abaixo.

## Aceite

- Relatório e orçamento batem no mesmo histórico de teste.
- Provedor simulado sem chamada quando a política bloqueia.
- `prune --dry-run` não altera registros (fingerprint estável).
- Sem chaves reais / sem HTTP pago.
