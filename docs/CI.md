# CI e revisão de PRs

O que o repositório realmente valida hoje. Sem deploy automático e sem publicação de secrets.

## Gate bloqueante (GitHub Actions)

Workflow: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)

Dispara em:

- `pull_request` (qualquer branch)
- `push` (qualquer branch, incluindo feature)

Passos (falha = PR vermelho):

1. Instalar `requirements.txt` + `requirements-dev.txt` (Python 3.11)
2. `make doctor` — Python, arquivos-chave, imports core/dev, alvos do Makefile
3. `make lint` — `ruff check src tests`
4. `make test` — `pytest tests -q`

Localmente, o mesmo gate:

```bash
make setup    # uma vez
make check    # doctor + lint + test
```

**Type check (mypy):** está em `requirements-dev.txt`, mas **não** entra no gate — o legado falharia em massa. O gate real é ruff + pytest.

### Branch protection (manual, mantenedor)

Para o CI de fato bloquear merge em `main`:

1. GitHub → Settings → Branches → Branch protection rule em `main`
2. Exigir status check: job `lint-and-test` do workflow **CI**
3. Não permitir bypass sem revisão, se o time quiser

Sem essa regra no GitHub, o workflow ainda falha o check, mas o merge pode ser forçado.

## Revisão automática de PRs

Workflow: [`.github/workflows/pr-review.yml`](../.github/workflows/pr-review.yml)

- Comenta (ou atualiza) um checklist no PR com achados determinísticos (legado tocado, possíveis secrets no diff, código sem teste).
- Não chama APIs de nuvem; não altera o código; não é o gate de merge (o CI é).

Script: `scripts/pr_auto_review.py` (também rodável localmente após um commit).

## Cursor Bugbot (opcional)

Se a conta/organização tiver **Cursor Bugbot** (ou Bugbot no marketplace GitHub):

1. Instale o GitHub App do Cursor / Bugbot no repositório `yby-seed`
2. Em Cursor → Settings → Bugbot (ou documentação atual da Cursor), habilite revisão automática de PRs
3. Confirme que o app tem permissão de leitura de código e comentários em PR

Com Bugbot ativo, ele passa a ser a revisão LLM principal; o workflow `PR Review` permanece como rede de segurança determinística. Se Bugbot não estiver disponível, só o Action acima comenta.

Não há chave de Bugbot no repositório — a ativação é configuração da conta/org, não código.
