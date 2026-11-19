#!/usr/bin/env bash
# Verificação parcial da Fase P — só o que dá para provar neste ambiente/repo.
# Itens de hardware (reboot, linger, rede, Syncthing real, restauração no Hub)
# saem como SKIP/PENDING. NÃO inventa PASS para esses.
#
# Uso (raiz do repo):
#   bash scripts/phase-p-check.sh
#   bash scripts/phase-p-check.sh --json   # resumo no fim em uma linha
#
# Checklist humano: docs/PHASE-P-CHECKLIST.md

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PASS=0
FAIL=0
SKIP=0
JSON=0
[[ "${1:-}" == "--json" ]] && JSON=1

_ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

pass() {
  PASS=$((PASS + 1))
  printf 'PASS  %s — %s\n' "$1" "$2"
}

fail() {
  FAIL=$((FAIL + 1))
  printf 'FAIL  %s — %s\n' "$1" "$2"
}

skip() {
  SKIP=$((SKIP + 1))
  printf 'SKIP  %s — %s\n' "$1" "$2"
}

need_file() {
  local id="$1" path="$2" msg="${3:-arquivo presente}"
  if [[ -f "$path" ]]; then
    pass "$id" "$msg ($path)"
  else
    fail "$id" "ausente: $path"
  fi
}

grep_unit() {
  local id="$1" pattern="$2" file="$3" msg="$4"
  if [[ -f "$file" ]] && grep -Eq "$pattern" "$file"; then
    pass "$id" "$msg"
  else
    fail "$id" "não encontrado '$pattern' em $file"
  fi
}

echo "=== phase-p-check ($( _ts )) ==="
echo "root: $ROOT"
echo "modo: só verificável no repo/ambiente — hardware = SKIP"
echo

# --- Artefatos no repositório (Fase 2 / unit) ---
echo "## Repo — unit systemd (conteúdo versionado)"
for unit in scripts/yby-hub.service deploy/systemd/yby-hub.service; do
  need_file "unit-file:${unit}" "$unit" "unit versionada"
done

grep_unit "unit-after-ollama" 'After=.*ollama\.service' scripts/yby-hub.service \
  "After=ollama.service (decisão P #3 / A)"
grep_unit "unit-after-network" 'After=.*network-online\.target' scripts/yby-hub.service \
  "After=network-online.target"
grep_unit "unit-wants-network" 'Wants=network-online\.target' scripts/yby-hub.service \
  "Wants=network-online.target"
grep_unit "unit-restart" '^Restart=on-failure' scripts/yby-hub.service \
  "Restart=on-failure"
grep_unit "unit-restart-sec" '^RestartSec=' scripts/yby-hub.service \
  "RestartSec definido"
grep_unit "unit-workdir" '^WorkingDirectory=' scripts/yby-hub.service \
  "WorkingDirectory definido"
grep_unit "unit-envfile" '^EnvironmentFile=' scripts/yby-hub.service \
  "EnvironmentFile (segredos fora do unit)"
grep_unit "unit-name-yby-hub" 'yby-hub|hub keepalive' scripts/yby-hub.service \
  "nome/escopo yby-hub (decisão P #7 / A)"

need_file "install-hub-script" scripts/install-hub-service.sh "instalador unit de usuário"
if grep -q 'systemctl --user\|systemd/user' scripts/install-hub-service.sh 2>/dev/null; then
  pass "unit-user-scope" "install-hub-service.sh usa systemd de usuário (decisão P #1 / A)"
else
  fail "unit-user-scope" "install-hub-service.sh não referencia systemd --user"
fi
echo

# --- Backup (Fase 5 — existência no repo; restauração real = SKIP) ---
echo "## Repo — backup vault"
need_file "backup-script" scripts/backup-vault.sh "scripts/backup-vault.sh (tar + retenção)"
need_file "backup-docs" docs/BACKUP.md "docs/BACKUP.md"
need_file "backup-timer-unit" scripts/yby-vault-backup.timer "timer systemd de usuário (versionado)"
need_file "backup-service-unit" scripts/yby-vault-backup.service "service oneshot backup (versionado)"
if grep -Eq 'tar|BACKUP_KEEP|YBY_BACKUP' scripts/backup-vault.sh 2>/dev/null; then
  pass "backup-tar-retention" "script usa tar/retenção (decisões P #4/#5 / A)"
else
  fail "backup-tar-retention" "script sem indício de tar/retenção"
fi
if grep -q 'OnCalendar=daily' scripts/yby-vault-backup.timer 2>/dev/null \
  && grep -q 'YBY_BACKUP_KEEP=7' scripts/yby-vault-backup.service 2>/dev/null; then
  pass "backup-timer-daily-keep7" "timer diário + KEEP=7 no unit (decisão P #5 / A)"
else
  fail "backup-timer-daily-keep7" "timer/service sem OnCalendar=daily ou KEEP=7"
fi
if grep -Eq 'yby-vault-backup\.timer|systemctl --user' docs/BACKUP.md 2>/dev/null; then
  pass "backup-timer-docs" "BACKUP.md documenta enable do timer --user"
else
  fail "backup-timer-docs" "BACKUP.md sem instrução do timer de usuário"
fi
skip "backup-restore-hub" "restauração real no PC Hub (hardware)"
skip "backup-daily-cron-hub" "timer/enable real no Hub (hardware; units só no repo)"
echo

# --- Syncthing exemplos (Fase 4 — docs; sync real = SKIP) ---
echo "## Repo — Syncthing (exemplos / docs)"
need_file "syncthing-readme" examples/syncthing/README.md "README exemplos"
need_file "syncthing-xml" examples/syncthing/folder-config.example.xml "esqueleto folder XML"
need_file "syncthing-yaml" docs/syncthing/vault-folder.example.yaml "esqueleto YAML"
need_file "syncthing-stignore" examples/syncthing/.stignore.example ".stignore.example"
if grep -q '\.yby/' examples/syncthing/.stignore.example 2>/dev/null; then
  pass "syncthing-ignore-yby" ".stignore.example ignora .yby/"
else
  fail "syncthing-ignore-yby" ".stignore.example sem .yby/"
fi
if grep -Eq 'systemctl --user|serviço de usuário' examples/syncthing/README.md 2>/dev/null; then
  pass "syncthing-user-service-doc" "README documenta serviço de usuário (decisão P #6 / A)"
else
  fail "syncthing-user-service-doc" "README sem nota de serviço de usuário"
fi
skip "syncthing-installed-hub" "Syncthing instalado no Hub (hardware)"
skip "syncthing-sync-pc-hub" "sincronização real PC↔Hub (hardware)"
echo

# --- Decisões P fechadas ---
echo "## Docs — decisões Fase P"
need_file "decisions-doc" docs/PHASE-P-DECISIONS.md "PHASE-P-DECISIONS.md"
if grep -Eq 'todas as 8|8/8|8 perguntas fechadas' docs/PHASE-P-DECISIONS.md 2>/dev/null; then
  pass "decisions-closed" "8 decisões P documentadas como fechadas"
else
  fail "decisions-closed" "PHASE-P-DECISIONS.md sem indício de 8/8 fechadas"
fi
need_file "checklist-doc" docs/PHASE-P-CHECKLIST.md "PHASE-P-CHECKLIST.md"
echo

# --- Política nuvem / #42 (código versionado) ---
echo "## Repo — D12 / #42 (falha Ollama sem nuvem)"
if grep -q '_after_local_failure' src/engine/hybrid.py 2>/dev/null \
  && grep -Eq 'não é acionada automaticamente|nao e acionada' src/engine/hybrid.py 2>/dev/null; then
  pass "d12-local-failure" "HybridEngine._after_local_failure sem cascade nuvem"
else
  fail "d12-local-failure" "caminho _after_local_failure ausente/incompleto"
fi
if grep -R -E -q 'def test_ollama_fora_nao_cai_na_nuvem|def test_ollama_falha_nao_pede_nuvem' \
  tests/test_engine.py tests/test_cloud_usage_log.py 2>/dev/null; then
  pass "d12-tests" "testes de regressão Ollama-fail→sem-nuvem presentes"
else
  fail "d12-tests" "testes D12 ausentes"
fi
skip "cloud-finops-sqlite" "FinOps SQLite (#42 S1+) ainda não implementado — ver CLOUD_USAGE_SPEC.md"
if grep -q 'YBY_CLOUD_DAILY_TOKEN_LIMIT' src/engine/budget.py 2>/dev/null \
  && grep -q 'daily_token_limit' src/engine/budget.py 2>/dev/null \
  && grep -q 'test_teto_diario_bloqueia' tests/test_budget.py 2>/dev/null; then
  pass "cloud-daily-budget" "daily token budget (#42 S2 parcial) em budget.py + teste"
else
  fail "cloud-daily-budget" "daily token budget ausente"
fi
skip "cloud-budget-cost-exception" "custo USD + exception path (#42 S2 restante)"
skip "cloud-sanitizer-gated" "sanitizer gated no hybrid (#42) ainda aberto"
echo

# --- Segredos fora do repo ---
echo "## Repo — segredos"
if [[ -f .env ]]; then
  # .env pode existir localmente; não deve estar no índice git
  if git ls-files --error-unmatch .env >/dev/null 2>&1; then
    fail "secrets-not-tracked" ".env está versionado — remova do git"
  else
    pass "secrets-not-tracked" ".env local não está no índice git"
  fi
else
  pass "secrets-not-tracked" "sem .env no workspace (ok); template .env.example"
fi
need_file "env-example" .env.example ".env.example presente"
echo

# --- Doctor (ambiente) ---
echo "## Ambiente — make doctor"
if make doctor >/tmp/yby-phase-p-doctor.log 2>&1; then
  pass "make-doctor" "make doctor OK (log /tmp/yby-phase-p-doctor.log)"
else
  fail "make-doctor" "make doctor falhou — ver /tmp/yby-phase-p-doctor.log"
fi
echo

# --- Hardware / runtime no Hub (sempre SKIP aqui) ---
echo "## Hardware Hub — PENDING (não verificável neste ambiente)"
skip "hub-linux-user" "confirmar usuário Linux no Hub"
skip "hub-vault-path" "confirmar YBY_VAULT_PATH no Hub"
skip "hub-python" "confirmar Python no Hub"
skip "hub-ollama-model" "Ollama + qwen2.5-coder:3b no Hub"
skip "hub-enable-service" "systemctl --user enable yby-hub no Hub"
skip "hub-reboot" "reboot completo com serviço ativo"
skip "hub-linger" "loginctl enable-linger no Hub"
skip "hub-status-cmd" "hub --once / status no hardware"
skip "hub-no-public-port" "validar bind só loopback no Hub"
skip "hub-network-fail" "falha simulada de rede no Hub"
skip "hub-ollama-fail-live" "falha simulada Ollama no Hub (código já coberto por testes)"
skip "hub-service-fail" "falha simulada do serviço no Hub"
echo

echo "=== resumo ==="
echo "PASS=$PASS FAIL=$FAIL SKIP=$SKIP"
echo "Itens SKIP exigem PC Hub físico — não marque o checklist humano como feito sem evidência."
echo "Checklist: docs/PHASE-P-CHECKLIST.md"

if [[ "$JSON" -eq 1 ]]; then
  printf '{"pass":%s,"fail":%s,"skip":%s,"ts":"%s"}\n' "$PASS" "$FAIL" "$SKIP" "$(_ts)"
fi

if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
exit 0
