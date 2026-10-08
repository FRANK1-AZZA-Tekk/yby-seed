#!/usr/bin/env python3
"""
Exemplo 1: Alerta de Chuva

Este script verifica se vai chover amanhã e envia uma notificação.

Como usar:
    python examples/01_weather_alert.py

O que ele faz:
    1. Consulta API do OpenWeatherMap
    2. Verifica previsão para amanhã
    3. Se chance de chuva > 50%, envia notificação
"""

import requests
from datetime import datetime, timedelta

# Configurações
API_KEY = "SUA_API_KEY_AQUI"  # Pegue em https://openweathermap.org/api
CITY = "Sao Paulo"
COUNTRY = "BR"

def get_weather_tomorrow():
    """Consulta previsão do tempo para amanhã"""
    
    url = f"http://api.openweathermap.org/data/2.5/forecast"
    params = {
        "q": f"{CITY},{COUNTRY}",
        "appid": API_KEY,
        "units": "metric"
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    # Filtra dados para amanhã
    tomorrow = datetime.now() + timedelta(days=1)
    tomorrow_str = tomorrow.strftime("%Y-%m-%d")
    
    for item in data["list"]:
        if item["dt_txt"].startswith(tomorrow_str):
            return item
    
    return None

def check_rain_chance(weather_data):
    """Verifica se há chance de chuva"""
    
    if not weather_data:
        return False
    
    # Verifica descrição do tempo
    description = weather_data["weather"][0]["description"].lower()
    rain_keywords = ["rain", "chuva", "drizzle", "garoa"]
    
    return any(keyword in description for keyword in rain_keywords)

def send_notification(message):
    """Envia notificação (placeholder)"""
    
    print(f"🔔 NOTIFICAÇÃO: {message}")
    # TODO: Implementar notificação real (Telegram, email, etc.)

def main():
    """Função principal"""
    
    print("🌤️  Verificando previsão do tempo para amanhã...")
    
    weather = get_weather_tomorrow()
    
    if not weather:
        print("❌ Não foi possível obter previsão do tempo")
        return
    
    print(f"📊 Previsão: {weather['weather'][0]['description']}")
    print(f"🌡️  Temperatura: {weather['main']['temp']}°C")
    
    if check_rain_chance(weather):
        send_notification("☔ Vai chover amanhã! Leve um guarda-chuva.")
    else:
        send_notification("☀️  Tempo seco amanhã. Aproveite!")

if __name__ == "__main__":
    main()
