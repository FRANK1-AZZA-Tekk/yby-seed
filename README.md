# YBY SEED 🌱

> Function Over Form: um projeto local-first para explorar programação por linguagem natural, automação e assistência de IA.

## Estado real do projeto

Este repositório está em fase de protótipo. A arquitetura e vários módulos experimentais estão presentes, mas isso não significa que a experiência ponta a ponta esteja implementada ou validada. Em particular, geração de embeddings, persistência de telemetria, execução segura de código gerado e os comandos CLI de inicialização ainda não devem ser tratados como recursos prontos para produção.

| Área | Estado nesta revisão |
|---|---|
| CLI e fluxo completo de intenção/aprovação/execução | Planejado/em implementação |
| Gateway FastAPI | Protótipo local; sem autenticação de API |
| Execução de código gerado | Desativada por segurança; não há sandbox aprovado |
| Ollama, MQTT, Node-RED e dashboards | Serviços auxiliares de desenvolvimento |
| Wearable e integração móvel | Roadmap; não são requisito do MVP |

## Requisitos e início

Requer Python 3.11 ou superior, Docker Compose v2 e Git. Para a instalação base:

```bash
git clone https://github.com/FRANK1-AZZA-Tekk/yby-seed.git
cd yby-seed
make setup
```

Edite `.env` com credenciais fortes antes de iniciar serviços. O setup apenas prepara dependências; não inicia containers nem baixa modelos automaticamente:

```bash
make run
make pull-models
make test
```

Os serviços do Compose são publicados somente em `127.0.0.1`. Não remova esse limite nem exponha os endpoints em uma rede pública sem autenticação, firewall e revisão de segurança. Ollama não deve ser considerado uma API autenticada.

## Configuração

Copie `.env.example` para `.env` (o `make setup` faz isso quando o arquivo não existe) e defina senhas únicas para PostgreSQL e Grafana. Nunca versione `.env`.

## Qualidade

```bash
make test
make lint
```

Os testes locais não comprovam segurança de sandbox, confiabilidade de modelos nem prontidão de produção. Os recursos devem ser promovidos de protótipo somente após testes reproduzíveis e revisão.

## Roadmap enxuto

1. CLI local que valida e persiste uma intenção sem executar ações externas.
2. Plano de ação legível e aprovação explícita do usuário.
3. Primeira skill determinística, com permissões mínimas e testes.
4. Integrações de modelo/RAG depois de contratos e avaliações básicas.
5. Serviços móveis e wearable em etapas posteriores.

Consulte `CONTRIBUTING.md`, `SECURITY.md` e `HARDWARE_SPEC.md` antes de contribuir. Licença: MIT.
