# YBY SEED — sandbox REA (engenharia reversa defensiva, somente leitura).
# Sem chaves SSH, credenciais do host ou chaves de API de nuvem. Rode com:
#   docker compose --profile rea run --rm -T rea-sandbox
# (rede desligada, rootfs somente leitura, /firmware montado :ro — ver docker-compose.yml)
FROM debian:bookworm-slim

# 1 instala também o JRE + pyghidra/pyghidra-mcp (o Ghidra em si deve ser montado/instalado
# à parte e apontado por GHIDRA_INSTALL_DIR); 0 mantém a imagem enxuta.
ARG INSTALL_GHIDRA=0

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    HOME=/tmp \
    YBY_REA_FIRMWARE_DIR=/firmware

RUN echo "wireshark-common wireshark-common/install-setuid boolean false" | debconf-set-selections \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates python3 python3-venv python3-pip binutils file \
 && apt-get install -y --no-install-recommends binwalk tshark \
 && (apt-get install -y --no-install-recommends radare2 \
     || apt-get install -y --no-install-recommends rizin \
     || echo "AVISO: radare2/rizin indisponíveis no apt; rabin2/r2pipe ficarão desativados") \
 && if [ "$INSTALL_GHIDRA" = "1" ]; then \
      apt-get install -y --no-install-recommends default-jre-headless; \
    fi \
 && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv \
 && pip install \
      "pydantic>=2.5.0" "httpx>=0.27.0" "click>=8.1.0" "python-dotenv>=1.0.0" \
      "requests>=2.31.0" "rich>=13.7.0" "loguru>=0.7.0" "pyyaml>=6.0" \
      "esptool>=4.7.0" "mitmproxy>=10.0.0" "r2pipe>=1.9.0" \
 && if [ "$INSTALL_GHIDRA" = "1" ]; then pip install pyghidra pyghidra-mcp; fi

RUN groupadd --system --gid 10001 reauser \
 && useradd --system --uid 10001 --gid reauser --no-create-home \
      --home-dir /tmp --shell /usr/sbin/nologin reauser \
 && mkdir -p /firmware /app \
 && chown root:root /firmware /app \
 && chmod 0555 /firmware /app

WORKDIR /app
COPY --chown=root:root src /app/src

USER reauser

VOLUME ["/firmware"]
ENTRYPOINT ["python3", "-m", "src.yby.rea.mcp_server"]
