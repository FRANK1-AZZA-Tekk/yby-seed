#!/usr/bin/env python
"""
Security Linter do YBY SEED
Valida código Python gerado por IA antes da execução.
"""

import ast

# Padrões perigosos que devem ser bloqueados
DANGEROUS_PATTERNS = [
    "os.system",
    "os.popen",
    "subprocess.call",
    "subprocess.run",
    "subprocess.Popen",
    "shutil.rmtree",
    "eval(",
    "exec(",
    "__import__",
    "open(",
    "socket.",
    "http.client",
    "urllib.request",
    "requests.",
]

def check_code(code: str) -> tuple[bool, str]:
    """
    Valida código Python em busca de padrões perigosos.
    
    Retorna:
        (is_safe, message): tuple com status e mensagem de erro
    """
    try:
        tree = ast.parse(code)
        
        for node in ast.walk(tree):
            # Verifica chamadas de função
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    # Constrói nome completo (ex.: "os.system")
                    if hasattr(node.func.value, 'id'):
                        full_name = f"{node.func.value.id}.{node.func.attr}"
                    else:
                        full_name = node.func.attr
                    
                    # Verifica contra padrões perigosos
                    if any(pattern.split('.')[0] in full_name for pattern in DANGEROUS_PATTERNS):
                        return False, f"Padrão perigoso detectado: {full_name}"
                
                # Verifica builtins perigosos (eval, exec, __import__)
                elif isinstance(node.func, ast.Name):
                    if node.func.id in ['eval', 'exec', '__import__', 'open']:
                        return False, f"Builtin perigoso detectado: {node.func.id}()"
        
        return True, "Código seguro"
    
    except SyntaxError as e:
        return False, f"Erro de sintaxe: {e}"
    except Exception as e:
        return False, f"Erro na validação: {e}"

if __name__ == "__main__":
    # Teste rápido
    test_code = """
import paho.mqtt.client as mqtt

def on_message(client, userdata, msg):
    bpm = json.loads(msg.payload)['bpm']
    if bpm > 120:
        client.publish('yby/alert', '{"message":"BPM elevado!"}')
"""
    
    is_safe, message = check_code(test_code)
    print(f"Safe: {is_safe}, Message: {message}")
