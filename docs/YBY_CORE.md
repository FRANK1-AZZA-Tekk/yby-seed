# YBY Core — Framework único do YBY SEED

## Objetivo

O YBY Core é o orquestrador central do YBY SEED. Ele cria a experiência de **um único app**, enquanto mantém serviços especializados isolados por trás.

O usuário interage apenas com o YBY. Os serviços — Ollama, OpenRouter, LiteLLM e memória — permanecem como infraestrutura gerenciada.

## Princípio

```text
Uma interface.
Um comando para subir.
Um cérebro central.
Vários serviços isolados.
```

## Arquitetura (fase atual)

```text
Usuário
  ↓
CLI / chat local
  ↓
yby_zero.Router  (provider + privacidade)
  ↓
orchestrator.classify_task
  ↓
RouterAgent / Planning / Validation / Execution
  ↓
tools (jail ~/yby) + Ollama local
  ↓
Resultado
```

LangGraph completo (opcional): `integrations/yby-core/`.

## Responsabilidades

| Componente | Responsabilidade |
|---|---|
| `src/yby_zero` | Eventos, privacidade P0–P3, degradação, roteamento de provider |
| `src/orchestrator` | Tipo de tarefa + escolha de modelo local-first |
| `src/agents` | Intenção → plano → validação → execução |
| `src/tools` | Ferramentas com caminho seguro |
| LiteLLM / Ollama | Inferência local e fallback sanitizado |
| `integrations/yby-core` | FastAPI + LangGraph + SSE (opcional) |

## Regras de segurança

1. Ações destrutivas exigem confirmação explícita.
2. Skills só executam a partir de diretórios permitidos.
3. Toda execução deve ter timeout e limites.
4. Segredos nunca ficam no repositório.
5. Dados sensíveis preferem Ollama local.
6. OpenRouter é fallback, não destino padrão de dados sensíveis.
