# YBY — Fluxo de Trabalho de Documentação

**Data:** 23/10/2026 (atualizado)  
**Status:** Ativo  
**Escopo:** Todo assunto relacionado ao ecossistema YBY (SEED, CyberTupã, Instituto, Upcycling)

## 1. Princípio

Toda discussão aqui no chat que fechar uma lacuna (decisão tomada, dúvida resolvida, informação consolidada) vira um documento no Google Drive, organizado na pasta correta.

- Chat = rascunho e discussão.
- Drive = fonte da verdade.
- Só entra no Drive o que está fechado.

## 2. Fluxo em 4 passos

1. **Discutir** o assunto no chat até fechar a lacuna.
2. **Detectar fechamento** — o assistente avisa: "isso virou um documento".
3. **Aprovar** — o usuário revisa e aprova (ou pede ajuste).
4. **Criar e organizar** — documento criado no Drive, na pasta correta, com título e data.

## 3. Estrutura padrão de documento

- Título + data
- Estado atual (o que já existia antes)
- Decisões tomadas (o que fechamos na conversa)
- Próximos passos (o que ainda falta)
- Referências/fontes (links, pesquisas, memórias)

## 4. Nomenclatura

`YYYY-MM-DD_Tema.md`

Exemplo: `2026-10-23_Instituto_ModeloNegocio.md`

## 5. Organização de pastas

```
YBY/
├── 00_FluxoDeTrabalho.md (este arquivo)
├── 00_Indice.md (índice mestre, a criar)
├── SEED/
├── CyberTupã/
└── Instituto/
    └── (upcycling entra aqui)
```

## 6. Regras

- Assuntos pequenos podem ser anexados como seção nova em documento existente, em vez de criar arquivo novo.
- Evitar fragmentação: só criar documento novo se o assunto for substancial e estiver realmente fechado.
- Sempre atualizar o índice mestre ao criar novo documento.
- Usar atalhos em vez de cópias quando precisar do mesmo doc em dois lugares.

## 7. Modo Programação

Sempre que o assunto for programação/desenvolvimento no YBY:

- Assistente explica termos técnicos como professor (linguagem simples, analogias quando ajudar).
- Assistente formula perguntas com 3 opções para cada decisão importante.
- Usuário responde com a opção (1, 2 ou 3) ou com suas palavras.
- Ao fechar a decisão, assistente cria documento no Drive e guia a implementação passo a passo.
- Princípio: programação por linguagem natural — usuário decide, sistema traduz em código.

## 8. Dupla escrita Drive + GitHub

Sempre que estivermos DESENVOLVENDO algo (código, arquitetura, documento técnico do YBY):

| Situação | Drive | GitHub |
|---|---|---|
| Discussão/pesquisa sem conclusão | Não | Não |
| Lacuna fechada (decisão, plano, documento) | Sim | Sim (cópia em docs/) |
| Código, teste, configuração | Não | Sim (commit direto ou PR) |
| Mudança grande/arriscada | Sim | Branch + Pull Request, usuário aprova antes |

Fluxo:
1. Fechar lacuna no chat.
2. Criar/atualizar documento no Drive.
3. Fazer commit correspondente no GitHub (FRANK1-AZZA-Tekk/yby-seed).
4. Se mudança grande, abrir Pull Request e aguardar aprovação do usuário antes do merge.

Válido para: YBY SEED, YBY Zero, CyberTupã, Instituto.

## 9. Próximos passos

- Criar `00_Indice.md` na raiz de YBY (quando houver 3+ documentos).
- Aplicar o fluxo no próximo assunto fechado.