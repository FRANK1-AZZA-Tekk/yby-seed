# IoT / MQTT — sensores domésticos (issue #111)

Módulo opcional em `src/iot/` para presença, temperatura, portas e movimento no **PC Hub** (D9), **sem VRAM** e **sem nuvem por padrão** (D3).

## Instalação

```bash
pip install -r requirements-iot.txt
```

Variáveis de ambiente:

| Variável | Padrão | Descrição |
| :--- | :--- | :--- |
| `IOT_BROKER_HOST` | `localhost` | Host do Mosquitto |
| `IOT_BROKER_PORT` | `1883` | Porta MQTT |
| `IOT_USERNAME` | _(vazio)_ | Usuário (opcional) |
| `IOT_PASSWORD` | _(vazio)_ | Senha (se usuário definido) |
| `IOT_TOPICS` | `yby/sensors/#` | Tópicos separados por vírgula |

## Mosquitto local (D9)

Ubuntu / Debian:

```bash
sudo apt install mosquitto mosquitto-clients
sudo systemctl enable --now mosquitto
```

Teste rápido:

```bash
mosquitto_sub -h localhost -t 'yby/sensors/#' -v
mosquitto_pub -h localhost -t 'yby/sensors/sala/dht/temperature' -m '{"value":22.5,"unit":"C"}'
```

O **hub YBY** (`yby-hub.service`) **não** inicia o broker; o Mosquitto é serviço à parte, como no Syncthing (ver [PLATFORM.md](PLATFORM.md)).

### Auth e TLS (D10)

Se o broker for acessível fora do loopback:

1. Crie usuário: `mosquitto_passwd -c /etc/mosquitto/passwd yby_hub`
2. Configure `listener` + `password_file` e, se exposto na LAN, **TLS** (`cafile`, `certfile`, `keyfile`).
3. Defina `IOT_USERNAME` / `IOT_PASSWORD` no `.env` do YBY.

Não publique o broker na internet sem VPN ou mTLS. Atuadores que ligam/desligam dispositivos devem passar por `src/safety` (D10) em código futuro.

## Convenção de tópicos

```
yby/sensors/{room}/{sensor_id}/{tipo}
```

`tipo` ∈ `presence` | `temperature` | `door` | `motion`

Exemplos:

| Tópico | Significado |
| :--- | :--- |
| `yby/sensors/sala/pir/presence` | Presença na sala |
| `yby/sensors/quarto/dht22/temperature` | Temperatura |
| `yby/sensors/entrada/magnet/door` | Porta/janela |
| `yby/sensors/garagem/pir/motion` | Movimento |

### Payload JSON

Schema mínimo (obrigatório):

```json
{"value": true}
```

Exemplos:

```json
{"value": 23.4, "unit": "C", "ts": 1730000000}
{"value": "open"}
{"value": "closed"}
{"value": "detected"}
```

`ts` opcional (epoch segundos); se ausente, usa horário de recepção.

## Uso no código

```python
from src.iot import IoTConfig, MQTTClient, parse_message
from src.iot.langgraph_bridge import SensorStateStore, register_iot_tools
from src.iot.mem0_bridge import save_episode

config = IoTConfig.from_env()
store = SensorStateStore()

client = MQTTClient(config)

def on_message(topic: str, payload: bytes) -> None:
    event = parse_message(topic, payload)
    store.update(event)
    save_episode(event, save_fn=lambda text, meta: print(text, meta))

client.on_message(on_message)
```

`MQTTClient` usa reconexão automática do paho (`loop_start`). Nos testes, injete `mqtt_client=...` com mock.

## Mem0

`save_episode(event, mem0_client=...)` grava texto em pt-BR no Mem0:

- **Dedupe:** mesmo `sensor_id` + mesmo `value` em **&lt; 5 s** → ignora.
- **Rate-limit:** **10** eventos/minuto por sensor.

Alternativa sem SDK Mem0: `save_fn(text, metadata)`.

## LangGraph

`register_iot_tools(store)` retorna tools:

| Tool | Função |
| :--- | :--- |
| `get_sensor_state(sensor_id)` | JSON com último estado |
| `list_sensors()` | Lista de sensores ativos |

O `SensorStateStore` é em memória no processo; reinicie o worker MQTT após reboot do Hub.

Integração com o LangGraph do **yby-core** (D7) permanece em repositório separado — use estas tools como contrato ao conectar grafos externos.

## Alinhamento com decisões

| Decisão | Como o módulo respeita |
| :--- | :--- |
| **D1** PC-first | Broker e consumer no PC Hub |
| **D3** Local-first | MQTT só na LAN; sem envio de leituras à nuvem |
| **D4** | Sem modelo na GPU |
| **D9** | Mosquitto como serviço doméstico paralelo ao hub |
| **D10** | Auth/TLS documentados; atuadores → `src/safety` (futuro) |
| **D11** | Alertas por voz podem consumir eventos (futuro) |
| **D12** | CPU apenas; zero tokens em leituras de sensor |
| **D14** | Independente da fila de visão |

## Testes

```bash
pytest tests/iot/ -vv
```

Mocks de `paho-mqtt` e Mem0 — não exige broker nem hardware.

## Referências

- [SENSES-ROADMAP.md](SENSES-ROADMAP.md) — prioridade IoT
- `src/iot/` — implementação