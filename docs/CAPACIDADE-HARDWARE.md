# YBY — Capacidade de Hardware e Matriz de Adoção (out/2026)

Objetivo: registrar o que o YBY adota, adapta ou descarta de acordo com o hardware que já existe. Princípio: Function over Form.

## Hardware de referência
- **PC (cérebro principal):** Ryzen 5 4600G, 16 GB RAM, GTX 1650 (4 GB VRAM), SSD 1 TB, Ubuntu 26.04.
- **Xiaomi 12:** 8 GB RAM (~4 GB livres em uso), gateway; modelos locais de até 3 GB.
- **LilyGO T-Watch S3 Plus (ESP32-S3):** BLE, microgestos, háptico; sem LLM.
- **Futuro:** Radxa ROCK 4D, Guition ESP32-P4+C6, XIAO ESP32-S3 Sense, AtomS3R.

## Adotar agora (cabe no PC)
| Item | Decisão | Observação |
|---|---|---|
| SQLite + sqlite-vec | Padrão de memória | Adequado para dezenas de milhares de entradas; backup = copiar arquivo |
| LanceDB | Só acima de ~50 mil vetores | Substitui o limite anterior de 500 memórias; revisar com benchmark real |
| LLM local 3–4B (Q4_K_M) | Modelo diário e de voz | Candidatos: Phi-4-mini, Gemma pequeno; validar por benchmark |
| faster-whisper (small/base) | STT em PT-BR | Priorizar latência em comandos de voz |
| llama.cpp com CUDA | Motor de inferência | Mantém regra atual |

## Adotar com ressalvas
- **Modelos 7–8B:** exigem offload parcial para a RAM em 4 GB de VRAM. Usar apenas para tarefas lentas em segundo plano, nunca no caminho de voz.
- **Qdrant e PostgreSQL (yby-core):** funcionam, mas são serviços extras que disputam RAM e contradizem a regra "SQLite primeiro". Reavaliar.

## Inspiração apenas (não cabe / licença)
- **MemT-1.0 e DeepSeek V4.1 Flash:** dezenas a centenas de bilhões de parâmetros. MemT: código PolyForm Noncommercial; não copiar código.
- **DeepInfer:** exige GPUs Nvidia SM100 ou NPUs Ascend. Aproveitar apenas a ideia (cache, agendamento determinístico).
- **OpenArm / OpenAMRobot:** referência de physical AI; kit exige Jetson Orin NX e custo elevado.

## Orçamento de VRAM (proposta, a validar)
- ~1 GB para Whisper, ~3 GB para o LLM do caminho de voz.
- Não carregar os dois ao máximo ao mesmo tempo.

## Roteamento por perfil
- **Voz:** modelo pequeno local.
- **Chat geral:** modelo pequeno local; nuvem sanitizada se não resolver.
- **Tarefa pesada:** modelo 7–8B local em segundo plano ou nuvem sanitizada.
- **Sensível:** sempre local.

## Pendências de validação
- Medir tokens/s, VRAM e latência de voz no PC real antes de fixar modelos.
- Decidir se yby-core e yby-seed serão fundidos.
- Conferir licença (MIT) em todos os repositórios.
