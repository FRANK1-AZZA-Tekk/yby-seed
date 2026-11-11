# Voz em tempo real

O pipeline controlável é:

`fone → VAD → STT → roteador → LLM → TTS → fone`.

Providers Live entram como adaptadores opcionais para conversas full-duplex. O núcleo deve manter suporte a push-to-talk, streaming, interrupção, timeout e fallback local.
