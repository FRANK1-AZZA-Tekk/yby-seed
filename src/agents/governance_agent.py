"""
Governance Agent — Governança + validação de segurança

Responsabilidade:
- Bloquear código perigoso (rm -rf, DROP TABLE, etc.)
- Validar permissões de API/DB
- Exigir aprovação humana para ações críticas

Regras Determinísticas:
- DANGEROUS_PATTERNS: Regex para código perigoso
- ALLOWED_IMPORTS: Whitelist de imports seguros
- ACTION_APPROVAL: Ações que exigem aprovação humana

Licença: MIT
"""

import re
from typing import Dict, Any, Tuple, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GovernanceAgent:
    """
    Agente de governança e segurança.
    """
    
    def __init__(self):
        # Padrões perigosos (regex)
        self.dangerous_patterns = [
            r"rm\\s+-rf\\s+/",  # Delete raiz
            r"DROP\\s+TABLE\\s+",  # Delete DB
            r"os\\.system\\s*\\(",  # Shell command
            r"subprocess\\..*shell\\s*=\\s*True",  # Shell injection
            r"eval\\s*\\(",  # Eval injection
            r"exec\\s*\\(",  # Exec injection
            r"__import__\\s*\\(",  # Dynamic import
            r"open\\s*\\([^)]*['\"]/[\\w/]+['\"]",  # Absolute path access
        ]
        
        # Imports permitidos (whitelist)
        self.allowed_imports = [
            "math", "random", "datetime", "time",
            "collections", "itertools", "functools",
            "re", "json", "csv", "typing",
            "dataclasses", "pathlib", "io",
            "string", "textwrap", "unicodedata",
            "zipfile", "tarfile", "shutil",  # Backup
            "paho.mqtt.client",  # MQTT
            "requests", "urllib"  # HTTP (com cuidado)
        ]
        
        # Ações que exigem aprovação humana
        self.action_approval_required = [
            "delete_files",
            "drop_table",
            "execute_shell",
            "send_email_bulk",
            "api_write"
        ]
    
    def check(self, code: str, action: str = "execute") -> Tuple[bool, str]:
        """
        Validar código.
        
        Args:
            code: Código Python para validar
            action: Ação pretendida (ex: "execute", "delete", "send_email")
        
        Returns:
            (is_allowed, reason)
        """
        logger.info(f"🛡️  Validando código (ação: {action})...")
        
        # 1. Verificar padrões perigosos
        for pattern in self.dangerous_patterns:
            if re.search(pattern, code):
                logger.warning(f"❌ Padrão perigoso detectado: {pattern}")
                return False, f"Código perigoso detectado (padrão: {pattern})"
        
        # 2. Verificar imports
        imports = self._extract_imports(code)
        
        for imp in imports:
            if imp not in self.allowed_imports:
                logger.warning(f"⚠️  Import não permitido: {imp}")
                return False, f"Import não permitido: {imp}"
        
        # 3. Verificar ação que exige aprovação
        if action in self.action_approval_required:
            logger.warning(f"⚠️  Ação exige aprovação humana: {action}")
            return False, f"Ação '{action}' exige aprovação humana"
        
        logger.info("✅ Código validado")
        return True, "Aprovado"
    
    def _extract_imports(self, code: str) -> List[str]:
        """
        Extrair imports do código.
        
        Args:
            code: Código Python
        
        Returns:
            Lista de imports
        """
        import ast
        
        imports = []
        
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
        
        except SyntaxError:
            logger.warning("⚠️  Erro de sintaxe ao extrair imports")
        
        return imports
    
    def require_human_approval(self, action: str, context: Dict[str, Any]) -> bool:
        """
        Verificar se ação exige aprovação humana.
        
        Args:
            action: Ação pretendida
            context: Contexto da ação
        
        Returns:
            True se exige aprovação
        """
        # Ações críticas sempre exigem aprovação
        if action in self.action_approval_required:
            return True
        
        # Contexto de risco (ex: produção, dados sensíveis)
        if context.get("environment") == "production":
            return True
        
        if context.get("data_sensitive", False):
            return True
        
        return False
    
    def generate_approval_request(self, action: str, code: str, context: Dict[str, Any]) -> str:
        """
        Gerar solicitação de aprovação humana.
        
        Args:
            action: Ação pretendida
            code: Código a ser executado
            context: Contexto
        
        Returns:
            Mensagem de solicitação
        """
        request = f"""
🛡️  **Solicitação de Aprovação**

**Ação:** {action}

**Código:**
```python
{code}
```

**Contexto:**
- Ambiente: {context.get('environment', 'unknown')}
- Dados sensíveis: {context.get('data_sensitive', False)}
- Impacto: {context.get('impact', 'unknown')}

**Aprovar?** (sim/não)
"""
        return request


# Instância global
governance_agent = GovernanceAgent()


if __name__ == "__main__":
    # Teste
    safe_code = '''
import json
import zipfile

def backup(source, dest):
    with zipfile.ZipFile(dest, 'w') as zipf:
        zipf.write(source)
'''
    
    dangerous_code = '''
import os
os.system("rm -rf /")
'''
    
    is_allowed, reason = governance_agent.check(safe_code, "backup")
    print(f"Safe code: {is_allowed} - {reason}")
    
    is_allowed, reason = governance_agent.check(dangerous_code, "execute")
    print(f"Dangerous code: {is_allowed} - {reason}")
