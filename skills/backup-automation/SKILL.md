---
name: backup-automation
description: Cria scripts de backup automático para arquivos e pastas, incluindo compactação ZIP, agendamento e rotação de backups antigos
compatibility: ubuntu, python-3.11+, shutil, zipfile, schedule
license: MIT
---

## Quando Usar

Use esta skill quando o usuário pedir para:

- "Fazer backup dos meus arquivos"
- "Criar backup automático"
- "Compactar PDFs antigos"
- "Agendar backup diário/semanal"
- "Manter apenas últimos N backups"

## Instruções Passo a Passo

### 1. Coletar Requisitos

Pergunte ao usuário:

1. **O que** quer fazer backup? (arquivos, pasta específica, tipo de arquivo)
2. **Para onde** quer salvar o backup? (pasta de destino)
3. **Com que frequência**? (diário, semanal, mensal, sob demanda)
4. **Rotação**? (manter últimos N backups, apagar após X dias)
5. **Notificação**? (quer ser avisado após backup?)

### 2. Gerar Script Python

Use o seguinte template:

```python
#!/usr/bin/env python3
"""Backup Automático - Gerado por YBY SEED"""

import shutil
import zipfile
from datetime import datetime
from pathlib import Path
import schedule
import time

# Configurações
SOURCE_FOLDER = "/caminho/origem"
BACKUP_FOLDER = "/caminho/backup"
BACKUP_PREFIX = "backup"
MAX_BACKUPS = 7  # Manter últimos 7 backups

def create_backup():
    """Cria backup ZIP"""
    
    # Gera nome com timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{BACKUP_PREFIX}_{timestamp}.zip"
    backup_path = Path(BACKUP_FOLDER) / backup_name
    
    # Cria pasta de backup se não existir
    Path(BACKUP_FOLDER).mkdir(parents=True, exist_ok=True)
    
    # Compacta arquivos
    print(f"📦 Criando backup: {backup_path}")
    
    with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in Path(SOURCE_FOLDER).glob("**/*"):
            if file.is_file():
                arcname = file.relative_to(SOURCE_FOLDER)
                zipf.write(file, arcname)
    
    print(f"✅ Backup criado: {backup_path.name}")
    
    # Rotação de backups
    rotate_backups()

def rotate_backups():
    """Mantém apenas últimos N backups"""
    
    backups = sorted(Path(BACKUP_FOLDER).glob(f"{BACKUP_PREFIX}_*.zip"))
    
    if len(backups) > MAX_BACKUPS:
        # Remove backups antigos
        for old_backup in backups[:-MAX_BACKUPS]:
            old_backup.unlink()
            print(f"🗑️  Backup antigo removido: {old_backup.name}")

def schedule_backup():
    """Agenda backup"""
    
    schedule.every().day.at("23:00").do(create_backup)
    
    print("🕒 Backup agendado para 23:00 diariamente")
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    # Backup imediato
    create_backup()
    
    # Agendar backups futuros
    schedule_backup()
```

### 3. Personalizar Baseado nos Requisitos

**Backup de PDFs específicos:**

```python
# Filtra apenas PDFs
for file in Path(SOURCE_FOLDER).glob("**/*.pdf"):
    if file.is_file():
        arcname = file.relative_to(SOURCE_FOLDER)
        zipf.write(file, arcname)
```

**Backup com filtro por data:**

```python
# Apenas arquivos modificados nos últimos 7 dias
from datetime import timedelta

cutoff = datetime.now() - timedelta(days=7)

for file in Path(SOURCE_FOLDER).glob("**/*"):
    if file.is_file() and datetime.fromtimestamp(file.stat().st_mtime) > cutoff:
        arcname = file.relative_to(SOURCE_FOLDER)
        zipf.write(file, arcname)
```

**Backup incremental:**

```python
# Verifica se arquivo já existe no backup
import hashlib

def file_hash(filepath):
    with open(filepath, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

# Compara hashes para evitar duplicatas
```

### 4. Adicionar Tratamento de Erros

```python
try:
    create_backup()

except FileNotFoundError as e:
    print(f"❌ Pasta não encontrada: {e}")

except PermissionError as e:
    print(f"❌ Permissão negada: {e}")

except Exception as e:
    print(f"❌ Erro inesperado: {e}")
```

### 5. Adicionar Notificação (Opcional)

```python
import subprocess

def send_notification(message):
    """Envia notificação do Ubuntu"""
    subprocess.run(["notify-send", "Backup", message])

# Após backup
send_notification(f"✅ Backup criado: {backup_path.name}")
```

## Exemplos

### Exemplo 1: Backup Simples de Pasta

**Input:**

> "Fazer backup da pasta Documentos"

**Output:**

```python
#!/usr/bin/env python3
SOURCE_FOLDER = "/home/usuario/Documentos"
BACKUP_FOLDER = "/home/usuario/Backups"

create_backup()
```

### Exemplo 2: Backup Agendado de PDFs

**Input:**

> "Backup automático dos meus PDFs toda noite às 23h"

**Output:**

```python
#!/usr/bin/env python3
SOURCE_FOLDER = "/home/usuario/Documentos"
BACKUP_FOLDER = "/home/usuario/Backups"

schedule.every().day.at("23:00").do(create_backup)
```

### Exemplo 3: Backup com Rotação

**Input:**

> "Backup semanal, manter apenas últimos 4"

**Output:**

```python
#!/usr/bin/env python3
MAX_BACKUPS = 4

schedule.every().week.do(create_backup)
```

## Edge Cases

### 1. Pasta de Origem Não Existe

```python
if not Path(SOURCE_FOLDER).exists():
    print(f"❌ Pasta não encontrada: {SOURCE_FOLDER}")
    sys.exit(1)
```

### 2. Sem Espaço em Disco

```python
import shutil

total, used, free = shutil.disk_usage(BACKUP_FOLDER)

if free < 1024 * 1024 * 1024:  # Menos de 1GB livre
    print("⚠️  Espaço em disco insuficiente")
    sys.exit(1)
```

### 3. Arquivos em Uso

```python
import psutil

def is_file_in_use(filepath):
    for proc in psutil.process_iter():
        try:
            for p in proc.open_files():
                if p.path == str(filepath):
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False

# Pula arquivos em uso
if is_file_in_use(file):
    print(f"⚠️  Arquivo em uso, pulando: {file}")
    continue
```

## Referências

- [Python zipfile](https://docs.python.org/3/library/zipfile.html)
- [Python shutil](https://docs.python.org/3/library/shutil.html)
- [schedule library](https://schedule.readthedocs.io/)
- [psutil](https://psutil.readthedocs.io/)

## Scripts

- `scripts/create_backup.py` - Script reutilizável para backup
- `scripts/rotate_backups.py` - Script para rotação de backups
- `scripts/check_disk_space.py` - Verifica espaço em disco

## Assets

- `assets/backup_template.py` - Template base para scripts de backup
- `assets/cron_examples.txt` - Exemplos de cron jobs para agendamento
