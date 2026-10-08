---
name: data-processing
version: 1.0.0
min_agent_version: 2.0.0
last_updated: 2026-10-08
description: Processa dados de arquivos CSV, JSON, Excel, TXT - incluindo leitura, transformação, filtragem, exportação, converter formatos, calcular estatísticas, agrupar dados, analisar informações
compatibility: ubuntu, python-3.11+, csv, json, pandas
license: MIT
authors:
  - "Alisson Faria (@FRANK1-AZZA-Tekk)"
keywords:
  - CSV
  - JSON
  - Excel
  - TXT
  - processar
  - dados
  - ler
  - arquivo
  - filtrar
  - converter
  - transformar
  - exportar
  - estatísticas
  - agrupar
  - analisar
  - planilha
  - tabela
  - pandas
changelog:
  - version: 1.0.0
    date: 2026-10-08
    changes:
      - "Versão inicial da skill de processamento de dados"
      - "Suporte a CSV, JSON, Excel, TXT"
      - "Operações de leitura, filtragem, transformação, exportação"
      - "Cálculo de estatísticas básicas (média, soma, min, max)"
      - "Agrupamento de dados por coluna"
      - "Conversão entre formatos (CSV↔JSON)"
      - "Tratamento de encoding e edge cases"
---

## Quando Usar

Use esta skill quando o usuário pedir para:

- "Ler arquivo CSV e extrair colunas"
- "Converter JSON para CSV"
- "Filtrar dados de uma planilha"
- "Contar linhas de um arquivo"
- "Agrupar dados por categoria"
- "Calcular estatísticas de vendas"
- "Processar dados de Excel"

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

#### Calcular Estatísticas

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

## Tests

```bash
# Testar skill
python -m pytest tests/skills/test_data_processing.py -v

# Testar com dados reais
python scripts/csv_stats.py dados.csv
```
