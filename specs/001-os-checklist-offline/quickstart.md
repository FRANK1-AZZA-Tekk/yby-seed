# Quickstart (Fase 1): validar o app de OS com checklist offline

Este guia vale para a fase de implementação. Nesta camada (plano) nada disso foi executado: o app ainda não existe.

## Pré-requisitos

- Python 3.11 e o ambiente do repositório (`make doctor`).
- Node 18 ou superior (opcional; sem ele os testes de lógica são pulados).
- Chrome para os testes de navegador (opcional).
- Android com Chrome e iPhone com Safari para o roteiro manual.

## Servir o app localmente

```bash
python3 -m http.server 8080 --directory web/os-checklist
```

- No computador: `http://localhost:8080` (origem segura).
- No Android: `adb reverse tcp:8080 tcp:8080` e abrir `http://localhost:8080` no Chrome do aparelho.
- No iPhone: exige HTTPS (decisão aberta D-A do plano).

## Testes automáticos

| O que | Comando | Quando |
|---|---|---|
| Lógica e varredura estática | `node --test web/os-checklist/tests/unit` | Sempre que mexer em `web/os-checklist/src` |
| Mesmo, pelo pytest | `python -m pytest tests/test_os_checklist_web.py -q` | Faz parte do `make test` |
| Contrato da porta em Chrome headless | `YBY_OS_BROWSER_TESTS=1 python -m pytest tests/test_os_checklist_web.py -q` | Local, sob demanda (decisão aberta D-B) |

Ao fim de cada camada de implementação: `make doctor`, `make lint` e `make test`.

## Roteiro manual (A-Chrome e I-Safari)

Para cada passo, anotar aparelho, navegador, versão, resultado (passou ou falhou) e observação. Guardar em `specs/001-os-checklist-offline/validation/<aparelho>.md`.

| # | Requisito | Passos | Resultado esperado |
|---|---|---|---|
| 1 | FR-012, D-2 | Abrir na primeira vez; recusar o consentimento | Nada gravado; armazenamento do site vazio |
| 2 | FR-012, D-2 | Aceitar o consentimento | Backend informado; tela de auditoria mostra `consentir` |
| 3 | FR-001, FR-002 | Com rede, abrir; ativar modo avião; fechar e reabrir | App abre e funciona sem rede |
| 4 | FR-005 | Criar OS com duplo toque rápido | Uma OS |
| 5 | FR-005 | Recarregar durante a criação | Zero ou uma OS, nunca duas |
| 6 | FR-006 | Marcar e desmarcar o mesmo item várias vezes | Estado final igual ao último toque; sem item duplicado |
| 7 | FR-003, FR-004 | Marcar item; observar "salvando" e "salvo" | "Salvo" só depois de gravar |
| 8 | FR-008 | Marcar item e encerrar o navegador na hora | Ao reabrir: estado anterior ou novo, nunca misto |
| 9 | D-5 | Concluir com item desmarcado | Alerta com pendentes; confirmar leva a `concluida_pendencias` |
| 10 | D-5 | Reabrir a OS | Estado `aberta`; pendentes limpos |
| 11 | FR-007 | Concluir duas vezes | Instante de conclusão da primeira mantido |
| 12 | D-7 | Remover uma OS; cancelar; remover de novo | Cancelar não remove; segunda remoção é `sem_efeito` |
| 13 | D-1, FR-012 | Exportar; cancelar; exportar e confirmar | Cancelar não gera arquivo; confirmar entrega o JSON |
| 14 | FR-009, PA-1 | Remover tudo (confirmar) | OS somem; tela de auditoria mantém todos os registros anteriores |
| 15 | FR-009, PA-2 | Cancelar uma confirmação | Registro `recusa` com `usuario_cancelou` |
| 16 | FR-009, PA-3 | Contar tentativas feitas e registros na tela | Números iguais |
| 17 | FR-011 | Inspecionar o armazenamento do site | Registros sem título, cliente, local, observação nem texto de item |
| 18 | FR-010 | Usar o app com um proxy ou monitor de rede | Nenhuma requisição além do carregamento inicial |
| 19 | FR-013, D-3 | Abrir uma segunda aba | Aviso de app já aberto; sem escrita |
| 20 | D-4 | Forçar a reserva (`?storage=ls`, decisão aberta D-C) | Aviso permanente; mesmas garantias; cota mostrada se esgotada |
| 21 | FR-014 | Safari: deixar o site sem uso e reabrir; instalar na tela inicial | Aviso de persistência negada; dados mantidos no app instalado; exportação como contingência |
| 22 | FR-013, D-6 | Procurar qualquer tela de importação | Não existe |

## Critério de pronto da validação

Todos os passos passam em A-Chrome e I-Safari, ou cada falha tem registro com evidência e decisão do mantenedor.
