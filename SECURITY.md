# Política de Segurança do YBY SEED

## 🛡️ Reportando uma Vulnerabilidade

Levamos a segurança do YBY SEED muito a sério. Se você identificar uma vulnerabilidade, siga as diretrizes abaixo.

### ⚠️ NÃO

- **NÃO** reporte vulnerabilidades em issues públicas do GitHub
- **NÃO** discuta vulnerabilidades em fóruns públicos, redes sociais ou chats
- **NÃO** explore a vulnerabilidade além do necessário para identificar o problema

### ✅ SIM

- **SIM** envie um email para: **alissonfaria4@gmail.com**
- **SIM** inclua o máximo de detalhes possível:
  - Tipo de vulnerabilidade (ex.: RCE, XSS, SQLi, etc.)
  - Passos para reproduzir
  - Impacto potencial
  - Versões afetadas (se souber)
  - Sugestão de fix (opcional)

## 📋 Processo de Resposta

1. **Recebimento (48h):** Confirmamos recebimento do report
2. **Análise (7 dias):** Avaliamos severidade e impacto
3. **Correção (30 dias):** Desenvolvemos e testamos fix
4. **Release (45 dias):** Publicamos patch e advisory
5. **Divulgação (60 dias):** Divulgamos detalhes publicamente (após usuários aplicarem patch)

## 🔒 Tipos de Vulnerabilidade

### Críticas (Resposta em 48h)

- **RCE (Remote Code Execution):** Execução arbitrária de código
- **Auth Bypass:** Burlar autenticação
- **Data Leak em Massa:** Exposição de dados sensíveis de múltiplos usuários

### Altas (Resposta em 7 dias)

- **Privilege Escalation:** Elevar privilégios de usuário
- **XSS/CSRF:** Injeção de scripts ou requisições
- **DoS:** Negação de serviço

### Médias (Resposta em 14 dias)

- **Information Disclosure:** Vazamento de informações não críticas
- **Configuração Insegura:** Defaults inseguros, logs expostos

### Baixas (Resposta em 30 dias)

- **Best Practices:** Headers de segurança, CSP, etc.
- **Dependências Desatualizadas:** Packages com vulnerabilidades conhecidas

## 🛠️ Boas Práticas de Segurança

### Para Usuários

- **Atualize regularmente:** `docker-compose pull && docker-compose up -d`
- **Use senhas fortes:** MQTT, OTA, APIs
- **Isole a rede:** VLAN separada para IoT, firewall
- **Monitore logs:** `docker-compose logs -f`
- **Backup:** Registry SQLite, configurações

### Para Contribuidores

- **Valide inputs:** Nunca confie em dados de MQTT/HTTP
- **Limite recursos:** `resource.setrlimit()` em subprocessos
- **Evite `eval()`/`exec()`:** Use AST parsing quando possível
- **Sanitize outputs:** Escape HTML/JS em TUIs
- **Teste segurança:** `pytest --cov=security`

## 📜 Histórico de Segurança

| Data | Versão | Vulnerabilidade | Severidade | Status |
|---|---|---|---|---|
| 2026-10-08 | 1.0.0 | - | - | Lançamento inicial |

## 🏆 Hall da Fama

Agradecemos aos pesquisadores que reportaram vulnerabilidades:

- (Em branco - seja o primeiro!)

## 📚 Referências

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [GitHub Security Advisories](https://docs.github.com/en/code-security/security-advisories)
- [Contributor Covenant](https://www.contributor-covenant.org/)

---

**Contato:** alissonfaria4@gmail.com  
**Última atualização:** 2026-10-08
