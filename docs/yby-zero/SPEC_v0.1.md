# YBY ZERO — Especificação v0.1

## Objetivo

Criar um núcleo modular para conversa por voz e assistência contextual, distribuindo responsabilidades entre PC, smartphone, fones e wearable.

## Critérios de sucesso

- Receber uma intenção estruturada.
- Classificar privacidade.
- Selecionar uma rota.
- Produzir resposta ou fallback.
- Emitir eventos versionados.
- Registrar latência e resultado.
- Operar com capacidade reduzida quando serviços falharem.

## Fora do escopo

- Treinamento de modelo próprio.
- Autonomia irrestrita.
- Visão contínua.
- Produto médico ou de segurança crítica.

## Estados de degradação

`FULL_LOCAL` → `MOBILE_LOCAL` → `DETERMINISTIC_ONLY` → `WATCH_SAFE_MODE` → `LOCKED_SAFE_STATE`.

## Interface entre dispositivos

Todos os dispositivos devem se comunicar por eventos versionados. O transporte pode evoluir de WebSocket para MQTT ou WebRTC sem alterar o contrato semântico.
