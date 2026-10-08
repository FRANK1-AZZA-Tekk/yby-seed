---
name: data-processing
description: Processa dados de arquivos CSV, JSON, Excel, TXT - incluindo leitura, transformação, filtragem e exportação
compatibility: ubuntu, python-3.11+, csv, json, pandas (opcional)
license: MIT
---

## Quando Usar

Use esta skill quando o usuário pedir para:

- "Ler arquivo CSV e extrair colunas"
- "Converter JSON para CSV"
- "Filtrar dados de uma planilha"
- "Contar linhas de um arquivo"
- "Agrupar dados por categoria"

## Instruções Passo a Passo

### 1. Coletar Requisitos

Pergunte ao usuário:

1. **Formato de entrada**? (CSV, JSON, Excel, TXT)
2. **Operação desejada**? (ler, filtrar, agrupar, converter, estatísticas)
3. **Colunas/campos relevantes**? (quais dados processar)
4. **Formato de saída**? (CSV, JSON, console, arquivo)

### 2. Template Base

```python
#!/usr/bin/env python3
"""Processamento de Dados - Gerado por YBY SEED"""

import csv
import json
from pathlib import Path

def read_csv(filepath: str) -> list:
    """Lê arquivo CSV e retorna lista de dicts"""
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)

def read_json(filepath: str) -> dict:
    """Lê arquivo JSON"""
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def write_csv(data: list, filepath: str):
    """Escreve lista de dicts em CSV"""
    
    if not data:
        return
    
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

def write_json(data: dict, filepath: str):
    """Escreve dict em JSON"""
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    # Exemplo de uso
    data = read_csv("dados.csv")
    print(f"📊 {len(data)} linhas lidas")
```

### 3. Operações Comuns

#### Filtrar Dados

```python
def filter_data(data: list, column: str, value) -> list:
    """Filtra dados por coluna e valor"""
    
    return [row for row in data if row[column] == str(value)]

# Uso
clientes_sp = filter_data(data, "cidade", "São Paulo")
```

#### Agrupar Dados

```python
from collections import defaultdict

def group_by(data: list, column: str) -> dict:
    """Agrupa dados por coluna"""
    
    grouped = defaultdict(list)
    
    for row in data:
        key = row[column]
        grouped[key].append(row)
    
    return dict(grouped)

# Uso
por_cidade = group_by(data, "cidade")
```

#### Estatísticas Básicas

```python
def calculate_stats(data: list, column: str) -> dict:
    """Calcula estatísticas de coluna numérica"""
    
    values = [float(row[column]) for row in data if row[column]]
    
    return {
        "count": len(values),
        "sum": sum(values),
        "mean": sum(values) / len(values) if values else 0,
        "min": min(values) if values else 0,
        "max": max(values) if values else 0
    }

# Uso
stats = calculate_stats(data, "valor")
print(f"Média: R$ {stats['mean']:.2f}")
```

#### Converter CSV → JSON

```python
def csv_to_json(csv_path: str, json_path: str):
    """Converte CSV para JSON"""
    
    data = read_csv(csv_path)
    write_json(data, json_path)
    
    print(f"✅ Convertido: {csv_path} → {json_path}")
```

#### Extrair Colunas Específicas

```python
def extract_columns(data: list, columns: list) -> list:
    """Extrai colunas específicas"""
    
    return [{col: row[col] for col in columns} for row in data]

# Uso
nomes_emails = extract_columns(data, ["nome", "email"])
```

### 4. Processamento de Arquivos Grandes

```python
def process_large_csv(filepath: str, chunk_size: int = 1000):
    """Processa CSV grande em chunks"""
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        chunk = []
        for i, row in enumerate(reader):
            chunk.append(row)
            
            if len(chunk) >= chunk_size:
                process_chunk(chunk)
                chunk = []
        
        # Processa último chunk
        if chunk:
            process_chunk(chunk)

def process_chunk(chunk: list):
    """Processa chunk de dados"""
    # Sua lógica aqui
    pass
```

### 5. Tratamento de Erros

```python
def safe_read_csv(filepath: str) -> list:
    """Lê CSV com tratamento de erros"""
    
    try:
        if not Path(filepath).exists():
            print(f"❌ Arquivo não encontrado: {filepath}")
            return []
        
        return read_csv(filepath)
    
    except UnicodeDecodeError:
        print("⚠️  Erro de encoding, tentando latin-1...")
        with open(filepath, 'r', encoding='latin-1') as f:
            return list(csv.DictReader(f))
    
    except Exception as e:
        print(f"❌ Erro ao ler CSV: {e}")
        return []
```

## Exemplos

### Exemplo 1: Contar Linhas de CSV

**Input:**

> "Contar quantas linhas tem o arquivo clientes.csv"

**Output:**

```python
#!/usr/bin/env python3
import csv

with open("clientes.csv", 'r') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print(f"📊 {len(rows)} clientes")
```

### Exemplo 2: Filtrar por Cidade

**Input:**

> "Filtrar apenas clientes de São Paulo"

**Output:**

```python
#!/usr/bin/env python3
import csv

data = []

with open("clientes.csv", 'r') as f:
    reader = csv.DictReader(f)
    data = list(reader)

clientes_sp = [row for row in data if row['cidade'] == 'São Paulo']

print(f"📍 {len(clientes_sp)} clientes em SP")
```

### Exemplo 3: Converter CSV para JSON

**Input:**

> "Converter vendas.csv para JSON"

**Output:**

```python
#!/usr/bin/env python3
import csv
import json

data = []

with open("vendas.csv", 'r') as f:
    reader = csv.DictReader(f)
    data = list(reader)

with open("vendas.json", 'w') as f:
    json.dump(data, f, indent=2)

print("✅ Convertido: vendas.csv → vendas.json")
```

### Exemplo 4: Calcular Total de Vendas

**Input:**

> "Calcular total de vendas por produto"

**Output:**

```python
#!/usr/bin/env python3
import csv
from collections import defaultdict

data = []

with open("vendas.csv", 'r') as f:
    reader = csv.DictReader(f)
    data = list(reader)

total_por_produto = defaultdict(float)

for row in data:
    produto = row['produto']
    valor = float(row['valor'])
    total_por_produto[produto] += valor

for produto, total in total_por_produto.items():
    print(f"{produto}: R$ {total:.2f}")
```

## Edge Cases

### 1. CSV com Encoding Diferente

```python
try:
    data = read_csv(filepath)
except UnicodeDecodeError:
    # Tenta encoding alternativo
    with open(filepath, 'r', encoding='latin-1') as f:
        data = list(csv.DictReader(f))
```

### 2. Coluna Inexistente

```python
def safe_get_column(data: list, column: str, default=""):
    """Extrai coluna, retorna default se não existir"""
    
    if not data or column not in data[0]:
        print(f"⚠️  Coluna '{column}' não encontrada")
        return [default] * len(data)
    
    return [row.get(column, default) for row in data]
```

### 3. Dados Vazios

```python
if not data:
    print("⚠️  Nenhum dado encontrado no arquivo")
    sys.exit(0)
```

## Referências

- [Python csv module](https://docs.python.org/3/library/csv.html)
- [Python json module](https://docs.python.org/3/library/json.html)
- [pandas library](https://pandas.pydata.org/) (opcional para dados complexos)

## Scripts

- `scripts/csv_stats.py` - Estatísticas de CSV
- `scripts/convert_format.py` - Converte entre formatos
- `scripts/filter_data.py` - Filtra dados por critérios
