# LiteLLM (espelho)

A configuração **canônica** do projeto é `config/litellm_config.yaml` (montada pelo `docker-compose.yml`).

Este diretório (`litellm/config.yaml` + `.env.example`) é um espelho/legado. Prefira editar a raiz. O comando `yby ask` não depende deste proxy: ele usa `src/engine` (Ollama + nuvem direta).

Ver [docs/DEV.md](../docs/DEV.md).
