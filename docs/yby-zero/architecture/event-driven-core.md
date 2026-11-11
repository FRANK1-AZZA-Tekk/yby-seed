# Núcleo orientado a eventos

Eventos são o contrato entre PC, Xiaomi 12, fones e T-Watch. Cada evento contém `schema_version`, `event_id`, `correlation_id`, `timestamp`, `source`, `target`, `event_type`, `priority`, `privacy_level` e `payload`.

Tipos iniciais:

- `audio.input.started`
- `audio.input.ended`
- `transcript.partial`
- `transcript.final`
- `intent.detected`
- `route.selected`
- `response.started`
- `response.chunk`
- `response.completed`
- `watch.notification`
- `system.fallback`
- `system.error`
