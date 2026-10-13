"""Prototype renderer: synthesizes a self-contained WORKING DEMO HTML prototype from a PrototypeSpec.

The renderer is deterministic and spec-driven so every prototype is guaranteed to be
navigable and interactive regardless of LLM output quality. All spec content is escaped
(LLM output is treated as untrusted data).

Design (root-cause fixes for the audited defects):
- Hero call-to-action uses a dedicated `.hero-cta` class with explicit colors in ONE
  rule — no cross-rule specificity collisions (the previous `.hero .btn-primary` vs
  `main .btn-primary` collision rendered white-on-white blank buttons).
- Single source of truth: lists/cards/stats render client-side from one STORE object
  seeded from the spec sample data. Dashboard metrics therefore always agree with the
  displayed records, and every form submission visibly mutates shared state.
- Every data region has an explicit empty state; stats bound to empty lists show 0.
- Role simulation, cross-screen flows, hash deep-links, and a flow-runner checklist
  make the prototype a functional demo, not a button gallery.
- The demo runs entirely in the browser sandbox (no backend). Storage degrades
  gracefully: in-memory state always works; localStorage persistence is attempted
  and skipped when the sandbox blocks it (e.g. preview iframes without same-origin).
"""

import html
import json
import re


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_") or "items"


def _seed_json(seed: dict) -> str:
    """Serialize the store seed safely for inline <script> (breaks </script> jailbreaks)."""
    return json.dumps(seed, default=str).replace("<", "\\u003c")


def build_seed(spec) -> dict[str, list[str]]:
    """Normalize spec sample data into store lists keyed by slug."""
    seed: dict[str, list[str]] = {}
    for key, values in (getattr(spec, "sample_data", None) or {}).items():
        if isinstance(values, list) and values:
            seed[_slug(key)] = [str(v) for v in values]
    return seed


def resolve_key(items: list[str], seed: dict[str, list[str]]) -> str | None:
    """Map a section's display items back to the store list they were taken from."""
    items = [str(i) for i in (items or [])]
    if not items:
        return None
    for key, values in seed.items():
        if items == values[: len(items)] and len(items) >= min(2, len(values)):
            return key
    for key, values in seed.items():
        if all(i in values for i in items):
            return key
    return None


def resolve_stat_key(label: str, seed: dict[str, list[str]]) -> str | None:
    slug = _slug(label)
    for key in seed:
        if slug == key or slug in key or key in slug:
            return key
    return None


def _status_of(item: str) -> str:
    lowered = str(item).lower()
    if any(w in lowered for w in ("confirmed", "completed", "delivered", "done", "approved", "passed")):
        return "Completed"
    if any(w in lowered for w in ("pending", "preparing", "processing", "waiting")):
        return "Pending"
    if any(w in lowered for w in ("cancel", "failed", "rejected")):
        return "Cancelled"
    return "Active"


def _render_hero(section, spec) -> str:
    label = (section.title or "").strip() or "Explore the Prototype"
    parts = [f'<div class="hero"><h1>{esc(section.title or getattr(spec, "app_name", "Prototype"))}</h1>']
    if section.subtitle:
        parts.append(f"<p>{esc(section.subtitle)}</p>")
    parts.append(f'<button class="hero-cta" onclick="nextScreen()">{esc(label) if (section.title or "").strip() else "Explore the Prototype"}</button></div>')
    # Hero CTA label: when the section carries its own title it describes the screen;
    # the primary action always has a visible, non-empty label (validated).
    return "".join(parts)


def _render_stats(section, seed: dict) -> str:
    cards = []
    for s in section.stats:
        key = resolve_stat_key(s.label, seed)
        if key is not None:
            cards.append(
                f'<div class="stat-card"><div class="stat-value" data-stat="{esc(key)}">{len(seed[key])}</div>'
                f'<div class="stat-label">{esc(s.label)}</div></div>'
            )
        else:
            cards.append(
                f'<div class="stat-card"><div class="stat-value">{esc(s.value)}</div>'
                f'<div class="stat-label">{esc(s.label)}</div></div>'
            )
    title = f"<h2>{esc(section.title)}</h2>" if section.title else ""
    return f'<div>{title}<div class="stats-grid">{"".join(cards)}</div></div>'


def _render_cards(section, seed: dict) -> str:
    key = resolve_key([str(i) for i in section.items], seed)
    title = f"<h2>{esc(section.title)}</h2>" if section.title else ""
    subtitle = f'<p class="muted">{esc(section.subtitle)}</p>' if section.subtitle else ""
    grid_attrs = f' class="cards-grid" data-store="{esc(key)}"' if key else ' class="cards-grid"'
    static_cards = ""
    if key is None:
        static_cards = "".join(
            f'<div class="card-item"><h3>{esc(str(item).split(" - ")[0])}</h3><p>{esc(item)}</p></div>'
            for item in section.items
        )
        if not section.items:
            static_cards = '<p class="muted">No items yet.</p>'
    return f"<div>{title}{subtitle}<div{grid_attrs}>{static_cards}</div></div>"


def _render_list(section, seed: dict) -> str:
    title_text = str(section.title or "Records")
    key = resolve_key([str(i) for i in section.items], seed)
    if "activit" in title_text.lower():
        key = "__activity__"
    title = f"<h2>{esc(section.title)}</h2>" if section.title else ""
    store_attr = f' data-store="{esc(key)}"' if key else ""
    static_rows = ""
    if key is None:
        static_rows = "".join(
            f"<tr><td>{esc(item)}</td><td><span class=\"badge\">{esc(_status_of(item))}</span></td><td></td></tr>"
            for item in section.items
        )
        if not section.items:
            static_rows = '<tr class="empty-row"><td colspan="3">No records yet.</td></tr>'
    return (
        f"<div>{title}"
        f'<table class="data-table"><thead><tr><th>Item</th><th>Status</th><th></th></tr></thead>'
        f"<tbody{store_attr}>{static_rows}</tbody></table></div>"
    )


def _render_form(section, seed: dict) -> str:
    fields_html = ""
    for f in section.fields:
        req = " required" if f.type in ("text", "email", "password", "date", "number") else ""
        if f.type == "select":
            options = "".join(f'<option value="{esc(o)}">{esc(o)}</option>' for o in (f.options or ["Option 1", "Option 2"]))
            fields_html += f'<label>{esc(f.label)}<select name="{esc(f.name)}"{req}>{options}</select></label>'
        elif f.type == "textarea":
            fields_html += f'<label>{esc(f.label)}<textarea name="{esc(f.name)}" rows="3"></textarea></label>'
        else:
            fields_html += (
                f'<label>{esc(f.label)}<input type="{esc(f.type)}" name="{esc(f.name)}" '
                f'placeholder="Enter {esc(f.label.lower())}"{req}></label>'
            )
    form_id = "form-" + _slug(section.title or "form")
    title = f"<h2>{esc(section.title)}</h2>" if section.title else ""
    return (
        f'<div>{title}<form id="{form_id}" class="form-grid" data-form="{form_id}" '
        f"onsubmit=\"return submitStoreForm('{form_id}')\">"
        f"{fields_html}"
        f'<div class="form-actions"><button type="submit" class="btn btn-primary">Submit</button>'
        f'<button type="reset" class="btn btn-outline">Clear</button></div>'
        f'<p class="form-note muted">Demo: submissions are stored in this prototype session.</p></form></div>'
    )


def _render_detail(section, seed: dict) -> str:
    rows = "".join(
        f'<div class="detail-row"><span>{esc(str(item).split(":")[0])}</span><strong>{esc(item)}</strong></div>'
        for item in section.items
    )
    if not section.items:
        rows = '<div class="detail-row"><span>No details available yet.</span></div>'
    title = f"<h2>{esc(section.title)}</h2>" if section.title else ""
    subtitle = f'<p class="muted">{esc(section.subtitle)}</p>' if section.subtitle else ""
    return f"<div>{title}{subtitle}<div class=\"detail-panel\">{rows}</div></div>"


def _render_chart(section, seed: dict) -> str:
    values = []
    for s in section.stats:
        try:
            values.append(int(re.sub(r"[^0-9]", "", s.value) or 0))
        except Exception:
            values.append(0)
    max_val = max(values) if values else 1
    bars = ""
    for s, v in zip(section.stats, values):
        pct = int((v / max_val) * 100) if max_val else 0
        bars += (
            f'<div class="bar-row"><span class="bar-label">{esc(s.label)}</span>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{pct}%"></div></div>'
            f'<span class="bar-value">{esc(s.value)}</span></div>'
        )
    if not section.stats:
        bars = '<p class="muted">No chart data yet.</p>'
    title = f"<h2>{esc(section.title)}</h2>" if section.title else ""
    return f"<div>{title}{bars}</div>"


_RENDERERS = {
    "hero": lambda s, seed, spec: _render_hero(s, spec),
    "stats": lambda s, seed, spec: _render_stats(s, seed),
    "cards": lambda s, seed, spec: _render_cards(s, seed),
    "list": lambda s, seed, spec: _render_list(s, seed),
    "form": lambda s, seed, spec: _render_form(s, seed),
    "detail": lambda s, seed, spec: _render_detail(s, seed),
    "chart": lambda s, seed, spec: _render_chart(s, seed),
}

MAX_PRIMARY_NAV = 6


def render_screen(screen, seed: dict, spec) -> str:
    body = "".join(_RENDERERS.get(s.type, _render_cards)(s, seed, spec) for s in screen.sections)
    name = esc(screen.name)
    admin_only = "admin" in str(screen.name).lower()
    role_attr = ' data-admin="1"' if admin_only else ""
    return f'<section class="screen" id="screen-{name}" data-title="{esc(screen.title)}" data-screen="{name}"{role_attr}>{body}</section>'


def step_to_screen(step: str, screens: list) -> str | None:
    """Map a user-flow step to the best-matching screen (drives the flow runner)."""
    words = [w for w in re.sub(r"[^a-z0-9 ]", " ", str(step).lower()).split() if len(w) > 3]
    best, best_score = None, 0
    for s in screens:
        name_words = set(re.sub(r"[^a-z0-9 ]", " ", str(s.name).lower()).split())
        score = sum(1 for w in words if w in name_words or any(w in nw or nw in w for nw in name_words if len(nw) > 3))
        if score > best_score:
            best, best_score = s.name, score
    return best


def render_prototype(spec) -> str:
    """Render the full self-contained working-demo HTML prototype from a PrototypeSpec."""
    theme = spec.theme
    seed = build_seed(spec)
    roles = list(getattr(spec, "roles", None) or [])
    nav_names = [s.name for s in spec.screens]
    ordered_nav = list(spec.navigation or nav_names)
    primary_nav = ordered_nav[:MAX_PRIMARY_NAV]
    overflow_nav = ordered_nav[MAX_PRIMARY_NAV:]
    nav_buttons = "".join(
        f'<button class="nav-btn" data-screen="{esc(name)}" onclick="showScreen(this.dataset.screen)">{esc(name)}</button>'
        for name in primary_nav
    )
    if overflow_nav:
        overflow = "".join(
            f'<button class="nav-btn" data-screen="{esc(name)}" onclick="showScreen(this.dataset.screen)">{esc(name)}</button>'
            for name in overflow_nav
        )
        nav_buttons += f'<details class="nav-more"><summary class="nav-btn">More</summary><div class="nav-more-menu">{overflow}</div></details>'
    screens_html = "".join(render_screen(s, seed, spec) for s in spec.screens)
    first_screen = ordered_nav[0] if ordered_nav else ""

    flow_items = []
    for idx, step in enumerate(spec.user_flow):
        target = step_to_screen(step, spec.screens)
        goto = f' data-goto="{esc(target)}"' if target else ""
        flow_items.append(
            f'<li class="flow-step" data-step="{idx}"><button class="btn btn-outline btn-sm" onclick="runFlowStep(this)"{goto}>Open</button>'
            f'<span>{esc(step)}</span><span class="flow-done" hidden>✓</span></li>'
        )
    flow_html = "".join(flow_items)
    features_html = "".join(f"<li>{esc(f)}</li>" for f in spec.features)
    role_pills = ""
    if roles:
        role_pills = '<div class="role-bar"><span>Viewing as:</span>' + "".join(
            f'<button class="role-pill" data-role="{esc(r)}" onclick="setRole(this.dataset.role)">{esc(r)}</button>'
            for r in roles
        ) + "</div>"
    info_screen = (
        '<section class="screen" id="screen-About" data-title="About this Prototype" data-screen="About">'
        '<h2>Prototype Flow</h2><p class="muted">Work through the journey — each step opens its screen.</p>'
        f'<ol class="flow-list">{flow_html}</ol>'
        f"<h2>Features Demonstrated</h2><ul class=\"flow-list\">{features_html}</ul>"
        '<p class="muted">Working demo: records you create, role selection and flow progress live in this browser session. '
        "Demo data is simulated locally; nothing is sent to a server.</p>"
        "</section>"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(spec.app_name)} — Prototype</title>
<style>
  :root {{ --primary: {esc(theme.primary_color)}; --accent: {esc(theme.accent_color)}; --bg: {esc(theme.background_color)}; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: var(--bg); color: #1e293b; }}
  .proto-banner {{ background: #0f172a; color: #e2e8f0; font-size: 12px; padding: 6px 16px; display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; }}
  .proto-banner strong {{ color: #a5b4fc; }}
  .role-bar {{ display: flex; align-items: center; gap: 6px; font-size: 12px; }}
  .role-pill {{ border: 1px solid #334155; background: transparent; color: #cbd5e1; padding: 3px 10px; border-radius: 999px; cursor: pointer; font-size: 12px; }}
  .role-pill.active {{ background: var(--primary); border-color: var(--primary); color: #fff; }}
  .navbar {{ background: #fff; border-bottom: 1px solid #e2e8f0; padding: 12px 20px; display: flex; align-items: center; gap: 10px; overflow-x: auto; }}
  .brand {{ font-weight: 700; font-size: 17px; color: var(--primary); margin-right: 12px; white-space: nowrap; }}
  .nav-btn {{ border: 1px solid #e2e8f0; background: #fff; color: #475569; padding: 7px 14px; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 500; white-space: nowrap; }}
  .nav-btn:hover {{ border-color: var(--primary); color: var(--primary); }}
  .nav-btn.active {{ background: var(--primary); border-color: var(--primary); color: #fff; }}
  .nav-more {{ position: relative; }}
  .nav-more summary {{ list-style: none; }}
  .nav-more-menu {{ position: absolute; z-index: 20; background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 8px; display: grid; gap: 6px; min-width: 220px; box-shadow: 0 10px 30px rgba(15,23,42,.12); }}
  main {{ max-width: 980px; margin: 0 auto; padding: 24px 20px 60px; }}
  .screen {{ display: none; animation: fadeIn .25s ease; }}
  .screen.active {{ display: block; }}
  @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(4px); }} to {{ opacity: 1; transform: none; }} }}
  h1 {{ font-size: 30px; margin-bottom: 10px; }}
  h2 {{ font-size: 19px; margin: 22px 0 12px; }}
  p.muted {{ color: #64748b; font-size: 14px; margin-bottom: 12px; }}
  .hero {{ background: linear-gradient(135deg, var(--primary), var(--accent)); color: #fff; border-radius: 16px; padding: 42px 32px; margin-bottom: 8px; }}
  .hero h1 {{ color: #fff; }}
  .hero p {{ opacity: .92; margin-bottom: 18px; max-width: 560px; }}
  .hero-cta {{ border: none; border-radius: 8px; padding: 10px 18px; font-size: 14px; font-weight: 600; cursor: pointer; background: #ffffff; color: var(--primary); }}
  .hero-cta:hover {{ transform: translateY(-1px); }}
  .btn {{ border: none; border-radius: 8px; padding: 10px 18px; font-size: 14px; font-weight: 600; cursor: pointer; transition: all .15s; }}
  .btn-primary {{ background: var(--primary); color: #ffffff; }}
  .btn-outline {{ background: #fff; color: #475569; border: 1px solid #e2e8f0; }}
  .btn-sm {{ padding: 6px 12px; font-size: 12px; }}
  .btn:hover {{ transform: translateY(-1px); }}
  .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }}
  .stat-card {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px; }}
  .stat-value {{ font-size: 24px; font-weight: 700; color: var(--primary); }}
  .stat-label {{ font-size: 12px; color: #64748b; margin-top: 4px; }}
  .cards-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 12px; }}
  .card-item {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; }}
  .card-item h3 {{ font-size: 15px; margin-bottom: 6px; }}
  .card-item p {{ font-size: 13px; color: #64748b; margin-bottom: 10px; }}
  .data-table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; }}
  .data-table th {{ text-align: left; background: #f1f5f9; font-size: 12px; text-transform: uppercase; color: #475569; padding: 10px 14px; }}
  .data-table td {{ padding: 11px 14px; border-top: 1px solid #e2e8f0; font-size: 14px; }}
  .empty-row td {{ color: #64748b; font-style: italic; text-align: center; padding: 18px 14px; }}
  .badge {{ font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 999px; background: #eef2ff; color: var(--primary); }}
  .form-grid {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
  .form-grid label {{ font-size: 13px; font-weight: 600; color: #475569; display: grid; gap: 6px; grid-column: span 1; }}
  .form-grid input, .form-grid select, .form-grid textarea {{ border: 1px solid #cbd5e1; border-radius: 8px; padding: 9px 12px; font-size: 14px; font-family: inherit; }}
  .form-grid input:focus, .form-grid select:focus, .form-grid textarea:focus {{ outline: 2px solid var(--primary); outline-offset: -1px; }}
  .form-actions {{ grid-column: 1 / -1; display: flex; gap: 10px; }}
  .form-note {{ grid-column: 1 / -1; }}
  .detail-panel {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 8px 18px; }}
  .detail-row {{ display: flex; justify-content: space-between; gap: 20px; padding: 11px 0; border-bottom: 1px solid #f1f5f9; font-size: 14px; color: #64748b; }}
  .detail-row:last-child {{ border-bottom: none; }}
  .bar-row {{ display: grid; grid-template-columns: 140px 1fr 60px; gap: 12px; align-items: center; margin-bottom: 10px; font-size: 13px; }}
  .bar-track {{ background: #e2e8f0; border-radius: 999px; height: 10px; overflow: hidden; }}
  .bar-fill {{ background: linear-gradient(90deg, var(--primary), var(--accent)); height: 100%; border-radius: 999px; transition: width .4s; }}
  .flow-list {{ margin-left: 6px; display: grid; gap: 8px; font-size: 14px; color: #334155; list-style: none; }}
  .flow-step {{ display: flex; align-items: center; gap: 10px; background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; }}
  .flow-step.done {{ border-color: var(--primary); }}
  .flow-done {{ color: var(--primary); font-weight: 700; }}
  .toast {{ position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%) translateY(80px); background: #0f172a; color: #fff; padding: 11px 20px; border-radius: 10px; font-size: 13px; opacity: 0; transition: all .3s; z-index: 50; max-width: 90vw; }}
  .toast.show {{ transform: translateX(-50%) translateY(0); opacity: 1; }}
  @media (max-width: 640px) {{
    .form-grid {{ grid-template-columns: 1fr; }}
    .form-grid label {{ grid-column: 1 / -1; }}
    .hero {{ padding: 28px 20px; }}
    h1 {{ font-size: 24px; }}
    .bar-row {{ grid-template-columns: 90px 1fr 48px; }}
  }}
</style>
</head>
<body>
<div class="proto-banner"><span><strong>INTERACTIVE PROTOTYPE</strong> — built by AgentForge for concept validation</span>{role_pills}<span>{esc(spec.app_name)}</span></div>
<nav class="navbar" aria-label="Prototype screens">
  <span class="brand">{esc(spec.app_name)}</span>
  {nav_buttons}
</nav>
<main>
  {screens_html}
  {info_screen}
</main>
<div class="toast" id="toast" role="status"></div>
<script>
  var SEED = {_seed_json(seed)};
  var STORE = {{ records: JSON.parse(JSON.stringify(SEED)), role: null, activity: [], flowDone: {{}} }};
  try {{
    var saved = null;
    try {{ saved = window.localStorage ? window.localStorage.getItem("agentforge-proto") : null; }} catch (e) {{ saved = null; }}
    if (saved) {{ STORE = JSON.parse(saved); }}
  }} catch (e) {{}}
  function persist() {{
    try {{ if (window.localStorage) window.localStorage.setItem("agentforge-proto", JSON.stringify(STORE)); }} catch (e) {{}}
  }}
  function escHtml(s) {{
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {{
      return {{"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}}[c];
    }});
  }}
  function statusOf(item) {{
    var v = String(item).toLowerCase();
    if (/confirmed|completed|delivered|done|approved|passed/.test(v)) return "Completed";
    if (/pending|preparing|processing|waiting/.test(v)) return "Pending";
    if (/cancel|failed|reject/.test(v)) return "Cancelled";
    return "Active";
  }}
  var CURRENT = {json.dumps(first_screen)};
  function showScreen(name) {{
    document.querySelectorAll('.screen').forEach(function (s) {{ s.classList.remove('active'); }});
    var el = null;
    document.querySelectorAll('.screen').forEach(function (s) {{
      if (s.getAttribute('data-screen') === name) el = s;
    }});
    if (el) el.classList.add('active');
    document.querySelectorAll('.nav-btn').forEach(function (b) {{ b.classList.toggle('active', b.dataset.screen === name); }});
    CURRENT = name;
    try {{ window.location.hash = "screen/" + encodeURIComponent(name); }} catch (e) {{}}
    window.scrollTo({{ top: 0, behavior: 'smooth' }});
  }}
  function nextScreen() {{
    var btns = Array.prototype.slice.call(document.querySelectorAll('.navbar .nav-btn'));
    var idx = btns.findIndex(function (b) {{ return b.dataset.screen === CURRENT; }});
    if (idx >= 0 && idx < btns.length - 1) showScreen(btns[idx + 1].dataset.screen);
  }}
  function renderStoreRegions() {{
    document.querySelectorAll('[data-store]').forEach(function (region) {{
      var key = region.getAttribute('data-store');
      var items = key === '__activity__' ? STORE.activity.slice().reverse() : (STORE.records[key] || []);
      var title = region.closest('div') ? '' : '';
      if (region.tagName === 'TBODY') {{
        if (!items.length) {{
          region.innerHTML = '<tr class="empty-row"><td colspan="3">No records yet — add one with the form above or keep exploring.</td></tr>';
        }} else {{
          region.innerHTML = items.map(function (item) {{
            return '<tr><td>' + escHtml(item) + '</td><td><span class="badge">' + statusOf(item) + '</span></td>'
              + '<td><button class="btn btn-outline btn-sm" data-view-item="' + escHtml(item).replace(/"/g, '&quot;') + '">View</button></td></tr>';
          }}).join('');
        }}
      }} else {{
        if (!items.length) {{
          region.innerHTML = '<p class="muted">No items yet.</p>';
        }} else {{
          region.innerHTML = items.map(function (item) {{
            var head = escHtml(String(item).split(' - ')[0]);
            return '<div class="card-item"><h3>' + head + '</h3><p>' + escHtml(item) + '</p></div>';
          }}).join('');
        }}
      }}
    }});
    document.querySelectorAll('[data-stat]').forEach(function (el) {{
      var key = el.getAttribute('data-stat');
      el.textContent = String((STORE.records[key] || []).length);
    }});
    applyRole();
  }}
  function setRole(role) {{
    STORE.role = role;
    persist();
    document.querySelectorAll('.role-pill').forEach(function (b) {{ b.classList.toggle('active', b.dataset.role === role); }});
    applyRole();
    showToast('Viewing as ' + role);
  }}
  function applyRole() {{
    var adminScreens = document.querySelectorAll('[data-admin="1"]');
    var isAdmin = STORE.role && /admin/i.test(STORE.role);
    adminScreens.forEach(function (s) {{
      s.style.opacity = isAdmin ? '' : '.55';
    }});
    document.querySelectorAll('.role-pill').forEach(function (b) {{ b.classList.toggle('active', b.dataset.role === STORE.role); }});
  }}
  function submitStoreForm(formId) {{
    var form = document.getElementById(formId);
    if (!form.checkValidity()) {{
      form.reportValidity();
      return false;
    }}
    var values = [];
    form.querySelectorAll('input, select, textarea').forEach(function (input) {{
      if (input.value) values.push(input.name + ': ' + input.value);
    }});
    var summary = values.join(' • ') || 'New entry';
    var target = null;
    var best = 0;
    Object.keys(STORE.records).forEach(function (key) {{
      var score = 0;
      values.forEach(function (v) {{
        if (key.replace(/_/g, ' ').split(' ').some(function (w) {{ return v.toLowerCase().indexOf(w) >= 0; }})) score += 1;
      }});
      if (score > best) {{ best = score; target = key; }}
    }});
    if (!target) {{
      var keys = Object.keys(STORE.records);
      target = keys.length ? keys[keys.length - 1] : 'records';
    }}
    if (!STORE.records[target]) STORE.records[target] = [];
    STORE.records[target].unshift(summary);
    STORE.activity.unshift(new Date().toLocaleTimeString() + ' — Added to ' + target.replace(/_/g, ' ') + ': ' + summary);
    persist();
    renderStoreRegions();
    showToast('Saved to ' + target.replace(/_/g, ' ') + ': ' + summary);
    form.reset();
    return false;
  }}
  function runFlowStep(btn) {{
    var step = btn.closest('.flow-step');
    var target = btn.getAttribute('data-goto');
    var idx = step ? step.getAttribute('data-step') : null;
    if (idx !== null) {{
      STORE.flowDone[idx] = true;
      persist();
      step.classList.add('done');
      var mark = step.querySelector('.flow-done');
      if (mark) mark.hidden = false;
    }}
    if (target) showScreen(target);
  }}
  function showToast(msg) {{
    var t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(t._timer);
    t._timer = setTimeout(function () {{ t.classList.remove('show'); }}, 2600);
  }}
  document.addEventListener('click', function (ev) {{
    var btn = ev.target && ev.target.closest ? ev.target.closest('[data-view-item]') : null;
    if (btn) showToast('Viewing: ' + btn.getAttribute('data-view-item'));
  }});
  document.addEventListener('DOMContentLoaded', function () {{
    var start = CURRENT;
    try {{
      var h = window.location.hash || '';
      if (h.indexOf('#screen/') === 0) {{
        var name = decodeURIComponent(h.slice(8));
        var exists = false;
        document.querySelectorAll('.screen').forEach(function (s) {{
          if (s.getAttribute('data-screen') === name) exists = true;
        }});
        if (exists) start = name;
      }}
    }} catch (e) {{}}
    Object.keys(STORE.flowDone || {{}}).forEach(function (idx) {{
      var step = document.querySelector('.flow-step[data-step="' + idx + '"]');
      if (step) {{
        step.classList.add('done');
        var mark = step.querySelector('.flow-done');
        if (mark) mark.hidden = false;
      }}
    }});
    renderStoreRegions();
    showScreen(start);
  }});
</script>
</body>
</html>"""
