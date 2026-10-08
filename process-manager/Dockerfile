FROM python:3.11-slim

WORKDIR /opt/yby

# Instala dependências
RUN pip install --no-cache-dir paho-mqtt sqlite3

# Copia código do gerenciador
COPY process_manager.py .
COPY security_linter.py .

# Cria usuário não-root para execução segura
RUN useradd -m yby-executor
USER yby-executor

CMD ["python", "process_manager.py"]
