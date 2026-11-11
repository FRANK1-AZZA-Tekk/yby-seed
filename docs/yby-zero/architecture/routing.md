# Roteamento

O roteador escolhe provider e modelo usando privacidade, latência, custo, bateria, disponibilidade do PC, necessidade de visão e necessidade de ferramentas.

Política inicial:

- P3: regras locais ou confirmação humana.
- P2: PC local preferencial.
- P1: local primeiro; nuvem somente se autorizada.
- P0: qualquer provider permitido.
- Falha do provider: circuit breaker e fallback.
