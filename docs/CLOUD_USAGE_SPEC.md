# Cloud Usage Registry & FinOps — Technical Spec (Issue #42)

**Status (código):** **parcial** — baseline JSONL + budget **diário+mensal (tokens)** + confirmação TTY + **falha Ollama no caminho local sem cascade nuvem** (D12 / fase P) + **sanitizer gated no `_cloud_call`** (`cloud_sanitizer.py`, S4 parcial) já no runtime.  
**Ainda aberto:** SQLite FinOps (S1), custo USD + exception path (resto de S2), authz vault antes do egress (resto de S4).  
**Este documento:** SPEC / PLAN (não muda comportamento por si só).  
**Decisions:** D12 (economia de execução) governs cloud; **D11 (voz local) is unchanged**.  
**Constraint:** no sensitive data leaves the machine without explicit authz; no OpenRouter auto-fallback; no heavy deps (stdlib `sqlite3` + existing `pydantic`).

### Status vs slices (honesto)

| Slice | Entrega | Estado |
|---|---|---|
| **S0** | Spec + comentários SECURITY/.env | Feito (este arquivo) |
| **D12 / fase P** | Falha Ollama local → sem nuvem automática (`HybridEngine._after_local_failure`) | Feito (código + testes) |
| Baseline pré-spec | JSONL `cloud_usage_log` + budget mensal + confirm TTY | Feito |
| **S1** | `cloud_usage_db.py` + import JSONL | Aberto |
| **S2** | Daily budget + custo + exception | **Parcial** — teto/aviso diário de **tokens** em `budget.py`; custo USD + exception ainda abertos |
| **S3** | Wire hybrid com registry status | Aberto (parcial: eventos JSONL no caminho cloud) |
| **S4** | Sanitizer/authz gated antes do egress | Parcial (sanitizer no hybrid; authz vault aberto) |
| **S5** | Dual-write / doctor / retenção | Aberto |

---

## 0. Executive summary

YBY SEED already ships a **local JSONL cloud usage log** (`src/engine/cloud_usage_log.py`) and a **monthly token budget gate** (`src/engine/budget.py`) wired into `HybridEngine` (`src/engine/hybrid.py`). This spec **evolves** that baseline toward a **local SQLite registry** with richer FinOps fields, daily+monthly budgets, explicit exceptions, sanitization/authz before egress, and a clear telemetry contract — without pretending the JSONL path does not exist.

| Today (baseline) | Target (this spec) |
|---|---|
| `logs/cloud_usage.jsonl` (0600) | `logs/cloud_usage.sqlite3` (0600) + JSONL import once |
| Fields: timestamp, provider, model, purpose, in/out token estimates, result | Same + optional `input_tokens_reported`/`output_tokens_reported` (API `usage` on fresh HTTP; budget unchanged) + estimated cost, status, session/task id, prompt hash/ref, result ref |
| Monthly token limit + warn | Daily + monthly limits; warn / block / explicit exception |
| Confirm when `YBY_CLOUD_REQUIRE_CONFIRM` | Confirm policy by mode, cost threshold, and purpose |
| Metadata-only log (rejects prompt/key fields) | Same + outbound sanitizer gate + vault authz |

---

## 1. Goals & non-goals

### Goals

1. **Every** cloud call attempt is recorded locally **before** network I/O (and updated on complete/fail).
2. User is **warned / asked to confirm** before cloud when cost or policy says so.
3. **Daily and monthly** budgets (tokens and optional currency estimate).
4. **Local-first / offline:** `YBY_CLOUD_MODE=local_only` and absence of network never break local ask/voice.
5. **No secrets** in the registry; prompt bodies stay on-disk only as optional local refs under vault rules.
6. Migration path from JSONL → SQLite that preserves history.

### Non-goals

- Changing D11 (faster-whisper + Piper remain default voice).
- OpenRouter (or any provider) as **automatic** failover of another provider.
- Shipping telemetry to a remote SaaS.
- New heavy dependencies (no ORM, no cloud billing SDK).
- Implementing application code in the PR that lands this doc (implementation is a later slice).

---

## 2. Current baseline (as-built)

### 2.1 Modules

| Module | Role today |
|---|---|
| `src/engine/cloud_usage_log.py` | Append-only JSONL; required fields; forbids `prompt`/`api_key`/`response`/`text`/`audio` |
| `src/engine/budget.py` | `CloudBudget`: `local_only`, monthly token hard cap, warn threshold, TTY confirm gate |
| `src/engine/hybrid.py` | Gate → confirm → call no caminho **cloud** (heavy/`--heavy`); falha Ollama no caminho local **não** chama nuvem (D12 / fase P). Events: requested / confirmed / completed / failed / cancelled / blocked_* |
| `src/engine/routing.py` | Local vs cloud **decision** (heavy heuristics); does not talk to network |
| `src/security/openrouter_sanitizer.py` | Legacy regex sanitizer (to be folded into `src/security/` contract below) |
| `src/security/ast_guard.py` | Unrelated to FinOps; remains for code sandbox |

### 2.2 Env knobs (today)

See `.env.example`:

- `YBY_CLOUD_MODE` (`ask` \| `local_only` \| future `auto` — auto still requires confirm policy)
- `YBY_CLOUD_LOG_PATH` (default `logs/cloud_usage.jsonl`)
- `YBY_CLOUD_DAILY_TOKEN_LIMIT`, `YBY_CLOUD_WARN_DAILY_TOKEN_LIMIT` (tokens; janela UTC)
- `YBY_CLOUD_MONTHLY_TOKEN_LIMIT`, `YBY_CLOUD_WARN_TOKEN_LIMIT`
- `YBY_CLOUD_REQUIRE_CONFIRM`, `YBY_CLOUD_ALLOW_NO_TTY`

### 2.3 Gaps vs issue #42 acceptance

| Acceptance | Baseline | Gap |
|---|---|---|
| No cloud without local registry | Yes (JSONL) | Need SQLite + stronger schema |
| Warn before relevant-cost cloud | Yes (TTY confirm + daily/monthly token warn) | Cost estimate USD + exception path |
| Local works offline | Yes | Keep invariant; document |
| Ollama fail on local path ≠ auto cloud | Yes (`_after_local_failure`, D12 / fase P) | None for this acceptance; FinOps SQLite still separate |
| No secrets/vault without auth | Log forbids raw fields; sanitizer exists but not gated in hybrid | Formal authz + redaction before egress |

---

## 3. Target architecture

```
CLI / voice (D11 local STT)
        │
        ▼
 routing.py  ──► RouteDecision {local|cloud, reasons, codes}
        │
        ▼
 HybridEngine
        │
        ├─► CloudAuthz / Sanitizer (src/security/) ── block or redact
        ├─► CloudBudget (daily+monthly, warn/block/exception)
        ├─► Confirm policy (TTY / session / explicit exception token)
        ├─► CloudUsageRegistry (SQLite) ── insert row status=requested
        └─► Provider (explicit config only; NO auto OpenRouter fallback)
                 │
                 └─► Registry update status=completed|failed + tokens/cost
```

**Local mode:** if route is local, or mode is `local_only`, or budget blocks, or user cancels — no network; Ollama path unchanged. Registry may still record `blocked_*` / `cancelled` for audit.

---

## 4. Data model — local SQLite registry

### 4.1 Storage

| Item | Spec |
|---|---|
| Default path | `logs/cloud_usage.sqlite3` |
| Env | `YBY_CLOUD_DB_PATH` (new); keep `YBY_CLOUD_LOG_PATH` for JSONL import / dual-write window |
| Permissions | file `0600`, dir `0700` |
| Engine | stdlib `sqlite3`; WAL mode; `busy_timeout=5000` |
| Secrets | never stored; CHECK/trigger or app-level reject of forbidden columns |

### 4.2 Table `cloud_usage_events`

Minimum fields required by product + FinOps:

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Auto |
| `timestamp` | REAL NOT NULL | Unix UTC seconds (compatible with JSONL) |
| `provider` | TEXT NOT NULL | e.g. `openrouter`, `xai`, `none` |
| `model` | TEXT NOT NULL | Configured model id |
| `purpose` | TEXT NOT NULL | `route_cloud`, `ollama_fallback`, `explicit`, … |
| `input_tokens` | INTEGER NOT NULL DEFAULT 0 | Prefer provider usage; else estimate |
| `output_tokens` | INTEGER NOT NULL DEFAULT 0 | Prefer provider usage; else estimate |
| `estimated_cost_usd` | REAL | Nullable; from local price table; **not** billed invoice |
| `status` | TEXT NOT NULL | See §4.3 |
| `session_id` | TEXT | CLI/session uuid (local) |
| `task_id` | TEXT | Optional task/correlation id |
| `prompt_hash` | TEXT | SHA-256 of **sanitized** prompt bytes; never raw prompt |
| `prompt_ref` | TEXT | Optional local path/uri under vault; **null unless authz** |
| `result_ref` | TEXT | Optional local path to truncated result metadata; never full secret payload |
| `result` | TEXT | Legacy event name for JSONL parity (`cloud_completed`, …) |
| `error_code` | TEXT | Optional short code |
| `meta_json` | TEXT | Small JSON bag (reasons, warn flags); no secrets |

Indexes: `(timestamp)`, `(status, timestamp)`, `(session_id)`, `(provider, model, timestamp)`.

### 4.3 Status / result vocabulary

Align with existing event constants; prefer `status` going forward, keep `result` during migration:

| status | legacy `result` | Meaning |
|---|---|---|
| `requested` | `cloud_requested` | Intent logged pre-call |
| `confirmed` | `cloud_confirmed` | User confirmed |
| `completed` | `cloud_completed` | Success (counts toward budget) |
| `failed` | `cloud_failed` | Provider error after attempt |
| `cancelled` | `cloud_cancelled` | User declined |
| `blocked_local_only` | `cloud_blocked_local_only` | Mode forbids cloud |
| `blocked_budget` | `cloud_blocked_budget` | Cap exceeded |
| `blocked_no_tty` | `cloud_blocked_no_tty` | Confirm required, no TTY |
| `blocked_authz` | *(new)* | Sanitizer/vault authz denied |
| `exception_granted` | *(new)* | Explicit exception used for this call |

**Budget counting rule:** only `completed` events add tokens/cost. Failed attempts may be counted optionally via `YBY_CLOUD_COUNT_FAILED=0` (default off).

### 4.4 Pydantic schemas (documentation examples)

```python
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator

FORBIDDEN_KEYS = frozenset({"prompt", "api_key", "response", "text", "audio", "vault"})

class CloudEventStatus(str, Enum):
    requested = "requested"
    confirmed = "confirmed"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    blocked_local_only = "blocked_local_only"
    blocked_budget = "blocked_budget"
    blocked_no_tty = "blocked_no_tty"
    blocked_authz = "blocked_authz"
    exception_granted = "exception_granted"

class CloudUsageEvent(BaseModel):
    timestamp: float
    provider: str
    model: str
    purpose: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost_usd: Optional[float] = Field(default=None, ge=0)
    status: CloudEventStatus
    session_id: Optional[str] = None
    task_id: Optional[str] = None
    prompt_hash: Optional[str] = Field(default=None, min_length=64, max_length=64)
    prompt_ref: Optional[str] = None
    result_ref: Optional[str] = None
    result: Optional[str] = None  # legacy mirror
    error_code: Optional[str] = None
    meta: dict[str, object] = Field(default_factory=dict)

    @field_validator("meta")
    @classmethod
    def no_secrets_in_meta(cls, v: dict) -> dict:
        bad = FORBIDDEN_KEYS.intersection(v)
        if bad:
            raise ValueError(f"forbidden meta keys: {sorted(bad)}")
        return v

class BudgetDecision(BaseModel):
    allowed: bool
    code: Literal[
        "allowed",
        "warn",
        "blocked_local_only",
        "blocked_budget",
        "blocked_no_tty",
        "blocked_authz",
        "exception_required",
    ]
    reason: str
    daily_tokens_used: int = 0
    monthly_tokens_used: int = 0
    daily_cost_usd: float = 0.0
    monthly_cost_usd: float = 0.0
    requires_confirmation: bool = True
```

JSON Schema mirror (optional file for tooling): see §11 `docs/schemas/cloud_usage_event.example.json`.

### 4.5 Cost estimation (local-only)

- Maintain a tiny in-repo price table (USD per 1M in/out tokens) keyed by `provider`+`model`, defaulting to `0` for `:free` / unknown.
- `estimated_cost_usd = in/1e6 * price_in + out/1e6 * price_out`.
- Estimates are **advisory**; never claim invoice accuracy.
- D12 operational ceilings (Cursor Premium R$100 / OpenRouter R$50) remain **human policy**; env limits below are machine-enforced token/USD guards.

---

## 5. Migration: JSONL → SQLite

1. **Detect** existing `YBY_CLOUD_LOG_PATH` file.
2. **One-shot import** on first registry open: map JSONL fields → rows; set `status` from `result`; leave new columns null.
3. **Dual-write window** (slice 1–2): write SQLite primary + append JSONL if `YBY_CLOUD_JSONL_MIRROR=1` (default `1` during migration, then `0`).
4. **Checksum:** import reports `imported_n`, `skipped_n`, `last_timestamp`.
5. Do **not** delete JSONL automatically; operator may archive.
6. Budget readers switch to SQLite sums; fallback to JSONL only if DB missing (compat).

---

## 6. When to confirm before a cloud call

### 6.1 Decision order (authz flow)

```
1. RouteDecision.target == local? → no cloud, no confirm
2. YBY_CLOUD_MODE == local_only? → block + log blocked_local_only
3. Sanitizer / vault authz fail? → block + log blocked_authz
4. Budget hard block (daily/monthly)? → block unless valid exception token
5. Cache hit for same prompt_hash+model? → skip network; no new billable event
   (optional: log cache_hit locally without status=completed)
6. Confirm policy (§6.2) → ask user or use session confirmation
7. Log status=requested → (confirm) → network call → completed|failed
```

### 6.2 Confirm policy

Confirm **before** network when **any** is true:

| Trigger | Default |
|---|---|
| `YBY_CLOUD_REQUIRE_CONFIRM=1` | on |
| Estimated cost ≥ `YBY_CLOUD_CONFIRM_COST_USD` | `0.01` |
| Estimated input tokens ≥ `YBY_CLOUD_CONFIRM_TOKEN_THRESHOLD` | `2000` |
| Purpose in `{ollama_fallback, explicit_paid_model}` | always |
| First cloud call in session | always if require_confirm |
| Budget in **warn** band | always (show usage %) |

Skip confirm when:

- `YBY_CLOUD_REQUIRE_CONFIRM=0` **and** cost/token triggers not met; or
- Valid **explicit exception** for this session/task (§7.3); or
- Session already confirmed **and** purpose is low-risk continuation **and** still under warn band.

No TTY + confirm required + `YBY_CLOUD_ALLOW_NO_TTY=0` → `blocked_no_tty` (current behavior).

Prompt copy (UX): show provider, model, purpose, est. tokens, est. USD, daily/monthly remaining — never show raw vault content.

---

## 7. Budget policy

### 7.1 Limits

| Env | Default | Role |
|---|---|---|
| `YBY_CLOUD_DAILY_TOKEN_LIMIT` | `50000` | Hard daily token cap |
| `YBY_CLOUD_MONTHLY_TOKEN_LIMIT` | `200000` | Hard monthly (exists) |
| `YBY_CLOUD_DAILY_COST_USD_LIMIT` | `2.00` | Soft/hard cost guard |
| `YBY_CLOUD_MONTHLY_COST_USD_LIMIT` | `10.00` | Aligns with planning doc free-tier mindset |
| `YBY_CLOUD_WARN_TOKEN_LIMIT` | `150000` | Monthly warn (exists) |
| `YBY_CLOUD_WARN_DAILY_TOKEN_LIMIT` | `40000` | Daily warn |
| `YBY_CLOUD_WARN_RATIO` | `0.8` | Warn when used ≥ 80% of any hard cap |

Windows: **UTC calendar** day/month (document; keep consistent with current `gmtime` monthly rollup).

### 7.2 Actions

| Band | Action |
|---|---|
| Below warn | Allow; confirm per §6 |
| Warn ≤ used < hard | Allow + warn message + force confirm |
| used ≥ hard | **Block**; log `blocked_budget` |
| Explicit exception | Allow one (or N) completed calls; log `exception_granted` then normal events |

### 7.3 Explicit exception

- CLI flag or env one-shot: `YBY_CLOUD_BUDGET_EXCEPTION=1` for current process, or `--cloud-exception` on `yby ask`.
- Must be **user-initiated**; never set by routing heuristics.
- Exception does **not** bypass `local_only`, authz deny, or missing credentials.
- Each use logged with `meta.exception=true`.

### 7.4 No OpenRouter auto-fallback

Provider selection remains **config-explicit** (primary cloud endpoint/model from env). Failure of OpenRouter must **not** cascade to Grok/xAI (or the reverse) unless the user configured that provider as the sole/primary target and re-confirmed. D12 + issue #42.

---

## 8. Sanitization & local-first security

### 8.1 Rules

1. Registry stores **metadata + hashes/refs only**.
2. Outbound payload must pass `CloudSanitizer.sanitize(text) -> SanitizedPayload`.
3. **Vault paths / Obsidian content** require explicit authz flag for the session (`YBY_CLOUD_ALLOW_VAULT=0` default). Without it: strip or refuse (`blocked_authz`).
4. API keys never appear in logs, exceptions, or confirm prompts.
5. Offline / `local_only`: zero egress; registry still writable on local disk.
6. Redaction patterns: API keys, bearer tokens, passwords, CPF/CNPJ, emails (reuse/replace `openrouter_sanitizer.py` under a stable API).

### 8.2 Proposed `src/security/` surface

| Symbol | Responsibility |
|---|---|
| `cloud_sanitizer.py` | Redact + stats; successor API to `openrouter_sanitizer.py` |
| `cloud_authz.py` | Decide if vault/refs allowed; session grants |
| `prompt_hash.py` | SHA-256 over sanitized UTF-8 |
| *(existing)* `ast_guard.py` | Unchanged |

### 8.3 Proposed engine modules (evolution)

| Module | Change |
|---|---|
| `cloud_usage_log.py` | Become façade or thin JSONL mirror; SQLite in `cloud_usage_db.py` |
| `budget.py` | Daily+monthly; cost; exception; warn code |
| `routing.py` | Unchanged decision logic; may attach `codes` consumed by confirm UX |
| `hybrid.py` | Call authz → budget → registry → provider (implementation slice) |

---

## 9. Telemetry contract (local)

**Name:** `yby.cloud_usage.v1`  
**Transport:** SQLite row insert/update only (optional JSONL mirror).  
**PII:** none by default.  
**Retention:** prune `completed`/`failed` older than `YBY_CLOUD_RETENTION_DAYS` (default `90`); keep `blocked_*` summary optional.

Event lifecycle:

1. Emit `requested` with prompt_hash, estimates, session/task ids.  
2. Optionally `confirmed` / `exception_granted`.  
3. Terminal: `completed` | `failed` | `cancelled` | `blocked_*`.

Consumers: `CloudBudget` rollups, future `yby doctor` / local report CLI — **not** remote analytics.

Aligns with bare-metal SQLite bias in `docs/OBSERVABILITY.md` without coupling to MQTT traces.

---

## 10. Acceptance criteria (spec → implementation)

1. With SQLite enabled, **no** provider HTTP call occurs unless a `requested` row exists for that attempt id/session.
2. Confirm prompt appears when cost/token/policy triggers fire; cancel → `cancelled`, no HTTP.
3. Daily or monthly hard cap → block + `blocked_budget`; exception path documented and logged.
4. `YBY_CLOUD_MODE=local_only` and airplane mode: local ask still works; no crash on missing network.
5. Inserting forbidden keys into registry raises; file mode `0600`.
6. JSONL history importable; dual-write toggle works.
7. Vault content not sent when `YBY_CLOUD_ALLOW_VAULT=0`.
8. D11 unchanged: voice default remains local STT/TTS.
9. No automatic OpenRouter↔Grok failover.
10. Unit tests cover budget bands, sanitizer, registry schema, confirm short-circuit (see §12).

---

## 11. Example JSON document (schema sample)

```json
{
  "timestamp": 1763472000.0,
  "provider": "openrouter",
  "model": "openrouter/free",
  "purpose": "route_cloud",
  "input_tokens": 420,
  "output_tokens": 180,
  "estimated_cost_usd": 0.0,
  "status": "completed",
  "session_id": "sess_01HZX…",
  "task_id": "ask_42",
  "prompt_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "prompt_ref": null,
  "result_ref": null,
  "result": "cloud_completed",
  "error_code": null,
  "meta": {"reasons": ["flag --heavy"], "warn": false}
}
```

---

## 12. Test cases (for later implementation PR)

| ID | Case | Expect |
|---|---|---|
| T1 | Append event missing `provider` | Validation error |
| T2 | Event with `api_key` in meta | Rejected |
| T3 | Monthly tokens at cap | `blocked_budget`, no HTTP |
| T4 | Daily warn band | Allowed + warn + confirm forced |
| T5 | Confirm declined | `cancelled`, no HTTP |
| T6 | No TTY, confirm required | `blocked_no_tty` |
| T7 | `local_only` | `blocked_local_only`; local path OK |
| T8 | JSONL import | Row count matches valid lines |
| T9 | Sanitizer strips `sk-` key in outbound | Redacted before provider |
| T10 | Vault ref without authz | `blocked_authz` |
| T11 | Exception flag under hard cap | One completed allowed; logged |
| T12 | Offline local ask | Success without registry cloud completed |
| T13 | Cost estimate for free model | `0.0` |
| T14 | Dual-write mirror | SQLite + JSONL line both present |

---

## 13. Small-slice implementation plan

Docs-only landed with this file. Code slices (separate PRs, minimal diffs):

| Slice | Deliverable | Risk |
|---|---|---|
| **S0** | This spec + SECURITY/.env comments | None (docs) |
| **S1** | `cloud_usage_db.py` + Pydantic models + JSONL import; façade keeps `CloudUsageLog.append` API | Low |
| **S2** | Budget daily+cost+exception; tests T3/T4/T11 | Low |
| **S3** | Wire hybrid: registry before HTTP; status updates; confirm UX with cost | Medium |
| **S4** | `src/security/cloud_sanitizer.py` + authz gate; deprecate direct use of legacy sanitizer | Medium |
| **S5** | Dual-write off by default; doctor/report; retention prune | Low |

**Do not** in any slice: change D11 defaults; add OpenRouter auto-fallback; add ORMs/billing SDKs; upload registry off-machine.

---

## 14. File touch list (future code)

- `src/engine/cloud_usage_db.py` (new)
- `src/engine/cloud_usage_log.py` (façade / mirror)
- `src/engine/budget.py` (policy)
- `src/engine/hybrid.py` (gate order)
- `src/engine/routing.py` (UX codes only if needed)
- `src/security/cloud_sanitizer.py`, `cloud_authz.py`, `prompt_hash.py`
- `tests/test_cloud_usage_*.py`, `tests/test_budget.py`
- `.env.example`, `docs/SECURITY.md` (kept in sync)

---

## 15. References

- Issue [#42](https://github.com/FRANK1-AZZA-Tekk/yby-seed/issues/42)
- `DECISIONS.md` — D11, D12, D13
- `docs/PLANEJAMENTO-CUSTOS-IA.md` — cost pyramid (human planning)
- `docs/OBSERVABILITY.md` — local SQLite preference
- Baseline code: `src/engine/cloud_usage_log.py`, `budget.py`, `hybrid.py`
