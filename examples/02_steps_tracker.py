#!/usr/bin/env python3
"""
Exemplo 2: Monitor de Passos

Este script monitora seus passos diários e avisa quando atingir a meta.

Como usar:
    python examples/02_steps_tracker.py

O que ele faz:
    1. Lê passos de um arquivo (simulando wearable)
    2. Compara com meta diária (10.000 passos)
    3. Envia notificação ao atingir meta
"""

import json
from datetime import datetime
from pathlib import Path

# Configurações
STEPS_FILE = "steps_data.json"
DAILY_GOAL = 10000

def load_steps():
    """Carrega dados de passos do arquivo"""
    
    if not Path(STEPS_FILE).exists():
        return {"steps": 0, "date": datetime.now().strftime("%Y-%m-%d")}
    
    with open(STEPS_FILE, "r") as f:
        return json.load(f)

def save_steps(steps_data):
    """Salva dados de passos no arquivo"""
    
    with open(STEPS_FILE, "w") as f:
        json.dump(steps_data, f, indent=2)

def check_goal(current_steps):
    """Verifica se meta foi atingida"""
    
    if current_steps >= DAILY_GOAL:
        return True
    return False

def send_notification(message):
    """Envia notificação (placeholder)"""
    
    print(f"🔔 NOTIFICAÇÃO: {message}")
    # TODO: Implementar notificação real

def main():
    """Função principal"""
    
    print("👟 Monitor de Passos Diários")
    print(f"🎯 Meta: {DAILY_GOAL} passos\n")
    
    # Carrega passos atuais
    data = load_steps()
    current_steps = data["steps"]
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Verifica se é um novo dia
    if data["date"] != today:
        print("📅 Novo dia! Resetando contagem...")
        current_steps = 0
        data = {"steps": 0, "date": today}
    
    # Simula leitura de passos (substitua por dados reais do wearable)
    new_steps = int(input("Quantos passos você deu hoje? "))
    current_steps += new_steps
    data["steps"] = current_steps
    
    # Salva dados
    save_steps(data)
    
    # Exibe progresso
    print(f"\n📊 Progresso: {current_steps}/{DAILY_GOAL} passos")
    print(f"📈 Faltam: {max(0, DAILY_GOAL - current_steps)} passos\n")
    
    # Verifica meta
    if check_goal(current_steps):
        send_notification("🎉 Parabéns! Você atingiu sua meta de passos hoje!")
    else:
        remaining = DAILY_GOAL - current_steps
        send_notification(f"💪 Você está a {remaining} passos da sua meta!")

if __name__ == "__main__":
    main()
