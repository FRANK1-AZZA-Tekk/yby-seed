---
name: file-operations
description: Operações com arquivos: ler, escrever, copiar, mover, renomear, deletar, listar, buscar por padrão
compatibility: ubuntu, python-3.11+, os, shutil, pathlib, fnmatch
license: MIT
---

## Quando Usar

Use esta skill quando o usuário pedir para:

- "Ler arquivo de texto"
- "Copiar arquivos de uma pasta"
- "Mover PDFs para backup"
- "Renomear arquivos em lote"
- "Deletar arquivos temporários"
- "Listar arquivos por extensão"
- "Buscar arquivos por padrão"

## Instruções Passo a Passo

### 1. Coletar Requisitos

Pergunte ao usuário:

1. **Operação**? (ler, escrever, copiar, mover, renomear, deletar, listar, buscar)
2. **Arquivos/pastas**? (caminhos de origem e destino)
3. **Filtro**? (extensão, padrão, data, tamanho)
4. **Ação em erro**? (ignorar, parar, logar)

### 2. Template Base

```python
#!/usr/bin/env python3
"""Operações com Arquivos - Gerado por YBY SEED"""

import os
import shutil
from pathlib import Path
import fnmatch

# Operações Básicas

def read_file(filepath: str) -> str:
    """Lê arquivo de texto"""
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

def write_file(filepath: str, content: str):
    """Escreve em arquivo de texto"""
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def copy_file(source: str, dest: str):
    """Copia arquivo"""
    
    shutil.copy2(source, dest)
    print(f"📋 Copiado: {source} → {dest}")

def move_file(source: str, dest: str):
    """Move arquivo"""
    
    shutil.move(source, dest)
    print(f"➡️  Movido: {source} → {dest}")

def rename_file(old_name: str, new_name: str):
    """Renomeia arquivo"""
    
    os.rename(old_name, new_name)
    print(f"🏷️  Renomeado: {old_name} → {new_name}")

def delete_file(filepath: str):
    """Deleta arquivo"""
    
    os.remove(filepath)
    print(f"🗑️  Deletado: {filepath}")

# Operações em Lote

def copy_files_pattern(source_dir: str, dest_dir: str, pattern: str):
    """Copia arquivos por padrão"""
    
    Path(dest_dir).mkdir(parents=True, exist_ok=True)
    
    for file in Path(source_dir).glob(pattern):
        if file.is_file():
            shutil.copy2(file, Path(dest_dir) / file.name)
            print(f"📋 Copiado: {file.name}")

def move_files_extension(source_dir: str, dest_dir: str, extension: str):
    """Move arquivos por extensão"""
    
    Path(dest_dir).mkdir(parents=True, exist_ok=True)
    
    for file in Path(source_dir).glob(f"*.{extension}"):
        if file.is_file():
            shutil.move(file, Path(dest_dir) / file.name)
            print(f"➡️  Movido: {file.name}")

def delete_files_older_than(directory: str, days: int):
    """Deleta arquivos mais antigos que N dias"""
    
    from datetime import datetime, timedelta
    
    cutoff = datetime.now() - timedelta(days=days)
    
    for file in Path(directory).iterdir():
        if file.is_file():
            mtime = datetime.fromtimestamp(file.stat().st_mtime)
            
            if mtime < cutoff:
                file.unlink()
                print(f"🗑️  Deletado: {file.name}")

# Listagem e Busca

def list_files(directory: str, pattern: str = "*") -> list:
    """Lista arquivos por padrão"""
    
    return [str(f) for f in Path(directory).glob(pattern) if f.is_file()]

def find_files_by_size(directory: str, min_size_mb: float = 0) -> list:
    """Encontra arquivos por tamanho mínimo"""
    
    min_size_bytes = min_size_mb * 1024 * 1024
    
    large_files = []
    
    for file in Path(directory).rglob("*"):
        if file.is_file() and file.stat().st_size > min_size_bytes:
            large_files.append(str(file))
    
    return large_files

def find_duplicate_files(directory: str) -> list:
    """Encontra arquivos duplicados por hash"""
    
    import hashlib
    
    hashes = {}
    duplicates = []
    
    for file in Path(directory).rglob("*"):
        if file.is_file():
            file_hash = hashlib.md5(file.read_bytes()).hexdigest()
            
            if file_hash in hashes:
                duplicates.append((str(file), hashes[file_hash]))
            else:
                hashes[file_hash] = str(file)
    
    return duplicates

if __name__ == "__main__":
    # Exemplo de uso
    files = list_files("/home/usuario/Documentos", "*.pdf")
    print(f"📄 {len(files)} PDFs encontrados")
```

### 3. Operações Comuns

#### Copiar Todos os PDFs

```python
def backup_pdfs(source_dir: str, backup_dir: str):
    """Copia todos os PDFs para backup"""
    
    Path(backup_dir).mkdir(parents=True, exist_ok=True)
    
    pdfs = list_files(source_dir, "*.pdf")
    
    for pdf in pdfs:
        shutil.copy2(pdf, Path(backup_dir) / Path(pdf).name)
    
    print(f"✅ {len(pdfs)} PDFs copiados")
```

#### Renomear em Lote

```python
def rename_files_add_prefix(directory: str, prefix: str, pattern: str = "*"):
    """Adiciona prefixo a arquivos"""
    
    for file in Path(directory).glob(pattern):
        if file.is_file():
            new_name = file.parent / f"{prefix}{file.name}"
            file.rename(new_name)
            print(f"🏷️  Renomeado: {file.name} → {new_name.name}")

# Uso
rename_files_add_prefix("/fotos", "2026_", "*.jpg")
```

#### Limpar Arquivos Temporários

```python
def cleanup_temp_files(directory: str, extensions: list = [".tmp", ".bak", ".old"]):
    """Remove arquivos temporários"""
    
    for ext in extensions:
        for file in Path(directory).rglob(f"*{ext}"):
            if file.is_file():
                file.unlink()
                print(f"🗑️  Removido: {file.name}")

# Uso
cleanup_temp_files("/home/usuario", [".tmp", ".bak", ".log"])
```

#### Organizar por Extensão

```python
def organize_files_by_extension(directory: str):
    """Organiza arquivos em pastas por extensão"""
    
    for file in Path(directory).iterdir():
        if file.is_file():
            ext = file.suffix.lstrip('.') or "sem_extensao"
            ext_folder = Path(directory) / ext
            
            ext_folder.mkdir(exist_ok=True)
            file.rename(ext_folder / file.name)
            
            print(f"📁 Movido: {file.name} → {ext}/")

# Uso
organize_files_by_extension("/downloads")
```

### 4. Tratamento de Erros

```python
def safe_copy_file(source: str, dest: str) -> bool:
    """Copia arquivo com tratamento de erros"""
    
    try:
        if not Path(source).exists():
            print(f"❌ Arquivo não encontrado: {source}")
            return False
        
        shutil.copy2(source, dest)
        print(f"✅ Copiado: {source} → {dest}")
        return True
    
    except PermissionError:
        print(f"❌ Permissão negada: {source}")
        return False
    
    except Exception as e:
        print(f"❌ Erro ao copiar: {e}")
        return False
```

### 5. Operações Seguras

```python
def safe_delete_file(filepath: str, dry_run: bool = True):
    """Deleta arquivo com segurança (dry-run opcional)"""
    
    if not Path(filepath).exists():
        print(f"⚠️  Arquivo não existe: {filepath}")
        return
    
    if dry_run:
        print(f"🔍 [DRY-RUN] Deletaria: {filepath}")
        return
    
    # Confirmação para arquivos grandes
    file_size = Path(filepath).stat().st_size / (1024 * 1024)  # MB
    
    if file_size > 100:  # > 100MB
        confirm = input(f"⚠️  Tem certeza que quer deletar {filepath} ({file_size:.1f} MB)? [y/N]: ")
        
        if confirm.lower() != 'y':
            print("❌ Cancelado")
            return
    
    # Deleta
    Path(filepath).unlink()
    print(f"✅ Deletado: {filepath}")
```

## Exemplos

### Exemplo 1: Listar PDFs

**Input:**

> "Listar todos os PDFs da pasta Documentos"

**Output:**

```python
#!/usr/bin/env python3
from pathlib import Path

pdfs = list(Path("/home/usuario/Documentos").glob("*.pdf"))

print(f"📄 {len(pdfs)} PDFs:")
for pdf in pdfs:
    print(f"  - {pdf.name}")
```

### Exemplo 2: Copiar Imagens

**Input:**

> "Copiar todas as imagens JPG para pasta backup"

**Output:**

```python
#!/usr/bin/env python3
import shutil
from pathlib import Path

backup_dir = Path("/backup/imagens")
backup_dir.mkdir(parents=True, exist_ok=True)

for jpg in Path("/fotos").glob("*.jpg"):
    shutil.copy2(jpg, backup_dir / jpg.name)

print(f"✅ {len(list(Path('/fotos').glob('*.jpg')))} imagens copiadas")
```

### Exemplo 3: Renomear em Lote

**Input:**

> "Adicionar '2026_' no início de todos os arquivos"

**Output:**

```python
#!/usr/bin/env python3
from pathlib import Path

for file in Path("/documentos").glob("*"):
    if file.is_file():
        new_name = file.parent / f"2026_{file.name}"
        file.rename(new_name)

print("✅ Arquivos renomeados")
```

### Exemplo 4: Limpar Temporários

**Input:**

> "Deletar todos os arquivos .tmp e .bak"

**Output:**

```python
#!/usr/bin/env python3
from pathlib import Path

for ext in [".tmp", ".bak"]:
    for file in Path("/home/usuario").rglob(f"*{ext}"):
        file.unlink()

print("✅ Arquivos temporários removidos")
```

## Edge Cases

### 1. Arquivo em Uso

```python
def is_file_in_use(filepath: str) -> bool:
    """Verifica se arquivo está em uso"""
    
    try:
        # Tenta abrir para escrita
        with open(filepath, 'a'):
            pass
        return False
    
    except (IOError, PermissionError):
        return True

# Uso
if is_file_in_use("arquivo.txt"):
    print("⚠️  Arquivo em uso, não posso deletar")
else:
    Path("arquivo.txt").unlink()
```

### 2. Sem Espaço em Disco

```python
import shutil

def check_disk_space(path: str, required_gb: float = 1.0) -> bool:
    """Verifica se há espaço suficiente"""
    
    total, used, free = shutil.disk_usage(path)
    free_gb = free / (1024 ** 3)
    
    if free_gb < required_gb:
        print(f"⚠️  Espaço insuficiente: {free_gb:.1f} GB livres (precisa de {required_gb} GB)")
        return False
    
    return True
```

### 3. Permissões

```python
def check_write_permission(directory: str) -> bool:
    """Verifica se tem permissão de escrita"""
    
    test_file = Path(directory) / ".write_test"
    
    try:
        test_file.touch()
        test_file.unlink()
        return True
    
    except PermissionError:
        print(f"❌ Sem permissão de escrita em: {directory}")
        return False
```

## Referências

- [pathlib](https://docs.python.org/3/library/pathlib.html)
- [shutil](https://docs.python.org/3/library/shutil.html)
- [os module](https://docs.python.org/3/library/os.html)
- [fnmatch](https://docs.python.org/3/library/fnmatch.html)

## Scripts

- `scripts/file_organizer.py` - Organiza arquivos por extensão
- `scripts/find_duplicates.py` - Encontra arquivos duplicados
- `scripts/cleanup_temp.py` - Limpa arquivos temporários
