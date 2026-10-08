"""
Configurações centralizadas do Gateway YBY SEED

Responsabilidade:
- Configurações de ambiente (variáveis de ambiente)
- Defaults para MQTT, LanceDB, Ollama, etc.
- Validação de configurações obrigatórias

Licença: MIT
"""

from pydantic import BaseSettings, Field
from typing import Optional


class Settings(BaseSettings):
    """
    Configurações do Gateway.
    """
    
    # === MQTT ===
    MQTT_BROKER_HOST: str = Field(default="localhost", description="Host do broker MQTT")
    MQTT_BROKER_PORT: int = Field(default=1883, description="Porta do broker MQTT")
    MQTT_CLIENT_ID: str = Field(default="yby-seed-gateway", description="Client ID MQTT")
    MQTT_TOPIC_PREFIX: str = Field(default="yby", description="Prefixo dos tópicos MQTT")
    
    # === LanceDB ===
    LANCEDB_PATH: str = Field(default="/data/vectors", description="Caminho do LanceDB")
    LANCEDB_INDEX_CACHE_SIZE: int = Field(default=128, description="Cache do índice em MB")
    
    # === Ollama (IA local) ===
    OLLAMA_HOST: str = Field(default="http://localhost:11434", description="Host do Ollama")
    OLLAMA_MODEL_EMBEDDING: str = Field(default="all-minilm:22m", description="Modelo de embeddings")
    OLLAMA_MODEL_LLM: str = Field(default="qwen2.5:7b", description="Modelo LLM principal")
    
    # === FastAPI ===
    FASTAPI_HOST: str = Field(default="0.0.0.0", description="Host do FastAPI")
    FASTAPI_PORT: int = Field(default=8000, description="Porta do FastAPI")
    FASTAPI_WORKERS: int = Field(default=4, description="Número de workers")
    
    # === Logging ===
    LOG_LEVEL: str = Field(default="INFO", description="Nível de log")
    
    # === Segurança ===
    API_KEY: Optional[str] = Field(default=None, description="Chave de API (opcional)")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Instância global
settings = Settings()


# Validação de configurações obrigatórias
def validate_settings():
    """Validar configurações obrigatórias"""
    required = ["MQTT_BROKER_HOST", "LANCEDB_PATH", "OLLAMA_HOST"]
    
    for field in required:
        if not getattr(settings, field):
            raise ValueError(f"Configuração obrigatória: {field}")
    
    print("✅ Configurações validadas")


if __name__ == "__main__":
    validate_settings()
