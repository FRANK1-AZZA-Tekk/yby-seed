import os

import httpx
from langchain_core.tools import tool


MQTT_HTTP_URL = os.getenv("MQTT_HTTP_URL", "http://localhost:8081/publish")


@tool
def publish_mqtt(topic: str, payload: dict) -> str:
    """Publica uma mensagem JSON em um tópico MQTT do YBY."""
    response = httpx.post(
        MQTT_HTTP_URL,
        json={"topic": topic, "payload": payload},
        timeout=10,
    )
    response.raise_for_status()
    return f"Mensagem publicada em {topic}."
