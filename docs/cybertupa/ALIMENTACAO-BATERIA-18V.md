# CyberTupã — Esquema de Alimentação com Bateria de Ferramenta 18V/20V

**Data:** 24/10/2026  
**Status:** Decisões fechadas (MVP)  
**Escopo:** Alimentação do CyberTupã (ecossistema YBY)

## 1. Estado atual

- Bateria Dewalt 20V MAX 5Ah confirmada como ecossistema principal (usuário já possui).
- Hub Waveshare USB3.2-Gen1-HUB-2IN-4OUT adquirido/identificado (entrada DC 7-36V, 4 portas USB 3.2, dual host).
- Decisão anterior de power bank substituída por bateria de ferramenta.
- Solar Power Manager (C) avaliado e classificado como backup futuro (fase 2).
- Bateria 48V Makita-style avaliada e descartada para o MVP (incompatível com hub, cara e pesada).

## 2. Decisões tomadas

| Decisão | Escolha |
|---|---|
| Bateria principal | Dewalt 20V MAX 5Ah |
| Redundância | Comprar 1-2 baterias Dewalt extras (troca rápida em campo) |
| Conversor | Buck 5V/5A dedicado (HJTOOK ou similar) para o ROCK 4D |
| Hub | Waveshare USB3.2-Gen1-HUB-2IN-4OUT (alimenta periféricos direto da bateria) |
| Proteção | Completa: fusível 5A + chave + medidor tensão/corrente + módulo UPS |
| Solar | Solar Power Manager (C) como backup futuro (fase 2) |
| Autonomia estimada | ~10-11h por bateria 5Ah em consumo moderado (~8W) |

## 3. Arquitetura final

```
Bateria Dewalt 20V (com 1-2 extras para troca)
        │
   [Fusível 5A] → [Chave] → [Medidor V/A]
        │
        ├──→ Hub Waveshare (7-36V direto)
        │        ├── ESP32-S3 Sense
        │        ├── Korvo-1
        │        ├── Câmera/sensor
        │        └── SSD/LoRa
        │
        └──→ Buck 5V/5A ──→ ROCK 4D (USB-C PD)

[Módulo UPS] ←→ Tomada 110V (quando disponível)

[Futuro - fase 2: Painel solar → Solar Power Manager (C) → ROCK 4D]
```

## 4. Justificativas técnicas

- **Dewalt 20V vs power bank:** ~45% mais energia útil (90Wh vs ~61Wh), 3x mais corrente, troca rápida em campo, flexibilidade de tensão.
- **Hub Waveshare:** aceita 7-36V direto da bateria, alimenta 4 periféricos USB com 5V/2A cada, tem ESD e proteções embutidas.
- **ROCK 4D:** precisa de 5V USB-C PD, mínimo 3A — por isso o buck 5V/5A separado.
- **Bateria 48V descartada:** tensão 39-54,6V excede o limite do hub (36V), exigiria conversor extra, é cara e pesada.
- **Solar Power Manager (C):** útil como backup solar (29Wh, 5V/3A PD), mas não substitui a Dewalt e não alimenta o hub (precisa de 7V mínimo).

## 5. Próximos passos

- Comprar 1-2 baterias Dewalt 20V extras.
- Adquirir buck 5V/5A, fusível 5A, chave, medidor e módulo UPS.
- Montar e testar o circuito em bancada antes de integrar ao case.
- Validar consumo real com o medidor e ajustar estimativas.
- Fase 2: avaliar Solar Power Manager (C) + painel solar para autonomia estendida.