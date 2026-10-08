---
name: notification-system
version: 1.0.0
min_agent_version: 2.0.0
last_updated: 2026-10-08
description: Envia notificações por email, Telegram, Slack, WhatsApp ou notificações do sistema Ubuntu notify-send, alertas, mensagens, avisos, comunicar, informar usuário
compatibility: ubuntu, python-3.11+, smtplib, requests
license: MIT
authors:
  - "Alisson Faria (@FRANK1-AZZA-Tekk)"
keywords:
  - notificação
  - email
  - Telegram
  - Slack
  - WhatsApp
  - alerta
  - mensagem
  - aviso
  - comunicar
  - informar
  - usuário
  - avisar
  - terminar
  - concluir
  - notificar
  - SMTP
  - webhook
  - bot
changelog:
  - version: 1.0.0
    date: 2026-10-08
    changes:
      - "Versão inicial da skill de notificações"
      - "Suporte a email (SMTP), Telegram, Slack, WhatsApp"
      - "Notificações do sistema Ubuntu (notify-send)"
      - "Templates de notificação personalizáveis"
      - "Tratamento de erros de autenticação e envio"
      - "Cooldown para evitar spam de notificações"
---

## Quando Usar

Use esta skill quando o usuário pedir para:

- "Me avisar quando terminar"
- "Enviar email de notificação"
- "Mandar mensagem no Telegram"
- "Notificar no Slack"
- "Alerta por WhatsApp"
- "Avisar quando backup concluir"

## Instruções Passo a Passo

### 1. Coletar Requisitos

Pergunte ao usuário:

1. **Canal de notificação**? (email, Telegram, Slack, WhatsApp, sistema)
2. **Destinatário**? (email, chat_id, canal)
3. **Conteúdo**? (mensagem, título, corpo)
4. **Gatilho**? (quando enviar: ao terminar, ao falhar, agendado)

### 2. Template Base

```python
#!/usr/bin/env python3
"""Sistema de Notificações - Gerado por YBY SEED"""

import smtplib
import requests
import subprocess
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configurações
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "seu_email@gmail.com"
SMTP_PASS = "SUA_SENHA_OU_APP_PASSWORD"

TELEGRAM_BOT_TOKEN = "SEU_BOT_TOKEN"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID"

def send_email(to_email: str, subject: str, body: str):
    """Envia email via SMTP"""
    
    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(SMTP_USER, SMTP_PASS)
    server.send_message(msg)
    server.quit()
    
    print(f"✅ Email enviado para {to_email}")

def send_telegram(text: str, chat_id: str = None):
    """Envia mensagem para Telegram"""
    
    if not chat_id:
        chat_id = TELEGRAM_CHAT_ID
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    
    response = requests.post(url, json=data)
    response.raise_for_status()
    
    print("✅ Mensagem enviada no Telegram")

def send_system_notification(title: str, message: str):
    """Envia notificação do sistema (Ubuntu)"""
    
    subprocess.run(["notify-send", title, message])
    
    print(f"🔔 Notificação: {title}")

if __name__ == "__main__":
    # Exemplo de uso
    send_system_notification("Teste", "YBY SEED funcionando!")
```

### 3. Notificações por Canal

#### Email (Gmail)

```python
def send_email_gmail(to_email: str, subject: str, body: str):
    """Envia email via Gmail"""
    
    import smtplib
    from email.mime.text import MIMEText
    
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = "seu_email@gmail.com"
    msg['To'] = to_email
    
    server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    server.login("seu_email@gmail.com", "SUA_SENHA")
    server.send_message(msg)
    server.quit()
```

#### Telegram Bot

```python
def send_telegram_message(text: str, bot_token: str, chat_id: str):
    """Envia mensagem para Telegram"""
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    
    response = requests.post(url, json=data)
    
    if response.status_code == 200:
        print("✅ Telegram enviado")
    else:
        print(f"❌ Erro: {response.text}")
```

#### Slack Webhook

```python
def send_slack_message(text: str, webhook_url: str):
    """Envia mensagem para Slack via webhook"""
    
    data = {"text": text}
    
    response = requests.post(webhook_url, json=data)
    
    if response.status_code == 200:
        print("✅ Slack enviado")
    else:
        print(f"❌ Erro: {response.text}")
```

### 4. Notificações Condicionais

```python
def notify_on_success(task_name: str):
    """Notifica ao concluir tarefa"""
    
    send_system_notification("✅ Sucesso", f"{task_name} concluído!")
    send_telegram(f"✅ {task_name} concluído com sucesso!")

def notify_on_failure(task_name: str, error: str):
    """Notifica ao falhar tarefa"""
    
    send_system_notification("❌ Erro", f"{task_name} falhou")
    send_telegram(f"❌ {task_name} falhou:\n{error}")
    send_email("admin@empresa.com", f"Erro: {task_name}", error)
```

## Exemplos

### Exemplo 1: Notificação de Sistema

**Input:**

> "Me avisar quando backup terminar"

**Output:**

```python
#!/usr/bin/env python3
import subprocess

# Após backup
subprocess.run(["notify-send", "Backup", "✅ Backup concluído!"])
```

### Exemplo 2: Email de Relatório

**Input:**

> "Enviar email com relatório de vendas diário"

**Output:**

```python
#!/usr/bin/env python3
import smtplib
from email.mime.text import MIMEText

def send_daily_report():
    msg = MIMEText("Relatório de vendas diário:\n- Total: R$ 15.000\n- Pedidos: 45")
    msg['Subject'] = "Relatório Diário de Vendas"
    msg['From'] = "sistema@empresa.com"
    msg['To'] = "gerente@empresa.com"
    
    server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    server.login("sistema@empresa.com", "SENHA")
    server.send_message(msg)
    server.quit()
```

### Exemplo 3: Alerta Telegram

**Input:**

> "Me avisar no Telegram se temperatura passar de 30°C"

**Output:**

```python
#!/usr/bin/env python3
import requests

temperature = 32  # Simulação

if temperature > 30:
    url = "https://api.telegram.org/botTOKEN/sendMessage"
    data = {
        "chat_id": "CHAT_ID",
        "text": f"⚠️ Alerta: Temperatura alta ({temperature}°C)"
    }
    requests.post(url, json=data)
```

## Edge Cases

### 1. Email Falhou

```python
def safe_send_email(to_email: str, subject: str, body: str):
    try:
        send_email(to_email, subject, body)
    except smtplib.SMTPAuthenticationError:
        print("❌ Erro de autenticação SMTP")
        print("💡 Verifique email e senha")
    except Exception as e:
        print(f"❌ Erro ao enviar email: {e}")
        # Fallback para Telegram
        send_telegram(f"⚠️ Falha no email: {e}")
```

### 2. Telegram Bot Inativo

```python
def check_telegram_bot(bot_token: str) -> bool:
    url = f"https://api.telegram.org/bot{bot_token}/getMe"
    response = requests.get(url)
    
    if response.status_code == 200:
        return True
    else:
        print("❌ Bot Telegram inválido ou inativo")
        return False
```

### 3. Notificação Duplicada

```python
from datetime import datetime, timedelta

last_notification = {}

def notify_with_cooldown(channel: str, message: str, cooldown_minutes: int = 5):
    now = datetime.now()
    
    # Verifica cooldown
    if channel in last_notification:
        elapsed = now - last_notification[channel]
        if elapsed < timedelta(minutes=cooldown_minutes):
            print(f"⏰ Aguardando cooldown ({cooldown_minutes} min)")
            return
    
    # Envia notificação
    if channel == "telegram":
        send_telegram(message)
    
    last_notification[channel] = now
```

## Referências

- [smtplib](https://docs.python.org/3/library/smtplib.html)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Slack Webhooks](https://api.slack.com/messaging/webhooks)
- [Twilio WhatsApp API](https://www.twilio.com/whatsapp)

## Scripts

- `scripts/test_notifications.py` - Testa todos os canais
- `scripts/email_templates.py` - Templates de email
- `scripts/telegram_bot.py` - Bot Telegram simples

## Tests

```bash
# Testar skill
python -m pytest tests/skills/test_notification_system.py -v

# Testar notificação
python scripts/test_notifications.py
```
