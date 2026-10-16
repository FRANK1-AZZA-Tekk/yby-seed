# Inventário de módulos experimentais — YBY SEED

> Fase 9A — somente leitura. Nenhum arquivo foi movido, alterado ou executado
> além deste documento. O mapeamento detalhado de imports por arquivo fica
> para a Fase 9B, antes de qualquer movimentação.

## Princípio

O nome do diretório não define maturidade: `src/core/` também contém código
experimental. A recomendação abaixo é preliminar e deve ser confirmada com
mapeamento de imports antes de qualquer movimentação (Fase 9B).

## Inventário

| Módulo | Status preliminar | Evidência | Recomendação |
|---|---|---|---|
| `src/core/gatekeeper.py` | Núcleo MVP | Usado pelo `ask` para reconhecer comandos | Manter |
| `src/core/ollama_client.py` | Núcleo MVP | Cliente HTTP com política loopback (4A) | Manter |
| `src/core/router.py` | Núcleo MVP | Router determinístico de rota única (4B) | Manter |
| `src/core/storage.py` | Núcleo MVP | Storage SQLite isolado (3A) | Manter |
| `src/core/audit.py` + `audit_contracts.py` | Núcleo MVP | Auditoria opt-in de metadados (3B) | Manter |
| `src/core/auto_improvement.py` | Experimental | Retorna métricas fixas; anuncia otimização com TODO | Mover para `src/experimental/` |
| `src/core/auto_cleanup.py` | Experimental | Limpeza de arquivos + PostgreSQL/Redis incompatíveis com o núcleo | Mover para `src/experimental/` |
| `src/core/fastapi_mqtt_bridge.py` | Experimental | Embeddings de zeros; WebSocket/worker consomem a mesma fila | Mover para `src/experimental/` |
| `src/core/openrouter_sanitizer.py` | Experimental | Pode retornar exemplos de dados sensíveis | Mover para `src/experimental/` |
| `src/core/skill_manager.py` | Experimental | Registra trecho do comando do usuário | Mover para `src/experimental/` |
| `src/security/sandbox_executor.py` | Legado | Não é fronteira de segurança; fora do MVP | Mover para `src/experimental/` ou arquivar |
| `src/gateway/` | Experimental | MQTT/LanceDB; fora do fluxo principal | Mover para `src/experimental/` |
| `src/mobile/` | Futuro | Fora do escopo PC-first da Fase 1 | Mover para `src/experimental/` |
| `src/agents/` | A avaliar | Sem evidência de uso no núcleo | Avaliar no mapeamento de imports (9B) |
| `src/evaluation/` | A avaliar | Sem evidência de uso no núcleo | Avaliar no mapeamento de imports (9B) |
| `src/monitoring/` | A avaliar | Dashboards fora do fluxo principal | Avaliar no mapeamento de imports (9B) |
| `src/rag/` | A avaliar | Busca documental é planejada, não implementada | Avaliar no mapeamento de imports (9B) |
| `src/skills/` | A avaliar | Automações; sem consumo confirmado no `ask` | Avaliar no mapeamento de imports (9B) |

## Regras para a Fase 9B

1. Um módulo por commit; nenhum módulo movido antes do mapeamento de imports.
2. Cada movimentação atualiza imports, testes e referências em workflows.
3. Nada é deletado — apenas reorganizado.
4. Critério de aceite por commit: testes do núcleo passam, nenhum import
   quebrado, CI verde.
5. `src/core/` não é movido inteiro; apenas arquivos experimentalmente
   identificados são candidados à movimentação.

## Limitações desta fase

- Mapeamento de imports por arquivo ainda não realizado (Fase 9B).
- Status de `agents`, `evaluation`, `monitoring`, `rag` e `skills` é
  preliminar, baseado em estrutura de diretórios e auditoria estática
  anterior, não em leitura completa de cada arquivo.
- Nenhuma execução de código ou teste foi realizada nesta sessão.
