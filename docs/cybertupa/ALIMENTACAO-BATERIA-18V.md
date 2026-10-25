# CyberTupã — Esquema de Alimentação (revisado: Power Bank MVP + Dewalt Fase 2)

**Data:** 24/10/2026 (revisado)  
**Status:** Decisões fechadas (MVP)  
**Escopo:** Alimentação do CyberTupã (ecossistema YBY)

## 1. Estratégia em duas fases

| Item | MVP (agora) | Fase 2 (futuro) |
|---|---|---|
| Fonte principal | Power bank 20.000mAh (USB-C PD) | Dewalt 20V MAX 5Ah + extras |
| Alimentação do ROCK 4D | Direto do power bank (USB-C PD) | Buck 5V/5A |
| Alimentação do hub | Boost 5V→12V | Direto da bateria (7-36V) |
| Proteção | Embutida do power bank + ESD do hub | Fusível + chave + medidor + UPS |
| Custo inicial | ~R$ 120-220 | ~R$ 300-500 adicionais |
| Autonomia | ~7-8h | ~10-11h + troca rápida |

## 2. Arquitetura do MVP

```
Power bank 20.000mAh (USB-C PD 5V/3A)
        │
        ├──→ ROCK 4D (USB-C PD, direto)
        │
        └──→ Boost 5V→12V ──→ Hub Waveshare (7-36V)
                                   ├── ESP32-S3 Sense
                                   ├── Korvo-1
                                   ├── Câmera/sensor
                                   └── SSD/LoRa
```

## 3. Arquitetura da Fase 2 (migração)

```
Bateria Dewalt 20V (com 1-2 extras para troca)
        │
   [Fusível 5A] → [Chave] → [Medidor V/A]
        │
        ├──→ Hub Waveshare (7-36V direto)
        │
        └──→ Buck 5V/5A ──→ ROCK 4D (USB-C PD)

[Módulo UPS] ←→ Tomada 110V

[Fase 3: Painel solar → Solar Power Manager (C) → ROCK 4D]
```

## 4. Justificativas

- **Power bank no MVP:** mais barato (R$ 100-200), já vem pronto com PD, suficiente para validação do CyberTupã.
- **Boost 5V→12V:** necessário porque o hub Waveshare exige no mínimo 7V e o power bank entrega 5V. Custo ~R$ 15-25.
- **Dewalt na fase 2:** ~45% mais energia útil (90Wh vs ~61Wh), 3x mais corrente, troca rápida em campo.
- **Bateria 48V Makita-style:** descartada (incompatível com hub, cara e pesada).
- **Solar Power Manager (C):** backup futuro (fase 3), não substitui a Dewalt.
- **Case modular:** projetar para aceitar power bank (MVP) e bateria Dewalt (fase 2) sem retrabalho.

## 5. Próximos passos

- Adquirir power bank 20.000mAh com PD 5V/3A.
- Adquirir conversor boost 5V→12V.
- Montar e testar o circuito MVP em bancada.
- Fase 2: migrar para Dewalt 20V + buck 5V/5A + proteções completas.
- Fase 3: avaliar solar com Solar Power Manager (C).