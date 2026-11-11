# Contribuindo para o YBY SEED

Primeiramente, obrigado por considerar contribuir com o YBY SEED! ❤️

**Guia atual do v1 (PC Hub):** [docs/DEV.md](docs/DEV.md) — setup, CLI, variáveis, pastas e testes (`ruff check .` + `pytest -q`). Onde programar e o que *não* mesclar: [docs/REPOS.md](docs/REPOS.md).

Este projeto e todos os participantes são regidos pelo [Código de Conduta](CODE_OF_CONDUCT.md). Ao participar, você deve uphold este código.

> Trechos abaixo sobre `wearable/`, mkdocs e pastas `getting-started/` são históricos. Ignore-os em favor de `docs/DEV.md`.

## 🚀 Como Contribuir

### 1. Reportar Bugs

Bugs são rastreados como [GitHub Issues](https://github.com/FRANK1-AZZA-Tekk/yby-seed/issues).

**Antes de reportar:**
- [ ] Verifique se o bug já foi reportado
- [ ] Teste na última versão (`main` branch)
- [ ] Colete informações: logs, versão do Docker, hardware

**Ao reportar, inclua:**
- Descrição clara do bug
- Passos para reproduzir
- Comportamento esperado vs. atual
- Logs de erro (se aplicável)
- Hardware e versões (Ubuntu, Docker, etc.)

### 2. Sugerir Features

Features são rastreadas como [GitHub Issues](https://github.com/FRANK1-AZZA-Tekk/yby-seed/issues).

**Antes de sugerir:**
- [ ] Verifique se a feature já existe
- [ ] Explique o caso de uso
- [ ] Descreva benefícios e trade-offs

### 3. Pull Requests

**Fluxo de trabalho:**

```bash
# 1. Fork o repositório
git clone https://github.com/SEU-USUARIO/yby-seed.git

# 2. Crie uma branch
git checkout -b feature/minha-feature

# 3. Faça suas mudanças e teste
git add .
git commit -m "feat: adiciona minha feature"

# 4. Push para sua fork
git push origin feature/minha-feature

# 5. Abra um Pull Request
```

**Checklist de PR:**

- [ ] Código segue padrões do projeto (PEP 8 para Python)
- [ ] Testes adicionados/atualizados (se aplicável)
- [ ] Documentação atualizada (README, docs/)
- [ ] Mensagem de commit clara e descritiva
- [ ] PR descreve mudanças e motivação

### 4. Padrões de Código

**Python:**
- Siga [PEP 8](https://pep8.org/)
- Use type hints (`def func(x: int) -> str:`)
- Docstrings no formato Google
- Testes com pytest

**YAML (Docker, etc.):**
- Indentação com 2 espaços
- Chaves ordenadas alfabeticamente (se possível)

**Markdown:**
- Títulos com `#`, `##`, `###`
- Listas com `-` ou `*`
- Código com ```python, ```bash, etc.

### 5. Testes

**Rodar testes locais (vigente):**

```bash
ruff check .
pytest -q
```

**CI/CD:** GitHub Actions roda `ruff` e `pytest` em push e pull request.

### 6. Documentação

**Estrutura:**

```
docs/
├── getting-started/    # Instalação, quickstart
├── architecture/       # Diagramas, componentes
├── development/        # Setup, testing, contributing
├── api/                # MQTT topics, REST API
├── examples/           # Automações de exemplo
└── research/           # Citation, papers
```

**Atualizar docs:**

```bash
# Build local
cd docs && mkdocs build

# Serve local
cd docs && mkdocs serve

# Acesse http://localhost:8000
```

## 📋 Áreas que Precisam de Ajuda

- [ ] **Testes E2E:** Simulação completa (wearable → mobile → server)
- [ ] **Documentação:** Traduções (espanhol, francês)
- [ ] **Firmware ESP32:** Otimização de energia, BLE
- [ ] **UI/UX:** Interface TUI (Textual) mais amigável
- [ ] **Papers Acadêmicos:** Escrita, revisão, submissão

## 🔒 Segurança

**NÃO reporte vulnerabilidades em issues públicas.**

Envie um email para: alissonfaria4@gmail.com com:
- Descrição da vulnerabilidade
- Passos para reproduzir
- Impacto potencial
- Sugestão de fix (se tiver)

Responderemos em até 48h.

## 🎓 Reconhecimento

Contribuidores serão listados em:
- [README.md](README.md) (seção "Contributors")
- [docs/research/citation.md](docs/research/citation.md)
- Papers acadêmicos derivados

## ❓ Dúvidas?

Abra uma [Discussion](https://github.com/FRANK1-AZZA-Tekk/yby-seed/discussions) ou email: alissonfaria4@gmail.com

---

Obrigado por contribuir! 🚀

**YBY SEED** - _Function Over Form_
