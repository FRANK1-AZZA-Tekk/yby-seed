#!/usr/bin/env python3
"""
Exemplo 3: Backup Automático de PDFs

Este script compacta todos os PDFs de uma pasta e salva como backup.

Como usar:
    python examples/03_backup_automation.py

O que ele faz:
    1. Procura PDFs em uma pasta
    2. Compacta em um arquivo ZIP
    3. Salva backup com data/hora
"""

import os
import zipfile
from datetime import datetime
from pathlib import Path

# Configurações
PDF_FOLDER = "/home/usuario/Documentos/PDFs"
BACKUP_FOLDER = "/home/usuario/Backups"

def find_pdfs(folder):
    """Encontra todos os PDFs em uma pasta"""
    
    pdfs = []
    folder_path = Path(folder)
    
    if not folder_path.exists():
        print(f"❌ Pasta não encontrada: {folder}")
        return pdfs
    
    for file in folder_path.glob("*.pdf"):
        pdfs.append(file)
    
    return pdfs

def create_backup(pdfs, backup_folder):
    """Cria backup ZIP dos PDFs"""
    
    if not pdfs:
        print("❌ Nenhum PDF encontrado para backup")
        return
    
    # Cria pasta de backup se não existir
    backup_path = Path(backup_folder)
    backup_path.mkdir(parents=True, exist_ok=True)
    
    # Nome do arquivo ZIP com data/hora
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_path / f"backup_pdfs_{timestamp}.zip"
    
    # Cria ZIP
    print(f"📦 Criando backup: {backup_file.name}...")
    
    with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for pdf in pdfs:
            zipf.write(pdf, pdf.name)
            print(f"  ✅ Adicionado: {pdf.name}")
    
    print(f"\n✅ Backup criado com sucesso!")
    print(f"📁 Local: {backup_file}")
    print(f"📊 Tamanho: {backup_file.stat().st_size / 1024:.2f} KB")

def main():
    """Função principal"""
    
    print("💾 Backup Automático de PDFs")
    print(f"📂 Pasta: {PDF_FOLDER}\n")
    
    # Encontra PDFs
    pdfs = find_pdfs(PDF_FOLDER)
    
    if not pdfs:
        print("❌ Nenhum PDF encontrado")
        return
    
    print(f"📄 PDFs encontrados: {len(pdfs)}\n")
    
    # Cria backup
    create_backup(pdfs, BACKUP_FOLDER)

if __name__ == "__main__":
    main()
