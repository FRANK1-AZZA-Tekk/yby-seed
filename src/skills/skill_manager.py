#!/usr/bin/env python3
"""
Skill Manager - Gerencia descoberta, ativação e execução de skills

Baseado em: Agent Skills Specification (agentskills.io) e Anthropic Skills

Uso:
    manager = SkillManager()
    manager.discover_skills()
    skill = manager.find_best_skill("fazer backup dos meus arquivos")
    skill.execute()
"""

import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from loguru import logger


@dataclass
class SkillMetadata:
    """Metadados de uma skill"""
    
    name: str
    description: str
    compatibility: str = ""
    license: str = "MIT"
    directory: Path = None
    
    @classmethod
    def from_yaml(cls, yaml_str: str, directory: Path) -> 'SkillMetadata':
        """Cria metadados a partir de YAML frontmatter"""
        
        data = yaml.safe_load(yaml_str)
        
        return cls(
            name=data.get("name", "unknown"),
            description=data.get("description", ""),
            compatibility=data.get("compatibility", ""),
            license=data.get("license", "MIT"),
            directory=directory
        )


class Skill:
    """Representa uma skill completa"""
    
    def __init__(self, metadata: SkillMetadata, content: str):
        self.metadata = metadata
        self.content = content
        self.instructions = self._parse_instructions(content)
        
        logger.debug(f"Skill carregada: {metadata.name}")
    
    def _parse_instructions(self, content: str) -> Dict[str, Any]:
        """Parse do conteúdo do SKILL.md"""
        
        # Remove YAML frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2].strip()
        
        # Parse seções
        sections = {}
        current_section = "body"
        
        for line in content.split("\n"):
            if line.startswith("## "):
                current_section = line[3:].strip().lower().replace(" ", "_")
                sections[current_section] = []
            else:
                if current_section not in sections:
                    sections[current_section] = []
                sections[current_section].append(line)
        
        return {
            key: "\n".join(value).strip()
            for key, value in sections.items()
        }
    
    def should_activate(self, user_command: str) -> bool:
        """Verifica se skill deve ser ativada para este comando"""
        
        # Verifica se descrição da skill é relevante para comando
        description_lower = self.metadata.description.lower()
        command_lower = user_command.lower()
        
        # Palavras-chave da descrição
        keywords = description_lower.split()
        
        matches = sum(1 for kw in keywords if kw in command_lower and len(kw) > 3)
        
        # Ativa se pelo menos 2 palavras-chave match
        return matches >= 2
    
    def get_instructions(self) -> str:
        """Retorna instruções da skill"""
        
        return self.instructions.get("body", "")
    
    def get_examples(self) -> str:
        """Retorna exemplos da skill"""
        
        return self.instructions.get("exemplos", "")
    
    def get_scripts(self) -> List[Path]:
        """Retorna scripts da skill"""
        
        if not self.metadata.directory:
            return []
        
        scripts_dir = self.metadata.directory / "scripts"
        
        if scripts_dir.exists():
            return list(scripts_dir.glob("*.py"))
        
        return []


class SkillManager:
    """Gerencia skills do YBY SEED"""
    
    def __init__(self, skills_dir: str = "skills"):
        self.skills_dir = Path(skills_dir)
        self.skills: Dict[str, Skill] = {}
        
        logger.info(f"📚 SkillManager inicializado (diretório: {skills_dir})")
    
    def discover_skills(self):
        """Descobre todas as skills disponíveis"""
        
        logger.info("🔍 Descobrindo skills...")
        
        if not self.skills_dir.exists():
            logger.warning(f"⚠️  Diretório de skills não encontrado: {self.skills_dir}")
            return
        
        # Encontra todos os SKILL.md
        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_md = skill_dir / "SKILL.md"
                
                if skill_md.exists():
                    self._load_skill(skill_md, skill_dir)
        
        logger.info(f"✅ {len(self.skills)} skills descobertas")
    
    def _load_skill(self, skill_md_path: Path, skill_dir: Path):
        """Carrega skill do arquivo SKILL.md"""
        
        content = skill_md_path.read_text(encoding="utf-8")
        
        # Extrai YAML frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            
            if len(parts) >= 3:
                yaml_str = parts[1].strip()
                
                try:
                    metadata = SkillMetadata.from_yaml(yaml_str, skill_dir)
                    skill = Skill(metadata, content)
                    
                    self.skills[metadata.name] = skill
                    
                    logger.debug(f"  📚 Skill carregada: {metadata.name}")
                
                except Exception as e:
                    logger.error(f"  ❌ Erro ao carregar skill {skill_dir.name}: {e}")
    
    def find_best_skill(self, user_command: str) -> Optional[Skill]:
        """Encontra melhor skill para comando do usuário"""
        
        logger.info(f"🔍 Buscando skill para: {user_command[:50]}...")
        
        best_match = None
        best_score = 0
        
        for skill in self.skills.values():
            if skill.should_activate(user_command):
                # Calcula score de match
                score = self._calculate_match_score(skill, user_command)
                
                if score > best_score:
                    best_score = score
                    best_match = skill
        
        if best_match:
            logger.info(f"✅ Skill encontrada: {best_match.metadata.name} (score: {best_score})")
        else:
            logger.warning("⚠️  Nenhuma skill encontrada")
        
        return best_match
    
    def _calculate_match_score(self, skill: Skill, user_command: str) -> float:
        """Calcula score de match entre skill e comando"""
        
        score = 0.0
        
        # Match na descrição (peso: 3)
        description_words = skill.metadata.description.lower().split()
        command_words = user_command.lower().split()
        
        description_matches = sum(1 for word in description_words if word in command_words and len(word) > 3)
        score += description_matches * 3
        
        # Match em "Quando Usar" (peso: 2)
        when_use = skill.instructions.get("quando_usar", "").lower()
        
        if when_use:
            when_use_words = when_use.split()
            when_use_matches = sum(1 for word in when_use_words if word in command_words and len(word) > 3)
            score += when_use_matches * 2
        
        # Match em exemplos (peso: 1)
        examples = skill.instructions.get("exemplos", "").lower()
        
        if examples:
            examples_words = examples.split()
            examples_matches = sum(1 for word in examples_words if word in command_words and len(word) > 3)
            score += examples_matches * 1
        
        return score
    
    def list_skills(self) -> List[Dict[str, str]]:
        """Lista todas as skills disponíveis"""
        
        return [
            {
                "name": skill.metadata.name,
                "description": skill.metadata.description,
                "compatibility": skill.metadata.compatibility
            }
            for skill in self.skills.values()
        ]
    
    def get_skill(self, name: str) -> Optional[Skill]:
        """Retorna skill por nome"""
        
        return self.skills.get(name)
    
    def test_skill(self, name: str, test_command: str):
        """Testa skill com comando específico"""
        
        skill = self.get_skill(name)
        
        if not skill:
            print(f"❌ Skill não encontrada: {name}")
            return
        
        print(f"\n🧪 Testando skill: {name}")
        print(f"📝 Comando: {test_command}")
        print(f"\n📊 Metadados:")
        print(f"  Nome: {skill.metadata.name}")
        print(f"  Descrição: {skill.metadata.description}")
        print(f"  Compatibilidade: {skill.metadata.compatibility}")
        print(f"  License: {skill.metadata.license}")
        
        print(f"\n🎯 Should activate: {skill.should_activate(test_command)}")
        print(f"📈 Match score: {self._calculate_match_score(skill, test_command)}")
        
        print(f"\n📚 Instruções:")
        print(skill.get_instructions()[:500] + "...")
    
    def generate_report(self) -> Dict[str, Any]:
        """Gera relatório de skills"""
        
        return {
            "total_skills": len(self.skills),
            "skills": self.list_skills(),
            "directory": str(self.skills_dir),
            "generated_at": __import__("datetime").datetime.now().isoformat()
        }


if __name__ == "__main__":
    # Teste do SkillManager
    manager = SkillManager()
    manager.discover_skills()
    
    print(f"\n📚 {len(manager.skills)} skills carregadas:\n")
    
    for skill_info in manager.list_skills():
        print(f"  • {skill_info['name']}: {skill_info['description'][:60]}...")
    
    # Testa busca
    print("\n\n🔍 Testando busca:")
    
    test_commands = [
        "Fazer backup dos meus arquivos PDF",
        "Buscar previsão do tempo da API",
        "Ler arquivo CSV e filtrar dados",
        "Enviar notificação por email",
        "Copiar arquivos para outra pasta"
    ]
    
    for command in test_commands:
        print(f"\n📝 Comando: {command}")
        
        skill = manager.find_best_skill(command)
        
        if skill:
            print(f"  ✅ Skill: {skill.metadata.name}")
        else:
            print(f"  ❌ Nenhuma skill encontrada")
