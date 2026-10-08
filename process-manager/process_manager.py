#!/usr/bin/env python
"""
Process Manager do YBY SEED
Gerencia subprocessos Python persistentes (automações) criados via NL2Code.
"""

import subprocess
import sqlite3
import json
import time
import signal
import sys
import os

# Dicionário de processos ativos: {seed_id: subprocess.Popen}
active_processes = {}

def get_db_connection():
    """Conecta ao banco SQLite do registry."""
    return sqlite3.connect('/opt/yby/registry/yby_seeds.db')

def load_active_seeds():
    """Carrega todas as automações ativas do banco."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, code FROM seeds WHERE status='active'")
    seeds = cursor.fetchall()
    conn.close()
    return seeds

def start_seed(seed_id, code):
    """Inicia subprocesso para uma automação específica."""
    try:
        # Limites de recursos via wrapper
        wrapper = f"""
import resource, sys
resource.setrlimit(resource.RLIMIT_AS, (128 * 1024 * 1024, 128 * 1024 * 1024))  # 128MB RAM
resource.setrlimit(resource.RLIMIT_CPU, (30, 30))  # 30s timeout de CPU

{code}
"""
        proc = subprocess.Popen(
            [sys.executable, "-c", wrapper],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, 'SEED_ID': str(seed_id)}
        )
        active_processes[seed_id] = proc
        print(f"[+] Seed {seed_id} iniciado (PID: {proc.pid})")
        return proc
    except Exception as e:
        print(f"[!] Erro ao iniciar seed {seed_id}: {e}")
        return None

def stop_seed(seed_id):
    """Para e remove um subprocesso ativo."""
    if seed_id in active_processes:
        proc = active_processes[seed_id]
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        del active_processes[seed_id]
        print(f"[-] Seed {seed_id} parado")

def monitor_seeds():
    """Monitora processos e reinicia se morrerem inesperadamente."""
    while True:
        for seed_id, proc in list(active_processes.items()):
            if proc.poll() is not None:  # Processo morreu
                print(f"[!] Seed {seed_id} morreu (código {proc.poll()}). Reiniciando...")
                # Recarrega código do banco
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT code FROM seeds WHERE id=?", (seed_id,))
                result = cursor.fetchone()
                conn.close()
                
                if result:
                    code = result[0]
                    start_seed(seed_id, code)
                else:
                    print(f"[!] Seed {seed_id} não encontrada no banco. Removendo.")
                    del active_processes[seed_id]
        
        time.sleep(5)

def shutdown(signum, frame):
    """Desliga todos os processos gracefulmente."""
    print("[!] Shutting down process manager...")
    for seed_id, proc in list(active_processes.items()):
        stop_seed(seed_id)
    sys.exit(0)

if __name__ == "__main__":
    # Registra handlers de sinal
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    
    print("[*] Process Manager do YBY SEED iniciado")
    
    # Carrega seeds ativos ao iniciar
    active_seeds = load_active_seeds()
    print(f"[*] Carregando {len(active_seeds)} seeds ativas...")
    
    for seed_id, code in active_seeds:
        start_seed(seed_id, code)
    
    print("[*] Iniciando monitoramento...")
    monitor_seeds()
