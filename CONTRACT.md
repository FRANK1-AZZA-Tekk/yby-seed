# CONTRATO DE TAREFA — YBY

> Preencha este arquivo **antes** de iniciar qualquer tarefa com agente.
> Ele é a fonte de verdade do escopo, das fronteiras e do critério objetivo de conclusão.

## 1. Identificação

- **ID da tarefa:** `YBY-<fase>-<numero>`
- **Título:** 
- **Data de início:** 
- **Responsável humano:** 
- **Agente executor:** 
- **Agente auditor (opcional):** 

## 2. Objetivo

Descreva em uma frase o resultado observável que deve existir ao final.

**Exemplo:**  
Implementar o endpoint `/health` no YBY SEED, com teste automatizado e documentação mínima.

## 3. Escopo permitido

Liste apenas diretórios e arquivos que o agente pode criar ou modificar.

```text
PERMITIDO:
- src/
- tests/
- docs/
- scripts/

PROIBIDO:
- .env
- .git/
- deploy/
- secrets/
- firmware/
- database/
- infraestrutura de produção
```

## 4. Regras do projeto

- Não altere arquivos de configuração sensíveis.
- Não instale dependências sem registrar em `requirements.txt` ou `pyproject.toml`.
- Não execute comandos de rede, deploy, exclusão ou migração sem aprovação humana.
- Siga a estrutura e as convenções já existentes no repositório.
- Um commit por unidade completa de trabalho.
- Não declare “pronto” sem executar os sensores definidos abaixo.

## 5. Critério objetivo de pronto

A tarefa só está concluída quando **todas** as condições abaixo forem verdadeiras:

- [ ] O código compila ou roda sem erro.
- [ ] Os testes definidos passam.
- [ ] O lint passa, se configurado.
- [ ] A funcionalidade está coberta por teste automatizado.
- [ ] A documentação relevante foi atualizada.
- [ ] O progresso foi registrado em `PROGRESS.md`.
- [ ] O commit foi criado.
- [ ] Nenhum arquivo fora do escopo foi alterado.

## 6. Sensores obrigatórios

| Sensor | Comando | Resultado esperado | Obrigatório |
|---|---|---|---|
| Testes | `make test` | exit code `0` | Sim |
| Lint | `make lint` | exit code `0` | Se disponível |
| Build | `make build` | exit code `0` | Se aplicável |
| Health check | `make doctor` | exit code `0` | Se aplicável |

> Regra: uma evidência só conta se ela pode retornar **erro**.

## 7. Limites de execução

- Máximo de tentativas para o mesmo erro: **2**
- Máximo de tempo total: **30 minutos**
- Máximo de custo de API, se aplicável: **definir valor**
- Ao atingir qualquer limite: **parar**, registrar em `PROGRESS.md` e escalar para humano.

## 8. Ações irreversíveis

As ações abaixo exigem aprovação humana explícita:

- `git push`
- `git push --force`
- Deploy
- Exclusão de arquivos ou branches
- Migração de banco
- Alteração de credenciais
- Acesso à rede externa
- Alteração de configuração de hardware ou firmware

## 9. Entrega

Ao final, o agente deve produzir:

1. Resumo objetivo do que foi feito.
2. Lista de arquivos alterados.
3. Resultado dos sensores executados.
4. Riscos, limitações ou pendências.
5. Commit(s) criados.
6. Atualização do `PROGRESS.md`.

## 10. Definição de falha

A tarefa é considerada **falha** se:

- O agente alterar arquivos fora do escopo.
- O agente pular os sensores obrigatórios.
- O agente declarar conclusão sem evidência verificável.
- O mesmo erro ocorrer duas vezes sem nova informação.
- O limite de tempo, custo ou tentativas for atingido.
