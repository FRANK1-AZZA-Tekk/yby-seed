# Design do Roteador Offline YBY

Documento da integração local-first do roteador com o agente (`agent_loop`). Sem nuvem, sem áudio/visão e sem multi-agentes nesta fase.

## Objetivos

- Classificar pedidos de texto com regras determinísticas.
- Escolher modelo local por perfil (`registry`).
- Aplicar fallback local se o principal falhar (nunca nuvem).
- Entregar uma `RouteDecision` validada ao agente.
- Respeitar limites de segurança, aprovação humana e allowlist de tools.
- Observar decisões sem registrar segredos.

## Fluxo

```text
Usuário (texto)
  → OfflineRouter.handle
      → classifier (regras)
      → ModelRegistry (perfil/modelo)
      → FallbackPolicy (opcional, invoker injetado)
      → AgentBridge
          → validate_route_decision / approval
          → RAG local (vault) se intent=knowledge  [dado, não instrução]
          → ControlledAgentLoop (max_steps, max_tool_calls)
      → RouterObserver (evento estruturado)
  → RouterResponse
```

## Módulos

| Módulo | Papel |
|---|---|
| `src/router/schemas.py` | Contratos Pydantic |
| `src/router/classifier.py` | Intenção/risco por regras |
| `src/router/policy.py` | Perfis e validação de segurança |
| `src/router/registry.py` | Catálogo local de modelos |
| `src/router/fallback.py` | Primary → fallback local |
| `src/router/observability.py` | Eventos sem segredos |
| `src/router/integration.py` | Ponte com `agent_loop` + RAG |
| `src/router/router.py` | Fachada `OfflineRouter` |

## Regras de segurança

- `allow_cloud` permanece `false`.
- Tools só do registry allowlisted (`echo_json`, `vault_search`).
- `automation` e risco `high` exigem aprovação humana.
- RAG é marcado como `RAG_DATA` / `not_instructions`.
- Logs não aceitam `prompt`, chaves ou tokens de autenticação.

## Fora de escopo (esta tarefa)

Chamadas reais ao Ollama, nuvem, áudio, visão, multi-agentes, shell livre e acesso irrestrito a arquivos.
