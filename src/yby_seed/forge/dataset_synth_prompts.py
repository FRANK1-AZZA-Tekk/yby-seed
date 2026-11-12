"""Prompts e templates para síntese de dataset (pt-BR)."""

SYNTH_SYSTEM = """Você gera exemplos de treino YBY SEED em português.
Siga docs/yby_seed_contracts.md: primeiro bloco ```yaml com hardware_check, depois código fenced.
Use placas reais (seeed_xiao_esp32s3, esp32_s3_devkitc1, esp32_p4_c6, waveshare_modbus_rtu).
ESP-IDF 5.3 para esp_idf; LVGL v9 para lvgl_v9; Modbus com CRC válido para modbus_rtu.
Sem texto fora dos blocos yaml e código."""

INTENT_TEMPLATES: dict[str, list[str]] = {
    "esp_idf": [
        "Crie app_main que pisca LED no GPIO 4 na esp32_s3_devkitc1 com FreeRTOS.",
        "Task MQTT publicando temperatura simulada a cada 5s (ESP-IDF 5.3).",
        "Configure I2C no XIAO ESP32-S3 para ler sensor, sem usar pinos reservados.",
    ],
    "lvgl_v9": [
        "Tela LVGL v9 com um botão que alterna label (placa esp32_s3_devkitc1).",
        "Inicialize lvgl v9 com flush callback mínimo e um label central.",
    ],
    "modbus_rtu": [
        "Leia holding register 1 do slave 1 em 9600 baud com CRC Modbus.",
        "Escreva coil 0 no slave 2 com trama RTU válida.",
    ],
    "python_fastapi": [
        "Endpoint GET /health que retorna status ok com pytest.",
        "Função add(a,b) com teste pytest simples.",
    ],
}
