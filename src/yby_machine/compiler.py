"""Compilador determinístico: YBYSpec → bundle PWA (HTML/CSS/JS). Sem LLM."""

from __future__ import annotations

import json
from typing import Mapping

from src.yby_machine.spec import YBYSpec

# Tema YBY (offline-first)
_BG = "#0D0D0D"
_FG = "#F5F5F2"
_ACCENT = "#00FF66"


def compile_pwa(spec: YBYSpec) -> dict[str, str]:
    """Retorna mapa filename → conteúdo UTF-8 do PWA offline."""

    spec_json = json.dumps(spec.model_dump(mode="json"), ensure_ascii=False, indent=2)
    return {
        "index.html": _html(spec),
        "styles.css": _css(),
        "app.js": _app_js(spec_json),
        "manifest.webmanifest": _manifest(spec),
        "sw.js": _service_worker(),
        "spec.json": spec_json + "\n",
    }


def write_pwa(spec: YBYSpec, out_dir: str | Mapping[str, str] | None = None) -> dict[str, str]:
    """Compila e, se `out_dir` for str, grava os arquivos no diretório."""

    from pathlib import Path

    bundle = compile_pwa(spec)
    if isinstance(out_dir, str) and out_dir:
        root = Path(out_dir)
        root.mkdir(parents=True, exist_ok=True)
        for name, content in bundle.items():
            (root / name).write_text(content, encoding="utf-8")
    return bundle


# CSP offline: só mesmos assets; wa.me é navegação (a href), não fetch.
_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "manifest-src 'self'; "
    "worker-src 'self'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "object-src 'none'; "
    "frame-ancestors 'none'"
)


def _html(spec: YBYSpec) -> str:
    title = _esc(spec.title)
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="theme-color" content="{_BG}" />
  <meta name="color-scheme" content="dark" />
  <meta http-equiv="Content-Security-Policy" content="{_CSP}" />
  <title>{title}</title>
  <link rel="manifest" href="manifest.webmanifest" />
  <link rel="stylesheet" href="styles.css" />
</head>
<body>
  <header class="top">
    <p class="brand">YBY</p>
    <h1 id="app-title">{title}</h1>
    <p class="sub" id="app-desc"></p>
  </header>
  <main>
    <section class="panel" id="form-panel">
      <h2>Novo registro</h2>
      <form id="record-form"></form>
      <div class="row actions" id="form-actions"></div>
    </section>
    <section class="panel">
      <h2>Registros</h2>
      <ul id="record-list" class="list"></ul>
    </section>
  </main>
  <footer class="foot">
    <span>Offline-first · Spec-First · dados no aparelho (localStorage)</span>
  </footer>
  <script src="app.js"></script>
</body>
</html>
"""


def _css() -> str:
    return f""":root {{
  --bg: {_BG};
  --fg: {_FG};
  --accent: {_ACCENT};
  --muted: #8a8a86;
  --panel: #161616;
  --border: #2a2a2a;
  font-family: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background:
    radial-gradient(ellipse at 20% 0%, #123322 0%, transparent 45%),
    radial-gradient(ellipse at 100% 100%, #1a1a12 0%, transparent 40%),
    var(--bg);
  color: var(--fg);
}}
.top {{
  padding: 1.5rem 1.25rem 0.75rem;
  border-bottom: 1px solid var(--border);
}}
.brand {{
  margin: 0;
  letter-spacing: 0.28em;
  font-size: 0.75rem;
  color: var(--accent);
  font-weight: 700;
}}
h1 {{
  margin: 0.35rem 0 0.25rem;
  font-size: 1.6rem;
  font-weight: 600;
}}
.sub {{ margin: 0; color: var(--muted); font-size: 0.95rem; }}
main {{
  max-width: 720px;
  margin: 0 auto;
  padding: 1rem 1.25rem 3rem;
  display: grid;
  gap: 1rem;
}}
.panel {{
  background: color-mix(in srgb, var(--panel) 92%, transparent);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 1rem;
}}
.panel h2 {{
  margin: 0 0 0.75rem;
  font-size: 1rem;
  font-weight: 600;
  color: var(--accent);
}}
label {{
  display: block;
  margin: 0.65rem 0 0.25rem;
  font-size: 0.85rem;
  color: var(--muted);
}}
input, select, textarea {{
  width: 100%;
  padding: 0.55rem 0.65rem;
  border: 1px solid var(--border);
  border-radius: 3px;
  background: #0a0a0a;
  color: var(--fg);
  font: inherit;
}}
.row.actions {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 1rem;
}}
button {{
  appearance: none;
  border: 1px solid var(--accent);
  background: transparent;
  color: var(--accent);
  padding: 0.55rem 0.9rem;
  border-radius: 3px;
  font: inherit;
  cursor: pointer;
}}
button.primary {{
  background: var(--accent);
  color: #04120a;
  font-weight: 600;
}}
button:disabled {{ opacity: 0.45; cursor: not-allowed; }}
.list {{
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.65rem;
}}
.list li {{
  border: 1px solid var(--border);
  padding: 0.75rem;
  border-radius: 3px;
}}
.list .meta {{ color: var(--muted); font-size: 0.85rem; margin-top: 0.35rem; }}
.list .btns {{ margin-top: 0.55rem; display: flex; flex-wrap: wrap; gap: 0.4rem; }}
.status {{
  display: inline-block;
  margin-top: 0.35rem;
  padding: 0.15rem 0.4rem;
  border: 1px solid var(--border);
  font-size: 0.75rem;
}}
.foot {{
  text-align: center;
  color: var(--muted);
  font-size: 0.75rem;
  padding: 1rem;
}}
.empty {{ color: var(--muted); font-size: 0.9rem; }}
"""


def _manifest(spec: YBYSpec) -> str:
    payload = {
        "name": spec.title,
        "short_name": spec.name[:12],
        "start_url": "./index.html",
        "display": "standalone",
        "background_color": _BG,
        "theme_color": _BG,
        "lang": "pt-BR",
        "description": spec.description or spec.title,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _service_worker() -> str:
    return """/* YBY Machine SW — cache estático offline */
const CACHE = "yby-machine-v2";
const ASSETS = [
  "./",
  "./index.html",
  "./styles.css",
  "./app.js",
  "./manifest.webmanifest",
  "./spec.json"
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  event.respondWith(
    caches.match(event.request).then((hit) => hit || fetch(event.request))
  );
});
"""


def _app_js(spec_json: str) -> str:
    # Spec embutida + fetch de spec.json como reforço
    return f"""/* YBY Machine — runtime Spec-First (gerado; não editar à mão) */
(function () {{
  "use strict";

  const EMBEDDED_SPEC = {spec_json};
  const STORAGE_KEY = "yby_machine_" + (EMBEDDED_SPEC.name || "app");

  const TYPE_HINTS = {{
    cpf: "000.000.000-00",
    cnpj: "00.000.000/0000-00",
    cep: "00000-000",
    telefone_br: "(11) 90000-0000",
    moeda_brl: "0,00",
    numero: "0",
    data: "AAAA-MM-DD",
    texto: ""
  }};

  function $(id) {{ return document.getElementById(id); }}

  function loadRecords() {{
    try {{
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      const data = JSON.parse(raw);
      return Array.isArray(data) ? data : [];
    }} catch (e) {{
      return [];
    }}
  }}

  function saveRecords(rows) {{
    localStorage.setItem(STORAGE_KEY, JSON.stringify(rows));
  }}

  function primaryEntity(spec) {{
    return (spec.entities && spec.entities[0]) || {{ name: "item", fields: [] }};
  }}

  function applyCalcs(spec, values) {{
    const out = Object.assign({{}}, values);
    const rules = spec.calc_rules || [];
    for (const rule of rules) {{
      const expr = String(rule.expression || "");
      let result = 0;
      if (expr.includes("*")) {{
        const parts = expr.split("*").map((p) => p.trim());
        result = parts.reduce((acc, key, i) => {{
          const n = Number(out[key]) || 0;
          return i === 0 ? n : acc * n;
        }}, 0);
      }} else if (expr.includes("+")) {{
        const parts = expr.split("+").map((p) => p.trim());
        result = parts.reduce((acc, key) => acc + (Number(out[key]) || 0), 0);
      }}
      if (rule.result_field) out[rule.result_field] = result;
    }}
    return out;
  }}

  function buildForm(spec) {{
    const form = $("record-form");
    form.innerHTML = "";
    const entity = primaryEntity(spec);
    for (const field of entity.fields || []) {{
      const label = document.createElement("label");
      label.setAttribute("for", "f_" + field.name);
      label.textContent = field.label + (field.required ? " *" : "");
      form.appendChild(label);

      let input;
      if (field.name === "pagamento" || field.type === "pagamento") {{
        input = document.createElement("select");
      }} else if (field.type === "data") {{
        input = document.createElement("input");
        input.type = "date";
      }} else if (field.type === "numero" || field.type === "moeda_brl") {{
        input = document.createElement("input");
        input.type = "number";
        input.step = field.type === "moeda_brl" ? "0.01" : "1";
      }} else {{
        input = document.createElement("input");
        input.type = "text";
        input.placeholder = TYPE_HINTS[field.type] || "";
      }}
      input.id = "f_" + field.name;
      input.name = field.name;
      if (field.required) input.required = true;
      form.appendChild(input);
    }}

    const payLabel = document.createElement("label");
    payLabel.setAttribute("for", "f_status_pagamento");
    payLabel.textContent = "Status pagamento";
    form.appendChild(payLabel);
    const pay = document.createElement("select");
    pay.id = "f_status_pagamento";
    pay.name = "status_pagamento";
    const statuses = spec.payment_statuses || ["Pago", "Pendente/Fiado", "Sinal 50%"];
    for (const s of statuses) {{
      const opt = document.createElement("option");
      opt.value = s;
      opt.textContent = s;
      pay.appendChild(opt);
    }}
    form.appendChild(pay);

    const actions = $("form-actions");
    actions.innerHTML = "";
    const saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.className = "primary";
    saveBtn.textContent = "Salvar";
    saveBtn.addEventListener("click", () => onSave(spec));
    actions.appendChild(saveBtn);
  }}

  function readForm(spec) {{
    const entity = primaryEntity(spec);
    const values = {{}};
    for (const field of entity.fields || []) {{
      const el = $("f_" + field.name);
      if (!el) continue;
      values[field.name] = el.type === "number" ? Number(el.value) : el.value;
    }}
    const pay = $("f_status_pagamento");
    if (pay) values.status_pagamento = pay.value;
    return applyCalcs(spec, values);
  }}

  function clearForm(spec) {{
    const entity = primaryEntity(spec);
    for (const field of entity.fields || []) {{
      const el = $("f_" + field.name);
      if (el) el.value = "";
    }}
  }}

  function onSave(spec) {{
    const form = $("record-form");
    if (!form.reportValidity()) return;
    const values = readForm(spec);
    values.id = String(Date.now());
    values.created_at = new Date().toISOString();
    const rows = loadRecords();
    rows.unshift(values);
    saveRecords(rows);
    clearForm(spec);
    renderList(spec);
  }}

  function fieldTypeMap(spec) {{
    const map = {{}};
    const entity = primaryEntity(spec);
    for (const field of entity.fields || []) {{
      map[field.name] = field.type;
    }}
    return map;
  }}

  function formatValue(key, value, types) {{
    if (value == null || value === "") return "";
    if (types[key] === "moeda_brl" || key === "total") {{
      const n = Number(value);
      if (!Number.isNaN(n)) {{
        return n.toLocaleString("pt-BR", {{ style: "currency", currency: "BRL" }});
      }}
    }}
    return String(value);
  }}

  function summarize(row, spec) {{
    const types = fieldTypeMap(spec || EMBEDDED_SPEC);
    return Object.keys(row)
      .filter((k) => k !== "id" && k !== "created_at")
      .map((k) => k + ": " + formatValue(k, row[k], types))
      .join(" | ");
  }}

  function waLink(spec, row) {{
    const phone = (spec.whatsapp && spec.whatsapp.phone_e164) || "";
    const prefix = (spec.whatsapp && spec.whatsapp.summary_prefix) || "Resumo YBY";
    const text = encodeURIComponent(prefix + "\\n" + summarize(row, spec));
    const base = phone ? "https://wa.me/" + phone.replace(/\\D/g, "") : "https://wa.me/";
    return base + "?text=" + text;
  }}

  function renderList(spec) {{
    const list = $("record-list");
    list.innerHTML = "";
    const rows = loadRecords();
    if (!rows.length) {{
      const empty = document.createElement("li");
      empty.className = "empty";
      empty.textContent = "Nenhum registro ainda.";
      list.appendChild(empty);
      return;
    }}
    for (const row of rows) {{
      const li = document.createElement("li");
      const title = document.createElement("div");
      title.textContent = summarize(row, spec);
      li.appendChild(title);
      const meta = document.createElement("div");
      meta.className = "meta";
      meta.textContent = row.created_at || "";
      li.appendChild(meta);
      const st = document.createElement("span");
      st.className = "status";
      st.textContent = row.status_pagamento || "";
      li.appendChild(st);

      const btns = document.createElement("div");
      btns.className = "btns";

      if (spec.pix && spec.pix.enabled && spec.pix.payload) {{
        const pixBtn = document.createElement("button");
        pixBtn.type = "button";
        pixBtn.textContent = spec.pix.label || "Copiar Pix";
        pixBtn.addEventListener("click", () => {{
          const label = spec.pix.label || "Copiar Pix";
          navigator.clipboard.writeText(spec.pix.payload).then(
            () => {{ pixBtn.textContent = "Copiado!"; setTimeout(() => {{
              pixBtn.textContent = label;
            }}, 1200); }},
            () => {{ alert(spec.pix.payload); }}
          );
        }});
        btns.appendChild(pixBtn);
      }}

      if (!spec.whatsapp || spec.whatsapp.enabled !== false) {{
        const wa = document.createElement("a");
        wa.href = waLink(spec, row);
        wa.target = "_blank";
        wa.rel = "noopener noreferrer";
        const waBtn = document.createElement("button");
        waBtn.type = "button";
        waBtn.textContent = "WhatsApp";
        wa.appendChild(waBtn);
        btns.appendChild(wa);
      }}

      const del = document.createElement("button");
      del.type = "button";
      del.textContent = "Apagar";
      del.addEventListener("click", () => {{
        saveRecords(loadRecords().filter((r) => r.id !== row.id));
        renderList(spec);
      }});
      btns.appendChild(del);

      li.appendChild(btns);
      list.appendChild(li);
    }}
  }}

  function boot(spec) {{
    $("app-title").textContent = spec.title || "YBY App";
    $("app-desc").textContent = spec.description || "";
    buildForm(spec);
    renderList(spec);
    if ("serviceWorker" in navigator) {{
      navigator.serviceWorker.register("./sw.js").catch(function () {{}});
    }}
  }}

  boot(EMBEDDED_SPEC);
}})();
"""


def _esc(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
