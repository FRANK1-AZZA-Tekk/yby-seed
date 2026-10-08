# Sua Primeira Automação

> **Tempo estimado:** 20 minutos  
> **Nível:** Iniciante

---

## 🎯 O Que Você Vai Criar

Neste tutorial, você vai criar um **monitor de passos diários** que:

1. Lê seus passos de um wearable (ou simula)
2. Compara com sua meta (10.000 passos)
3. Envia notificação quando atingir a meta

---

## 📋 Pré-requisitos

- ✅ YBY SEED instalado (veja [Primeiros Passos](01-first-steps.md))
- ✅ Microfone funcional
- ✅ (Opcional) Wearable com sensor de passos

---

## 🚀 Criando a Automação

### Método 1: Por Voz (Recomendado)

**Comando de voz:**

> "Crie um script que conte meus passos diários e me avise quando eu atingir 10 mil passos"

**O que acontece:**

1. YBY SEED transcreve sua voz
2. Analisa a intenção (monitor de passos)
3. Gera código Python
4. Salva em `examples/steps_tracker.py`

### Método 2: Por Texto (Alternativo)

Se não tiver microfone, use o **Modo Texto**:

```bash
# Abra o terminal do YBY SEED
python src/main.py run

# Digite o comando
"Crie um script que conte meus passos diários e me avise quando eu atingir 10 mil passos"
```

---

## 📄 Código Gerado

O YBY SEED vai criar algo assim:

```python
#!/usr/bin/env python3
"""Monitor de Passos Diários - Gerado por YBY SEED"""

import json
from datetime import datetime
from pathlib import Path

# Configurações
STEPS_FILE = "steps_data.json"
DAILY_GOAL = 10000

def load_steps():
    """Carrega passos do arquivo"""
    if not Path(STEPS_FILE).exists():
        return {"steps": 0, "date": datetime.now().strftime("%Y-%m-%d")}
    
    with open(STEPS_FILE, "r") as f:
        return json.load(f)

def save_steps(data):
    """Salva passos no arquivo"""
    with open(STEPS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def check_goal(current_steps):
    """Verifica se meta foi atingida"""
    return current_steps >= DAILY_GOAL

def send_notification(message):
    """Envia notificação"""
    print(f"🔔 NOTIFICAÇÃO: {message}")

def main():
    """Função principal"""
    print("👟 Monitor de Passos Diários")
    print(f"🎯 Meta: {DAILY_GOAL} passos\n")
    
    # Carrega passos
    data = load_steps()
    current_steps = data["steps"]
    
    # Simula leitura (substitua por dados reais do wearable)
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
```

---

## 🧪 Testando a Automação

### Passo 1: Execute o Script

```bash
cd examples
python steps_tracker.py
```

### Passo 2: Interaja

O script vai pedir:

```
Quantos passos você deu hoje? 
```

**Digite um número** (ex: 5000)

### Passo 3: Veja o Resultado

**Saída esperada:**

```
👟 Monitor de Passos Diários
🎯 Meta: 10000 passos

Quantos passos você deu hoje? 5000

📊 Progresso: 5000/10000 passos
📈 Faltam: 5000 passos

🔔 NOTIFICAÇÃO: 💪 Você está a 5000 passos da sua meta!
```

---

## 🔧 Personalizando

### Mudar a Meta

Edite o arquivo `steps_tracker.py`:

```python
# Mude de 10000 para 15000
DAILY_GOAL = 15000
```

### Adicionar Notificação Real

Substitua a função `send_notification`:

```python
import subprocess

def send_notification(message):
    """Envia notificação do Ubuntu"""
    subprocess.run(["notify-send", "Monitor de Passos", message])
```

### Conectar Wearable Real

Se tiver um wearable (ex: Xiaomi Mi Band), use a biblioteca `miband`:

```python
from miband import MiBand

def get_real_steps():
    """Lê passos reais do wearable"""
    band = MiBand("MAC_ADDRESS")
    data = band.get_steps()
    return data["steps"]
```

---

## 📊 Entendendo o Código

### Estrutura do Script

```python
# 1. Imports
import json
from datetime import datetime
from pathlib import Path

# 2. Configurações
STEPS_FILE = "steps_data.json"
DAILY_GOAL = 10000

# 3. Funções
def load_steps():
    ...

def save_steps(data):
    ...

def check_goal(current_steps):
    ...

def send_notification(message):
    ...

def main():
    ...

# 4. Ponto de entrada
if __name__ == "__main__":
    main()
```

### Por Que Essa Estrutura?

- **Imports:** Traz funcionalidades prontas (JSON, datas, arquivos)
- **Configurações:** Facilita mudar valores sem mexer no código
- **Funções:** Divide o problema em partes menores
- **`if __name__ == "__main__":`** Garante que o script só roda quando chamado diretamente

---

## 🎯 Desafios

Tente melhorar o script:

1. **Fácil:** Mude a meta para 15.000 passos
2. **Médio:** Adicione notificação por email
3. **Difícil:** Conecte com API do Google Fit

---

## 📚 Próximos Passos

1. **[Comandos de Voz](03-voice-commands.md)** - Configure microfone
2. **[Personalizando Modelos](04-custom-models.md)** - Troque modelos de IA
3. **[Integrações com APIs](05-api-integrations.md)** - Conecte serviços externos

---

**Parabéns!** Você criou sua primeira automação. 🎉

**Próximo tutorial:** [Comandos de Voz](03-voice-commands.md)
