#!/usr/bin/env python3
"""
Validador de Skills - YBY SEED

Valida versionamento, metadados e integridade de skills.

Uso:
    python scripts/validate_skills.py
    python scripts/validate_skills.py skills/backup-automation
"""

import yaml
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple


class SkillValidator:
    """Valida skills do YBY SEED"""
    
    VERSION_PATTERN = r"^\d+\.\d+\.\d+$"
    DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
    
    REQUIRED_FIELDS = [
        "name",
        "version",
        "min_agent_version",
        "last_updated",
        "description",
        "license"
    ]
    
    def __init__(self, skills_dir: str = "skills"):
        self.skills_dir = Path(skills_dir)
        self.errors = []
        self.warnings = []
        self.successes = []
    
    def validate_all(self) -> bool:
        """Valida todas as skills"""
        
        print("=" * 60)
        print("🔍 VALIDADOR DE SKILLS - YBY SEED")
        print("=" * 60)
        print()
        
        if not self.skills_dir.exists():
            print(f"❌ Diretório não encontrado: {self.skills_dir}")
            return False
        
        # Encontra todas as skills
        skill_dirs = [d for d in self.skills_dir.iterdir() if d.is_dir()]
        
        print(f"📚 {len(skill_dirs)} skills encontradas\n")
        
        # Valida cada skill
        for skill_dir in skill_dirs:
            skill_md = skill_dir / "SKILL.md"
            
            if skill_md.exists():
                self._validate_skill(skill_md)
            else:
                self.errors.append(f"{skill_dir.name}: SKILL.md não encontrado")
        
        # Reporta resultados
        self._print_report()
        
        return len(self.errors) == 0
    
    def _validate_skill(self, skill_md: Path):
        """Valida skill individual"""
        
        skill_name = skill_md.parent.name
        print(f"📋 Validando {skill_name}...")
        
        try:
            content = skill_md.read_text(encoding="utf-8")
            
            # Extrai YAML frontmatter
            if not content.startswith("---"):
                self.errors.append(f"{skill_name}: Falta YAML frontmatter")
                return
            
            parts = content.split("---", 2)
            
            if len(parts) < 3:
                self.errors.append(f"{skill_name}: YAML frontmatter mal formado")
                return
            
            yaml_str = parts[1].strip()
            metadata = yaml.safe_load(yaml_str)
            
            # Valida campos obrigatórios
            for field in self.REQUIRED_FIELDS:
                if field not in metadata:
                    self.errors.append(f"{skill_name}: Campo obrigatório faltando: {field}")
            
            # Valida versão
            if "version" in metadata:
                version = metadata["version"]
                
                if not re.match(self.VERSION_PATTERN, str(version)):
                    self.errors.append(
                        f"{skill_name}: Versão inválida '{version}' (deve ser MAJOR.MINOR.PATCH)"
                    )
                else:
                    self.successes.append(f"{skill_name}: Versão {version} ✅")
            
            # Valida min_agent_version
            if "min_agent_version" in metadata:
                version = metadata["min_agent_version"]
                
                if not re.match(self.VERSION_PATTERN, str(version)):
                    self.errors.append(
                        f"{skill_name}: min_agent_version inválido '{version}'"
                    )
            
            # Valida last_updated
            if "last_updated" in metadata:
                date_str = metadata["last_updated"]
                
                if not re.match(self.DATE_PATTERN, str(date_str)):
                    self.errors.append(
                        f"{skill_name}: last_updated inválido '{date_str}' (deve ser YYYY-MM-DD)"
                    )
                else:
                    # Verifica se data não é futura
                    last_updated = datetime.strptime(date_str, "%Y-%m-%d")
                    
                    if last_updated.date() > datetime.now().date():
                        self.warnings.append(
                            f"{skill_name}: last_updated é uma data futura ({date_str})"
                        )
            
            # Valida changelog
            if "changelog" not in metadata:
                self.warnings.append(f"{skill_name}: Sem changelog")
            else:
                changelog = metadata["changelog"]
                
                if not isinstance(changelog, list) or len(changelog) == 0:
                    self.warnings.append(f"{skill_name}: Changelog vazio ou mal formado")
                else:
                    # Valida cada entrada do changelog
                    for entry in changelog:
                        if "version" not in entry or "changes" not in entry:
                            self.warnings.append(
                                f"{skill_name}: Entrada de changelog sem version ou changes"
                            )
            
            # Valida keywords
            if "keywords" not in metadata:
                self.warnings.append(f"{skill_name}: Sem keywords (recomendado para busca)")
            elif not isinstance(metadata["keywords"], list):
                self.errors.append(f"{skill_name}: keywords deve ser uma lista")
            
            # Valida authors
            if "authors" not in metadata:
                self.warnings.append(f"{skill_name}: Sem authors (recomendado)")
            elif not isinstance(metadata["authors"], list):
                self.errors.append(f"{skill_name}: authors deve ser uma lista")
            
            print(f"  ✅ Validação concluída")
        
        except yaml.YAMLError as e:
            self.errors.append(f"{skill_name}: Erro ao parse YAML: {e}")
        except Exception as e:
            self.errors.append(f"{skill_name}: Erro inesperado: {e}")
    
    def _print_report(self):
        """Imprime relatório de validação"""
        
        print()
        print("=" * 60)
        print("📊 RELATÓRIO DE VALIDAÇÃO")
        print("=" * 60)
        print()
        
        # Sucessos
        if self.successes:
            print(f"✅ SUCESSOS ({len(self.successes)}):")
            for success in self.successes:
                print(f"   {success}")
            print()
        
        # Warnings
        if self.warnings:
            print(f"⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   {warning}")
            print()
        
        # Errors
        if self.errors:
            print(f"❌ ERROS ({len(self.errors)}):")
            for error in self.errors:
                print(f"   {error}")
            print()
        
        # Resumo
        print("-" * 60)
        print(f"Total: {len(self.successes) + len(self.warnings) + len(self.errors)} verificações")
        print(f"Sucesso: {len(self.successes)}")
        print(f"Warnings: {len(self.warnings)}")
        print(f"Erros: {len(self.errors)}")
        print()
        
        if self.errors:
            print("❌ Validação FALHOU - Corrija os erros acima")
            return False
        elif self.warnings:
            print("⚠️  Validação PASSOU com warnings")
            return True
        else:
            print("✅ Validação PASSOU com sucesso!")
            return True


if __name__ == "__main__":
    validator = SkillValidator()
    
    # Se argumento passado, valida skill específica
    if len(sys.argv) > 1:
        skill_path = Path(sys.argv[1])
        
        if skill_path.exists():
            validator._validate_skill(skill_path)
            validator._print_report()
        else:
            print(f"❌ Skill não encontrada: {skill_path}")
            sys.exit(1)
    else:
        # Valida todas
        success = validator.validate_all()
        
        sys.exit(0 if success else 1)
