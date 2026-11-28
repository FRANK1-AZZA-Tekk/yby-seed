# Pesquisa (Fase 0): Ordens de serviço com checklist offline

Todas as incógnitas do Contexto Técnico foram resolvidas abaixo. Nenhuma pendência de esclarecimento permanece. Três escolhas dependem do mantenedor e estão em "Decisões abertas" no fim.

## R1. Módulo novo em vez de estender `src/yby_machine/compiler.py`

- **Decisão**: criar `web/os-checklist/` como app estático independente.
- **Motivo**: o gerador atual (legado, fora do fluxo `ask`; `src/README.md` pede para não expandir) grava `localStorage` primeiro e depois IndexedDB, engole erros e não relê o que gravou. Isso fere o Princípio III (sem "salvo" otimista) e a regra S2 (sem auditoria). Reaproveitar exigiria reescrever o núcleo de escrita dentro de um gerador de templates em strings Python, o que é um diff maior e mais frágil.
- **Reaproveitado como referência**: a CSP restritiva, o DOM sem `innerHTML` e a convenção de nomes de banco. Nada de código é copiado.
- **Alternativas**: estender o compilador (rejeitada: acopla ao legado e amplia módulo fora de escopo); gerar o app a partir do `yby` (rejeitada: fora do escopo da spec).

## R2. JavaScript puro em módulos ES, sem framework nem build

- **Decisão**: ES2022 nativo, sem bundler, sem dependências.
- **Motivo**: Princípio I e regra de nenhuma dependência nova sem aprovação. Módulos nativos funcionam com `script-src 'self'`.
- **Alternativas**: framework de UI ou TypeScript (rejeitadas: exigem build e dependências).

## R3. Efeito e registro de auditoria na mesma transação

- **Decisão**: `commit` grava o efeito e o registro juntos, de forma atômica.
- **Motivo**: S2 diz que falha de log bloqueia a ação; a transação única entrega isso e evita o caso "efeito sem registro" e o caso "registro dizendo sucesso sem efeito".
- **Alternativas**: registro antes e efeito depois (rejeitada: deixa registro de sucesso sem efeito se o app cair no meio); efeito antes e registro depois (rejeitada: efeito sem registro).

## R4. Reserva em `localStorage` com chave única

- **Decisão**: o estado inteiro numa chave (`yby_os_checklist_v1`), um `setItem` por commit, releitura e comparação.
- **Motivo**: D-4 pede uma gravação completa por commit; `setItem` é atômico em relação a cota e interrupção, e permite incluir OS e auditoria na mesma gravação (R3). Custo: reescrever o JSON inteiro a cada commit, aceitável na escala do modo reserva.
- **Alternativas**: chaves separadas para OS e auditoria (rejeitada: não é atômica entre chaves).

## R5. Fila única e controle de revisão

- **Decisão**: o coordenador executa um comando por vez; o commit informa a revisão lida e a porta recusa se for outra.
- **Motivo**: com aba única (R6) a corrida só aparece por defeito; vira erro visível, não corrupção. Também resolve o duplo toque: o segundo toque espera o primeiro terminar e então é avaliado contra o estado já gravado (`sem_efeito`).
- **Alternativas**: sem controle (rejeitada: mascara defeitos); bloqueio otimista por OS (rejeitada: complexidade sem ganho com uma aba).

## R6. Segunda aba bloqueada por Web Locks, falha fechada

- **Decisão**: `navigator.locks.request('yby-os-checklist', { ifAvailable: true })` mantido durante a vida da aba. Sem bloqueio, aviso e sem UI de escrita. Sem Web Locks, aviso de navegador sem suporte.
- **Motivo**: D-3 pede bloqueio com aviso; Web Locks existe em Chrome 69 ou superior e Safari 15.4 ou superior. Falhar fechado é coerente com a constituição.
- **Alternativas**: lease com batimento em `localStorage` (rejeitada: mais código para navegadores que o escopo não exige); `BroadcastChannel` (rejeitada: não dá exclusão mútua confiável).
- **Limite conhecido**: o app instalado na tela inicial do iPhone e a aba do Safari têm armazenamento separado; o bloqueio não cobre essa separação. Vira orientação e item de roteiro.

## R7. Sonda sem criar banco

- **Decisão**: antes do consentimento, `probe.js` abre o IndexedDB e aborta a transação de atualização quando a versão antiga é 0, o que não cria o banco. Para a reserva, só lê `getItem`.
- **Motivo**: SC-006 exige zero bytes antes do consentimento e o app precisa saber se o consentimento já existe.
- **Alternativas**: `indexedDB.databases()` (rejeitada: suporte irregular); marcador em `localStorage` (rejeitada: seria escrita antes do consentimento).

## R8. Recusa do consentimento inicial não é gravada

- **Decisão**: a recusa fica só em memória; nada é persistido, nem auditoria.
- **Motivo**: D-2 e SC-006 pedem zero gravação antes do aceite. É a única exceção a "toda tentativa gera registro" e está declarada no plano.

## R9. Service Worker: lista fixa, cache-first, atualização no próximo início

- **Decisão**: cache versionado (`yby-os-v1`) com lista fixa de arquivos; sem `skipWaiting`; resposta de rede nunca é guardada.
- **Motivo**: troca de módulos no meio do uso pode misturar versões. Sem dado dinâmico no cache (S4).
- **Alternativas**: stale-while-revalidate (rejeitada: exige rede e guarda respostas).

## R10. Estratégia de testes sem dependência nova

- **Decisão**: `node --test` (embutido) para a lógica e a varredura estática, com invólucro pytest que pula sem Node. Chrome headless via `subprocess` e servidor `http.server` para o contrato da porta (opt-in). Roteiro manual para aparelhos.
- **Motivo**: Playwright e jsdom exigiriam aprovação; Node e Chrome já existem no ambiente e nos runners.
- **Alternativas**: fake de IndexedDB em JavaScript (rejeitada: comportamento falso não prova durabilidade real); Playwright (rejeitada: dependência nova).
- **Injeção de falha**: a porta falsa e envoltórios de teste forçam falha no commit, falha na releitura, cota e interrupção.

## R11. HTTPS para validar no iPhone

- **Decisão**: validar em origem segura. Android usa `adb reverse` para `localhost`. iPhone precisa de HTTPS real.
- **Motivo**: Service Worker e armazenamento persistente exigem contexto seguro; `http` na rede local não conta no Safari.
- **Alternativas**: HTTPS local com certificado confiável (viável, mais trabalho no aparelho); hospedagem estática do código (precisa de aprovação de deploy; `vercel.json` hoje pula builds).

## R12. Persistência e remoção por inatividade no Safari

- **Decisão**: chamar `navigator.storage.persist()` depois do consentimento; mostrar aviso quando negado; recomendar instalar na tela inicial e exportar.
- **Motivo**: FR-014 exige tratamento da perda por inatividade; o app não consegue impedir a remoção, só reduzir o risco e avisar.

## R13. Exportação e compartilhamento

- **Decisão**: arquivo JSON (`yby-os-export`, versão 1) só com OS e itens. Entrega por `navigator.share` com arquivo quando disponível; senão download por `<a download>` de um Blob. O registro de auditoria é gravado antes da entrega.
- **Motivo**: D-1 define leitura crítica como exportar ou compartilhar. A auditoria não é exportada (não pedido na spec).
- **Limite**: o app não sabe se o usuário concluiu o compartilhamento.

## R14. Limites de entrada

- **Decisão**: título até 120 caracteres; cliente até 120; local até 200; telefone até 30; observações até 2000; item até 200 caracteres; até 100 itens por OS.
- **Motivo**: mantém o estado dentro da capacidade do modo reserva e evita entradas patológicas. São valores propostos; podem ser ajustados nas tarefas sem mudar o desenho.

## R15. Tela de auditoria somente leitura

- **Decisão**: lista simples de registros (tipo, ação, instante, identificador da OS).
- **Motivo**: o roteiro precisa comparar tentativas com registros em aparelho real sem ferramentas de desenvolvedor.

## Decisões abertas (padrão proposto)

| ID | Pergunta | Padrão proposto | Alternativa |
|---|---|---|---|
| D-A | Como obter HTTPS para I-Safari | Hospedagem estática só do código, com deploy aprovado à parte | HTTPS local com certificado confiável |
| D-B | Testes de navegador no CI | Opt-in, fora do `make test` | Incluir no CI |
| D-C | Chave de diagnóstico `?storage=ls` | Incluir, documentada, com aviso visível | Sem chave; reserva só em teste headless |
