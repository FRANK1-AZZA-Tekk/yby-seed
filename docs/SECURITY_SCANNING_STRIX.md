# Scan de Segurança com Strix

> Resumo: a Strix é um agente de IA open source que testa vulnerabilidades como um pentester. Este guia mostra como rodá-la no YBY SEED de forma segura e barata.

Documentação oficial: https://docs.strix.ai/usage/cli

## Pré-requisitos

- Docker em execução
- Strix instalada (veja a documentação oficial)
- Chave de um provedor de LLM configurada, conforme a documentação da Strix

## Regras de ouro

1. **Commit ou stash antes de rodar.** Um diretório local é montado de forma gravável no sandbox, então o agente edita os arquivos reais (exceto `.git`).
2. **Rode sempre em um branch separado** (`git checkout -b strix-scan`) e revise o diff antes do merge.
3. **Defina teto de custo** com `--max-budget` e `--max-turns`.

## Comandos

Scan rápido (padrão recomendado para o MVP):

```bash
strix -n --target ./ --scan-mode quick --max-budget 5 --max-turns 150
```

Scan focado nos riscos do YBY SEED:

```bash
strix --target ./ --scan-mode standard \
  --instruction "Foque em prompt injection, execução arbitrária de código gerado por LLM, command injection, path traversal e vazamento de segredos/API keys"
```

Apenas arquivos alterados (ideal para PRs):

```bash
strix -n --target ./ --scan-mode quick --scope-mode diff --diff-base origin/main
```

Falhar apenas em severidade alta ou crítica (CI):

```bash
strix -n --target ./ --scan-mode quick --fail-on high
```

## Códigos de saída

| Código | Significado |
| - | - |
| 0 | Scan concluído sem achados (ou abaixo do limite de `--fail-on`) |
| 1 | Erro fatal (variáveis ausentes, Docker indisponível, config inválida) |
| 2 | Vulnerabilidades encontradas (somente modo headless) |

## Modos de scan

- `quick`: rápido e barato, bom para CI e PRs
- `standard`: equilíbrio entre profundidade e custo
- `deep`: padrão da ferramenta, mais completo e mais caro

## Áreas prioritárias no YBY SEED

- Execução de código gerado por LLM (isolar em sandbox, sem rede, sem privilégios)
- Prompt injection em automações de linguagem natural
- Segredos e chaves de API (litellm, docker-compose, .env)
- Process manager e scripts com chamadas de shell

## Relação com outros documentos

- [SECURITY.md](../SECURITY.md)
- [SECURITY_BEST_PRACTICES.md](SECURITY_BEST_PRACTICES.md)

## Checklist

- [ ] Commit/stash feito e branch `strix-scan` criado
- [ ] Scan `quick` executado e relatório revisado
- [ ] Achados triados em issues
- [ ] Workflow de CI avaliado
