#!/usr/bin/env python3
"""
generate_domain_overview.py

Reads the domain contracts (OpenAPI, AsyncAPI, Data Contract YAML) and
generates a rich static HTML domain-overview page at:
  docs/specifications/domain-overview.html

Run via:  task docs:generate
"""

import os
import sys
import yaml
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
SPECS_DIR = os.path.join(REPO_ROOT, "docs", "specifications")
CONTRACTS_DIR = os.path.join(SPECS_DIR, "contracts")
# Output path is overridable via env so the audit's GENERATOR-CLEAN-OUTPUT
# check can render to a tmp location without churning the on-disk file.
OUTPUT_FILE = os.environ.get("DOMAIN_OVERVIEW_OUTPUT") or os.path.join(
    SPECS_DIR, "domain-overview.html"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_yaml(path):
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def h(text):
    """HTML-escape a string."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


METHOD_COLORS = {
    "get":    "#61affe",
    "post":   "#49cc90",
    "patch":  "#fca130",
    "put":    "#fca130",
    "delete": "#f93e3e",
}

# Schema names ending with these suffixes are request/response helpers, not
# domain entities, and are excluded from entity and ERD sections.
_NON_ENTITY_SUFFIXES = ("Request", "Response", "Error", "List", "Pagination")


def method_badge(method):
    color = METHOD_COLORS.get(method.lower(), "#aaa")
    return (
        f'<span class="badge method-badge" '
        f'style="background:{color};color:#fff">'
        f'{h(method.upper())}</span>'
    )


def auth_badge(required):
    if required:
        return '<span class="badge auth-badge auth-required">🔒 Auth</span>'
    return '<span class="badge auth-badge auth-public">🌐 Public</span>'


def tag_badge(tag):
    return f'<span class="badge tag-badge">{h(tag)}</span>'


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def build_summary_section(openapi):
    info = openapi.get("info", {})
    title = info.get("title", "Domain")
    version = info.get("version", "")
    description = info.get("description", "")
    contact = info.get("contact", {})

    desc_html = ""
    for line in description.strip().splitlines():
        line = line.strip()
        if line.startswith("- "):
            desc_html += f"<li>{h(line[2:])}</li>"
        elif line.startswith("**") and line.endswith("**"):
            desc_html += f"<p><strong>{h(line[2:-2])}</strong></p>"
        elif line:
            desc_html += f"<p>{h(line)}</p>"

    servers = openapi.get("servers", [])
    server_rows = "".join(
        f"<tr><td>{h(s.get('url',''))}</td><td>{h(s.get('description',''))}</td></tr>"
        for s in servers
    )

    contact_html = ""
    if contact:
        cname = contact.get("name", "")
        cemail = contact.get("email", "")
        if cname or cemail:
            contact_html = (
                f'<p class="contact">Contact: <strong>{h(cname)}</strong>'
                + (f' &lt;{h(cemail)}&gt;' if cemail else "")
                + "</p>"
            )

    return f"""
<section id="summary" class="card">
  <h2>📋 Domain Summary</h2>
  <div class="summary-header">
    <span class="domain-title">{h(title)}</span>
    <span class="domain-version badge">v{h(version)}</span>
  </div>
  <div class="description">{desc_html}</div>
  {contact_html}
  {"<h3>Servers</h3><table><thead><tr><th>URL</th><th>Description</th></tr></thead><tbody>" + server_rows + "</tbody></table>" if server_rows else ""}
</section>
"""


def _extract_roles(openapi):
    """Extract role enum values from the RegisterRequest schema."""
    schemas = openapi.get("components", {}).get("schemas", {})
    register = schemas.get("RegisterRequest", {})
    props = register.get("properties", {})
    role_prop = props.get("role", {})
    return role_prop.get("enum", [])


def build_roles_section(openapi):
    roles = _extract_roles(openapi)
    if not roles:
        return ""

    # Static descriptions — these come from what is defined in the specs.
    role_descriptions = {
        "contributor": "Can add items and edit/remove their own items.",
        "viewer": "Read-only access to items.",
    }

    rows = "".join(
        f"<tr><td><code>{h(r)}</code></td><td>{h(role_descriptions.get(r, ''))}</td></tr>"
        for r in roles
    )

    return f"""
<section id="roles" class="card">
  <h2>👤 Roles</h2>
  <table>
    <thead><tr><th>Role</th><th>Description</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <p class="note">All protected routes require a <code>Bearer</code> JWT in the
  <code>Authorization</code> header. Unauthenticated requests return
  <code>401 Unauthorized</code>.</p>
</section>
"""


def build_operations_section(openapi):
    paths = openapi.get("paths", {})
    tags_order = [t["name"] for t in openapi.get("tags", [])]

    # Group by tag
    by_tag = {}
    for path, path_item in paths.items():
        for method, op in path_item.items():
            if method.lower() not in METHOD_COLORS:
                continue
            op_tags = op.get("tags", ["Other"])
            requires_auth = bool(op.get("security"))
            for tag in op_tags:
                by_tag.setdefault(tag, []).append({
                    "method": method,
                    "path": path,
                    "summary": op.get("summary", ""),
                    "description": op.get("description", ""),
                    "auth": requires_auth,
                    "operationId": op.get("operationId", ""),
                })

    # Sort tags by declared order
    ordered_tags = [t for t in tags_order if t in by_tag] + [
        t for t in by_tag if t not in tags_order
    ]

    blocks = []
    for tag in ordered_tags:
        ops = by_tag[tag]
        rows = ""
        for op in ops:
            rows += (
                f"<tr>"
                f"<td>{method_badge(op['method'])}</td>"
                f"<td><code>{h(op['path'])}</code></td>"
                f"<td>{h(op['summary'])}</td>"
                f"<td>{auth_badge(op['auth'])}</td>"
                f"</tr>"
            )
        blocks.append(f"""
<h3>{h(tag)}</h3>
<table>
  <thead><tr><th>Method</th><th>Path</th><th>Summary</th><th>Auth</th></tr></thead>
  <tbody>{rows}</tbody>
</table>
""")

    return f"""
<section id="operations" class="card">
  <h2>🔌 API Operations</h2>
  {"".join(blocks)}
</section>
"""


def build_events_section(asyncapi):
    channels = asyncapi.get("channels", {})
    messages = asyncapi.get("components", {}).get("messages", {})
    info = asyncapi.get("info", {})

    rows = ""
    for channel_name, channel in channels.items():
        pub = channel.get("publish", {})
        msg_ref = pub.get("message", {}).get("$ref", "")
        msg_name = msg_ref.split("/")[-1] if msg_ref else ""
        msg = messages.get(msg_name, {})
        title = msg.get("title", msg_name)
        summary = msg.get("summary", pub.get("description", ""))
        rows += (
            f"<tr>"
            f"<td><code>{h(channel_name)}</code></td>"
            f"<td><strong>{h(title)}</strong></td>"
            f"<td>{h(summary)}</td>"
            f"</tr>"
        )

    return f"""
<section id="events" class="card">
  <h2>📡 Domain Events</h2>
  <p>{h(info.get('description', '').splitlines()[0] if info.get('description') else '')}</p>
  <table>
    <thead><tr><th>Channel</th><th>Event</th><th>Description</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <p class="note">All events follow the
  <a href="https://cloudevents.io/" target="_blank" rel="noopener">CloudEvents 1.0</a>
  specification.</p>
</section>
"""


def build_event_operation_correlation(openapi, asyncapi):
    """
    Derive event↔operation mappings from channel name conventions.
    e.g. items.item.added  → POST (add)   /v1/items
         items.item.edited → PATCH (edit) /v1/items/{itemId}
         items.item.removed → DELETE      /v1/items/{itemId}
    """
    channel_to_method = {
        "added":   ("POST",   "Add"),
        "edited":  ("PATCH",  "Edit"),
        "removed": ("DELETE", "Remove"),
    }

    channels = asyncapi.get("channels", {})
    messages = asyncapi.get("components", {}).get("messages", {})
    paths = openapi.get("paths", {})

    rows = ""
    for channel_name, channel in channels.items():
        # e.g. items.item.added → action = "added"
        action = channel_name.split(".")[-1] if "." in channel_name else channel_name
        method_info = channel_to_method.get(action)

        # Find matching OpenAPI operation
        matched_path = ""
        matched_summary = ""
        if method_info:
            http_method, verb = method_info
            for path, path_item in paths.items():
                op = path_item.get(http_method.lower(), {})
                if op and verb.lower() in op.get("summary", "").lower():
                    matched_path = path
                    matched_summary = op.get("summary", "")
                    break

        pub = channel.get("publish", {})
        msg_ref = pub.get("message", {}).get("$ref", "")
        msg_name = msg_ref.split("/")[-1] if msg_ref else ""
        msg = messages.get(msg_name, {})
        event_title = msg.get("title", msg_name)

        rows += (
            f"<tr>"
            f"<td><strong>{h(event_title)}</strong></td>"
            f"<td><code>{h(channel_name)}</code></td>"
            f"<td>"
            + (
                f"{method_badge(method_info[0])} <code>{h(matched_path)}</code> — {h(matched_summary)}"
                if method_info and matched_path else "—"
            )
            + f"</td>"
            f"</tr>"
        )

    return f"""
<section id="event-correlation" class="card">
  <h2>🔗 Operation → Event Correlation</h2>
  <p>Each write operation publishes a corresponding domain event.</p>
  <table>
    <thead><tr><th>Event</th><th>Channel</th><th>Triggered By</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</section>
"""


def _schema_type(prop):
    t = prop.get("type", "")
    fmt = prop.get("format", "")
    enum = prop.get("enum", [])
    nullable = prop.get("nullable", False)
    ref = prop.get("$ref", "")

    if ref:
        return f"→ {ref.split('/')[-1]}"
    if enum:
        # OpenAPI may include literal null in an enum (alongside nullable: true);
        # PyYAML parses that to None. Render as "null" rather than crashing on str.join.
        values = ["null" if v is None else str(v) for v in enum]
        return f"enum({', '.join(values)})"
    if fmt:
        display = f"{t}({fmt})"
    else:
        display = t
    if nullable:
        display += " | null"
    return display


def build_entities_section(openapi):
    schemas = openapi.get("components", {}).get("schemas", {})
    # Show main domain entities only (skip request/response wrappers)
    entity_names = [
        name for name in schemas
        if not any(name.endswith(s) for s in _NON_ENTITY_SUFFIXES)
    ]

    blocks = []
    for name in entity_names:
        schema = schemas[name]
        props = schema.get("properties", {})
        required_fields = set(schema.get("required", []))
        if not props:
            continue
        rows = ""
        for field, defn in props.items():
            req = "✓" if field in required_fields else ""
            desc = defn.get("description", "")
            rows += (
                f"<tr>"
                f"<td><code>{h(field)}</code></td>"
                f"<td>{h(_schema_type(defn))}</td>"
                f"<td>{h(req)}</td>"
                f"<td>{h(desc)}</td>"
                f"</tr>"
            )
        blocks.append(f"""
<h3><code>{h(name)}</code></h3>
<table>
  <thead><tr><th>Field</th><th>Type</th><th>Required</th><th>Description</th></tr></thead>
  <tbody>{rows}</tbody>
</table>
""")

    return f"""
<section id="entities" class="card">
  <h2>🗂️ Entity Schemas</h2>
  {"".join(blocks)}
</section>
"""


def build_data_contract_section(datacontract):
    name = datacontract.get("name", "Data Contract")
    version = datacontract.get("version", "")
    desc_obj = datacontract.get("description", {})
    purpose = desc_obj.get("purpose", "") if isinstance(desc_obj, dict) else str(desc_obj)
    record_count = len(datacontract.get("schema", []))

    return f"""
<section id="data-contract" class="card">
  <h2>📄 Data Contract</h2>
  <div class="summary-header">
    <span class="domain-title">{h(name)}</span>
    <span class="domain-version badge">v{h(version)}</span>
  </div>
  <p>{h(purpose.strip())}</p>
  <p>
    The full data contract ({record_count} record{'s' if record_count != 1 else ''})
    is rendered as a standalone interactive reference at
    <a href="datacontract-reference.html"><code>datacontract-reference.html</code></a>
    — generated via <code>datacontract export html</code>.
  </p>
</section>
"""


def build_erd_section(openapi):
    """Generate a Mermaid ER diagram from OpenAPI component schemas."""
    schemas = openapi.get("components", {}).get("schemas", {})

    entity_names = {
        name for name in schemas
        if not any(name.endswith(s) for s in _NON_ENTITY_SUFFIXES)
    }

    lines = ["erDiagram"]
    for name in sorted(entity_names):
        schema = schemas[name]
        props = schema.get("properties", {})
        if not props:
            continue
        lines.append(f"    {name} {{")
        for field, defn in props.items():
            ftype = defn.get("format", defn.get("type", "string"))
            ftype = ftype.replace("-", "_")  # mermaid-safe
            lines.append(f"        {ftype} {field}")
        lines.append("    }")

    # Infer relationships: if a field ends with "Id" and the referenced entity exists
    for name in sorted(entity_names):
        schema = schemas[name]
        props = schema.get("properties", {})
        for field, defn in props.items():
            if field.endswith("Id") and field != "id":
                # Try to find a matching entity whose name appears in the field name
                # e.g. contributorId → look for an entity whose name is in "contributorid"
                for candidate in entity_names:
                    if candidate.lower() in field.lower() or field.lower().startswith(candidate.lower()):
                        lines.append(f"    {candidate} ||--o{{ {name} : \"owns\"")
                        break

    diagram = "\n".join(lines)
    return f"""
<section id="erd" class="card">
  <h2>🏗️ Entity Relationship Diagram</h2>
  <div class="mermaid">
{diagram}
  </div>
</section>
"""


# ---------------------------------------------------------------------------
# Full page assembly
# ---------------------------------------------------------------------------

def build_page(openapi, asyncapi, datacontract):
    title = openapi.get("info", {}).get("title", "Domain")
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    summary = build_summary_section(openapi)
    roles = build_roles_section(openapi)
    operations = build_operations_section(openapi)
    events = build_events_section(asyncapi)
    correlation = build_event_operation_correlation(openapi, asyncapi)
    entities = build_entities_section(openapi)
    contract = build_data_contract_section(datacontract)
    erd = build_erd_section(openapi)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{h(title)} — Domain Overview</title>
  <style>
    :root {{
      --bg:       #0d1117;
      --surface:  #161b22;
      --border:   #30363d;
      --text:     #c9d1d9;
      --muted:    #8b949e;
      --accent:   #58a6ff;
      --heading:  #e6edf3;
    }}

    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
      font-size: 14px;
      line-height: 1.6;
      padding-bottom: 3rem;
    }}

    /* ── Top navigation bar ── */
    #docs-nav {{
      position: sticky;
      top: 0;
      z-index: 9999;
      background: var(--bg);
      border-bottom: 1px solid var(--border);
      padding: 8px 20px;
      display: flex;
      align-items: center;
      gap: 16px;
      font-size: 13px;
    }}
    #docs-nav a {{
      color: var(--accent);
      text-decoration: none;
    }}
    #docs-nav a:hover {{ text-decoration: underline; }}
    #docs-nav .sep {{ color: var(--border); }}

    /* ── Page header ── */
    #page-header {{
      background: linear-gradient(135deg, #161b22 0%, #0d1117 100%);
      border-bottom: 1px solid var(--border);
      padding: 2.5rem 2rem 2rem;
      text-align: center;
    }}
    #page-header h1 {{
      font-size: 2rem;
      color: var(--heading);
      margin-bottom: 0.4rem;
    }}
    #page-header .subtitle {{
      color: var(--muted);
      font-size: 0.85rem;
    }}

    /* ── TOC / Jump nav ── */
    #toc {{
      max-width: 960px;
      margin: 1.5rem auto 0;
      padding: 0 1rem;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    #toc a {{
      color: var(--accent);
      text-decoration: none;
      font-size: 13px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 4px 10px;
    }}
    #toc a:hover {{ border-color: var(--accent); }}

    /* ── Content layout ── */
    #content {{
      max-width: 960px;
      margin: 0 auto;
      padding: 1.5rem 1rem;
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }}

    /* ── Cards ── */
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1.5rem;
    }}
    .card h2 {{
      font-size: 1.1rem;
      color: var(--heading);
      margin-bottom: 1rem;
      padding-bottom: 0.5rem;
      border-bottom: 1px solid var(--border);
    }}
    .card h3 {{
      font-size: 0.95rem;
      color: var(--heading);
      margin: 1rem 0 0.5rem;
    }}
    .card p, .card li {{
      color: var(--text);
      margin-bottom: 0.4rem;
    }}
    .card ul {{ padding-left: 1.25rem; }}
    .description p {{ margin-bottom: 0.5rem; }}

    /* ── Tables ── */
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
      margin: 0.5rem 0 1rem;
    }}
    th {{
      background: #1c2128;
      color: var(--heading);
      text-align: left;
      padding: 7px 10px;
      border: 1px solid var(--border);
      font-weight: 600;
    }}
    td {{
      padding: 6px 10px;
      border: 1px solid var(--border);
      vertical-align: top;
    }}
    tr:nth-child(even) td {{ background: #1a1f2a; }}

    /* ── Badges ── */
    .badge {{
      display: inline-block;
      border-radius: 4px;
      padding: 2px 7px;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.04em;
    }}
    .method-badge {{ min-width: 52px; text-align: center; }}
    .auth-required {{ background: #1f3a24; color: #56d364; border: 1px solid #238636; }}
    .auth-public   {{ background: #1c2c42; color: #58a6ff; border: 1px solid #388bfd; }}
    .tag-badge     {{ background: #21262d; color: var(--muted); border: 1px solid var(--border); }}
    .domain-version {{ background: #21262d; color: var(--muted); border: 1px solid var(--border); font-size: 12px; }}

    /* ── Summary header ── */
    .summary-header {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 0.75rem;
    }}
    .domain-title {{
      font-size: 1rem;
      font-weight: 700;
      color: var(--heading);
    }}
    .contact {{ color: var(--muted); font-size: 12px; margin-top: 0.5rem; }}

    /* ── Code ── */
    code {{
      background: #1c2128;
      padding: 1px 5px;
      border-radius: 3px;
      font-size: 12px;
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
      color: #e6edf3;
    }}

    /* ── Notes ── */
    .note {{
      color: var(--muted);
      font-size: 12px;
      margin-top: 0.5rem;
    }}
    .note a {{ color: var(--accent); }}

    /* ── Mermaid ── */
    .mermaid {{ text-align: center; padding: 1rem 0; }}

    /* ── Footer ── */
    #footer {{
      text-align: center;
      color: var(--muted);
      font-size: 11px;
      margin-top: 2rem;
    }}
  </style>
</head>
<body>

<nav id="docs-nav">
  <a href="./index.html">&larr; Back to Docs</a>
  <span class="sep">|</span>
  <a href="./api-reference.html">API Reference</a>
  <span class="sep">|</span>
  <a href="./asyncapi-reference.html">AsyncAPI Events</a>
  <span class="sep">|</span>
  <a href="./contracts/openapi.yaml">openapi.yaml</a>
  <span class="sep">|</span>
  <a href="./contracts/asyncapi.yaml">asyncapi.yaml</a>
  <span class="sep">|</span>
  <a href="./contracts/datacontract.yaml">datacontract.yaml</a>
</nav>

<header id="page-header">
  <h1>{h(title)} — Domain Overview</h1>
  <p class="subtitle">Deterministically generated from OpenAPI, AsyncAPI &amp; Data Contract · {generated_at}</p>
</header>

<nav id="toc">
  <a href="#summary">📋 Summary</a>
  <a href="#roles">👤 Roles</a>
  <a href="#operations">🔌 Operations</a>
  <a href="#events">📡 Events</a>
  <a href="#event-correlation">🔗 Correlation</a>
  <a href="#entities">🗂️ Entities</a>
  <a href="#erd">🏗️ ERD</a>
  <a href="#data-contract">📄 Data Contract</a>
</nav>

<main id="content">
  {summary}
  {roles}
  {operations}
  {events}
  {correlation}
  {entities}
  {erd}
  {contract}
</main>

<footer id="footer">
  <p>Generated by <code>scripts/generate_domain_overview.py</code> · {generated_at}</p>
</footer>

<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
  mermaid.initialize({{ startOnLoad: true, theme: "dark" }});
</script>

</body>
</html>
"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    openapi_path = os.path.join(CONTRACTS_DIR, "openapi.yaml")
    asyncapi_path = os.path.join(CONTRACTS_DIR, "asyncapi.yaml")
    datacontract_path = os.path.join(CONTRACTS_DIR, "datacontract.yaml")

    missing = [p for p in [openapi_path, asyncapi_path, datacontract_path] if not os.path.exists(p)]
    if missing:
        print("ERROR: Missing contract files:", missing, file=sys.stderr)
        sys.exit(1)

    print("Reading contracts…")
    openapi = load_yaml(openapi_path)
    asyncapi = load_yaml(asyncapi_path)
    datacontract = load_yaml(datacontract_path)

    print("Generating domain overview…")
    html = build_page(openapi, asyncapi, datacontract)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"Written → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
