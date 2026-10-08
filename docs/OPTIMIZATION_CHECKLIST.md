# ✅ Checklist de Otimização do Repositório YBY SEED

Este documento lista todas as melhorias aplicadas ao repositório YBY SEED com base em melhores práticas de 2025-2026 do GitHub, Hugging Face, Zenodo e literatura acadêmica.

---

## 📁 Estrutura do Repositório

### Monorepo (✅ Aplicado)

- [x] **Wearable:** `/wearable/` (firmware ESP32, PlatformIO)
- [x] **Server:** `/server/` (Docker, Ollama, Node-RED, LiteLLM)
- [x] **Mobile:** `/mobile/` (Termux, Python, MQTT)
- [x] **Tests:** `/tests/` (Pytest E2E, MQTT mock)
- [x] **Docs:** `/docs/` (MkDocs, documentação técnica)
- [x] **Examples:** `/examples/` (automações prontas)
- [x] **Scripts:** `/scripts/` (setup, deploy, utilitários)

**Justificativa:** Reprodutibilidade acadêmica, histórico unificado, DOI único, CI/CD integrado.

---

## 📄 Documentação Técnica

### Model Card (✅ Aplicado - Hugging Face Standard)

- [x] **MODEL_CARD.md** com:
  - Model Details (descrição, desenvolvedor, licença)
  - Intended Uses (casos de uso primários e out-of-scope)
  - Architecture (diagrama, componentes)
  - Evaluation (HumanEval, latência, recursos)
  - Limitations (técnicas, segurança, éticas)
  - Training Data (dataset, fine-tuning)
  - Security & Privacy (medidas, considerações)
  - Hardware Requirements (servidor, wearable, mobile)
  - Citation (BibTeX)

**Referência:** [Hugging Face Model Card Guidebook](https://huggingface.co/docs/hub/model-card-guidebook)

### MkDocs (✅ Aplicado)

- [x] **mkdocs.yml** configurado
- [x] **Tema Material** (profissional, acadêmico)
- [x] **Navegação tabular** (getting-started, architecture, development, api, examples, research)
- [x] **Search integrado** (lunr.js)
- [x] **Deploy automático** (GitHub Actions → GitHub Pages)

**Referência:** [MkDocs Material](https://squidfunk.github.io/mkdocs-material/)

---

## 🛡️ Governança e Segurança

### Arquivos de Governança (✅ Aplicado)

- [x] **CONTRIBUTING.md** (como contribuir, padrões de código, testes)
- [x] **CODE_OF_CONDUCT.md** (Contributor Covenant 2.1)
- [x] **SECURITY.md** (política de segurança, reporting, processo)
- [x] **LICENSE** (MIT)
- [x] **CITATION.cff** (citação padrão acadêmica)

**Referência:** [GitHub Best Practices](https://docs.github.com/en/repositories/creating-and-managing-repositories/best-practices-for-repositories)

### Issue Templates (✅ Aplicado)

- [x] **bug_report.md** (descrição, reprodução, logs, hardware)
- [x] **feature_request.md** (problema, solução, caso de uso, impacto)

### Pull Request Template (✅ Aplicado)

- [x] **PULL_REQUEST_TEMPLATE.md** (descrição, tipo, checklist, reviewers)

---

## 🧪 CI/CD e Testes

### GitHub Actions (✅ Aplicado)

- [x] **ci.yml** com:
  - Testes servidor (Python + Pytest + Coverage)
  - Testes wearable (PlatformIO Native)
  - Build Docker images (GHCR)
  - Deploy documentação (MkDocs → GitHub Pages)

### Pre-commit Hooks (✅ Aplicado)

- [x] **.pre-commit-config.yaml** com:
  - Black (formatação Python)
  - Pylint (linting Python)
  - MyPy (type checking)
  - Prettier (YAML formatting)
  - Detect secrets (private keys, AWS credentials)
  - Markdown link check

### Test Coverage (✅ Aplicado)

- [x] **tests/requirements.txt** (pytest, coverage, mocking)
- [x] **Makefile** (make test, make test-wearable, make test-server)
- [x] **Coverage report** (Codecov integration)

---

## 🐳 DevContainer e Reprodutibilidade

### DevContainer (✅ Aplicado)

- [x] **.devcontainer/devcontainer.json** com:
  - Base image: Python 3.11 + Docker-in-Docker
  - Extensions: Python, PlatformIO, Docker, GitHub Copilot
  - Features: Python, Docker, GitHub CLI
  - Forwarded ports: 1880 (Node-RED), 1883 (MQTT), 4000 (LiteLLM), 11434 (Ollama)
  - postCreateCommand: setup-dev.sh
  - Mounts: SSH keys, volumes locais

**Referência:** [VS Code Dev Containers](https://code.visualstudio.com/docs/devcontainers/containers)

### Makefile (✅ Aplicado)

- [x] **Comandos unificados:**
  - `make setup` (instala dependências, inicia Docker)
  - `make test` (roda todos os testes)
  - `make docs` (MkDocs serve local)
  - `make deploy-wearable` (OTA firmware)
  - `make clean` (limpa temporários)

---

## 📊 Badges e Metadados

### README Badges (✅ Aplicado)

- [x] **License:** MIT
- [x] **CI/CD:** GitHub Actions status
- [x] **Documentation:** MkDocs
- [x] **Model Card:** Hugging Face style
- [x] **Citation:** DOI (Zenodo)
- [x] **Stars/Forks/Issues:** GitHub metrics

### CITATION.cff (✅ Aplicado)

- [x] **Metadados completos:**
  - Authors (Alisson De Faria)
  - Title (YBY SEED)
  - Abstract
  - Version (1.0.0)
  - DOI (pendente Zenodo)
  - License (MIT)
  - Keywords (NL2Code, IoT, ESP32, MQTT, LLM)

**Referência:** [Zenodo CITATION.cff](https://help.zenodo.org/docs/github/describe-software/citation-file/)

---

## 🎯 Próximos Passos (Pendente)

### Publicação Acadêmica

- [ ] **Registrar DOI no Zenodo:**
  ```bash
  # 1. Crie release no GitHub
  git tag v1.0.0
  git push origin v1.0.0
  
  # 2. Acesse https://zenodo.org
  # 3. Conecte conta GitHub
  # 4. Selecione repositório yby-seed
  # 5. Preencha metadados
  # 6. Publique (gera DOI)
  ```

- [ ] **Submeter paper:**
  - Conferências: IEEE IoT, ACM UbiComp, USENIX OSDI
  - Journals: IEEE IoT Journal, ACM TECS, Elsevier FGCS
  - Preprint: arXiv (cs.SE, cs.DC)

### Documentação

- [ ] **Traduções:**
  - [ ] Espanhol (docs-es/)
  - [ ] Francês (docs-fr/)
  - [ ] Chinês (docs-zh/)

- [ ] **Vídeo tutorials:**
  - [ ] Instalação (15 min)
  - [ ] Primeira automação (10 min)
  - [ ] Contribuindo (20 min)

### Comunidade

- [ ] **Discord/Slack:** Canal para contribuidores
- [ ] **Roadmap público:** GitHub Projects
- [ ] **Release notes:** CHANGELOG.md
- [ ] **Hall da fama:** CONTRIBUTORS.md

---

## 📈 Métricas de Sucesso

### Reprodutibilidade

- [ ] Clone + `make setup` funciona em <15 min
- [ ] DevContainer inicia sem erros
- [ ] Testes passam em CI/CD
- [ ] Documentação acessível em mkdocs serve

### Adoção Acadêmica

- [ ] DOI registrado no Zenodo
- [ ] Paper submetido (pelo menos 1 conferência/journal)
- [ ] Citações (Google Scholar, Semantic Scholar)
- [ ] Stars no GitHub (>100 em 6 meses)

### Comunidade

- [ ] Contribuidores externos (>5 em 6 meses)
- [ ] Issues resolvidas por comunidade (>50%)
- [ ] Forks ativos (>10 em 6 meses)

---

## 🔗 Referências

1. **GitHub Best Practices:** https://docs.github.com/en/repositories/creating-and-managing-repositories/best-practices-for-repositories
2. **Hugging Face Model Cards:** https://huggingface.co/docs/hub/model-card-guidebook
3. **Zenodo CITATION.cff:** https://help.zenodo.org/docs/github/describe-software/citation-file/
4. **VS Code Dev Containers:** https://code.visualstudio.com/docs/devcontainers/containers
5. **Contributor Covenant:** https://www.contributor-covenant.org/version/2/1/code_of_conduct.html
6. **OWASP Top 10:** https://owasp.org/www-project-top-ten/
7. **OpenSSF Scorecard:** https://securityscorecards.dev/

---

**YBY SEED** está pronto para submissão acadêmica! 🎓🚀

**Última atualização:** 2026-10-08  
**Versão:** 1.0.0
