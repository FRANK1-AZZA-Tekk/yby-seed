# Arquitetura de Reuso — YBY SEED

## Decisão

O YBY SEED deve ser um **hub local-first com orquestração explícita**, não um sistema multiagente conversacional genérico. O projeto mantém sua camada própria de skills, segurança e experiência, mas reutiliza componentes maduros para reduzir esforço.

## Pilares

1. **Orquestração:** LangGraph como base futura do fluxo `router -> planner -> executor -> validator`.
2. **Modelos locais:** Ollama como runtime local, sempre mockável em testes.
3. **RAG:** RAGFlow ou R2R para ingestão, parsing, busca híbrida e citações.
4. **Memória:** padrão MemGPT/Letta — memória de trabalho, histórico recuperável e arquivo de longo prazo.
5. **Skills:** código próprio do YBY, com manifesto, permissões, sandbox e confirmação humana.

## Fluxo alvo

```text
usuário
  -> router
  -> planner
  -> executor (tools/skills)
  -> validator
  -> resposta com fontes e auditoria
```

## Regras

- Nenhum serviço externo é obrigatório para rodar testes unitários.
- Ollama, Qdrant, RAGFlow e serviços de memória são opcionais e injetáveis.
- Ações com efeito externo exigem permissão explícita e log de auditoria.
- Ferramentas seguem whitelist; não há execução arbitrária de código sem sandbox.
- Cada skill declara permissões, limite de passos e política de confirmação.

## Roadmap de adoção

| Fase | Entrega | Reuso |
|---|---|---|
| A | CLI real de testes e testes da CLI | pytest, Click |
| B | `yby status` e limpeza de dependências | psutil/opcional |
| C | `yby ask` com busca em documentos e LLM mockável | LangGraph, Ollama |
| D | RAG local com citações | RAGFlow ou R2R, Qdrant |
| E | Memória persistente | Padrão MemGPT/Letta |
| F | Skills seguras com sandbox | Código próprio do YBY |

## Referências

- LangGraph: orquestração stateful de agentes.
- MemGPT/Letta: memória hierárquica e persistente.
- ReAct: loop `Thought -> Action -> Observation` para uso de ferramentas.
- RAGFlow/R2R: RAG local com processamento de documentos.
- Open Interpreter: referência para sandbox e confirmação humana.
