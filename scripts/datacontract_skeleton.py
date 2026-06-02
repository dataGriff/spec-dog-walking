"""Generate a contracts/datacontract.yaml skeleton from asyncapi.yaml.

The datacontract is essentially a one-to-one mirror of the
asyncapi event payloads — every event needs a corresponding
ODCS record, and the record's fields mirror the payload's
properties.

Reads:
- `docs/specifications/contracts/asyncapi.yaml` — every message
  and its payload schema.
- `docs/specifications/nfr.md` (optional) — best-effort lookup
  of `NFR-AVAIL-002` and `NFR-DATA-001` for slaProperties.

Emits:
- ODCS 3.1 (Open Data Contract Standard) document with:
  - `id`, `name`, `version`, `domain`, `dataProduct`,
    `description.purpose`/`usage`/`limitations`.
  - `team` placeholder.
  - `servers` placeholder (AMQP development binding mirroring
    asyncapi).
  - `schema[*]` — one record per channel family (groups
    channels sharing the same entity slug; aggregate-root
    families carry the children).
  - `slaProperties` with availability + retention (from NFRs or
    placeholders).

The agent walks each record after generation to fill in
descriptions and any reduced-payload variants for removal
events.

Usage:

    python scripts/datacontract_skeleton.py            # writes datacontract.yaml
    python scripts/datacontract_skeleton.py --stdout   # prints to stdout

Refuses to overwrite an existing non-template datacontract.yaml
(size > 200 bytes and no `[Domain]` placeholder). Use --force.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

REMOVAL_ACTIONS = {"removed", "deleted", "expired"}


# ── ODCS type mapping ───────────────────────────────────────────────


def jsonschema_to_odcs(prop: dict) -> dict:
    """Map an asyncapi JSON Schema fragment to an ODCS field
    descriptor. Returns a dict of ODCS field attributes to merge."""
    if not isinstance(prop, dict):
        return {"logicalType": "string"}
    t = prop.get("type")
    fmt = prop.get("format", "")
    if t == "string":
        if fmt == "uuid":
            return {"logicalType": "string", "physicalType": "uuid"}
        if fmt == "date-time":
            return {"logicalType": "timestamp"}
        if fmt == "date":
            return {"logicalType": "date"}
        if fmt == "email":
            return {"logicalType": "string", "physicalType": "email"}
        return {"logicalType": "string"}
    if t == "integer":
        return {"logicalType": "integer"}
    if t == "number":
        return {"logicalType": "number"}
    if t == "boolean":
        return {"logicalType": "boolean"}
    if t == "array":
        return {"logicalType": "array"}
    # $ref to an enum/schema
    if "$ref" in prop:
        return {"logicalType": "string"}
    return {"logicalType": "string"}


# ── asyncapi traversal ──────────────────────────────────────────────


def _resolve_ref(node: dict, schemas: dict) -> dict:
    if not isinstance(node, dict):
        return node
    ref = node.get("$ref")
    if not isinstance(ref, str):
        return node
    name = ref.rsplit("/", 1)[-1]
    return schemas.get(name, node)


def _find_data_property(envelope: dict, schemas: dict) -> dict | None:
    for branch in envelope.get("allOf", []) or []:
        resolved = _resolve_ref(branch, schemas)
        data = (resolved.get("properties") or {}).get("data")
        if data is not None:
            return _resolve_ref(data, schemas)
    data = (envelope.get("properties") or {}).get("data")
    if data is not None:
        return _resolve_ref(data, schemas)
    return None


def extract_event_payloads(asyncapi: dict) -> list[dict]:
    """Returns [{event, channel, data_properties, required, action}, ...]
    in declaration order."""
    channels = asyncapi.get("channels") or {}
    messages = (asyncapi.get("components") or {}).get("messages") or {}
    schemas = (asyncapi.get("components") or {}).get("schemas") or {}

    # Build a {message_name: channel} map by walking channels and pulling
    # the message ref from publish/subscribe operations.
    msg_to_channel: dict[str, str] = {}
    for channel_name, channel_def in channels.items():
        if not isinstance(channel_def, dict):
            continue
        for op_key in ("publish", "subscribe"):
            op = channel_def.get(op_key)
            if not isinstance(op, dict):
                continue
            msg = op.get("message") or {}
            ref = msg.get("$ref", "")
            if ref.startswith("#/components/messages/"):
                msg_to_channel[ref.rsplit("/", 1)[-1]] = channel_name

    out: list[dict] = []
    for msg_name, msg in messages.items():
        if not isinstance(msg, dict):
            continue
        payload = msg.get("payload")
        if not isinstance(payload, dict):
            continue
        envelope = _resolve_ref(payload, schemas)
        data = _find_data_property(envelope, schemas)
        if not isinstance(data, dict):
            continue
        channel = msg_to_channel.get(msg_name, "")
        action = channel.split(".")[-1].lower() if channel else ""
        props = data.get("properties") or {}
        required = data.get("required") or []
        out.append(
            {
                "event": msg_name,
                "channel": channel,
                "action": action,
                "data_properties": props,
                "required": required,
                "schemas": schemas,  # captured so nested array items can be resolved
            }
        )
    return out


# ── NFR lookup ──────────────────────────────────────────────────────


def parse_nfr_value(text: str, code: str) -> str | None:
    """Best-effort search for `<code>` followed by a value cell or
    sentence containing a number/unit."""
    if not text:
        return None
    # Look for a line containing the code and pull a percentage / number
    # / duration nearby.
    pattern = rf"{re.escape(code)}[^\n]*"
    match = re.search(pattern, text)
    if not match:
        return None
    line = match.group(0)
    # Try percentages first
    pct = re.search(r"(\d+(?:\.\d+)?)\s*%", line)
    if pct:
        return pct.group(1)
    days = re.search(r"(\d+)\s*(?:days?|d\b)", line)
    if days:
        return days.group(1)
    months = re.search(r"(\d+)\s*months?", line)
    if months:
        return months.group(1)
    return None


# ── grouping ────────────────────────────────────────────────────────


def group_events_by_entity(events: list[dict]) -> dict[str, list[dict]]:
    """Group events by entity slug (channel segment 1) so we emit one
    record per entity family. Removal events go in a separate
    `<slug>_removed` group."""
    groups: dict[str, list[dict]] = {}
    for ev in events:
        parts = ev["channel"].split(".")
        if len(parts) < 3:
            slug = ev["event"].lower()
        else:
            slug = parts[1].lower()
        if ev["action"] in REMOVAL_ACTIONS:
            slug = f"{slug}_removed"
        groups.setdefault(slug, []).append(ev)
    return groups


# ── renderer ────────────────────────────────────────────────────────


def render_field(
    name: str, prop: dict, required: bool, schemas: dict, indent: int = 6
) -> list[str]:
    """Render one ODCS field. Handles scalars and array-of-object."""
    pad = " " * indent
    lines: list[str] = []
    if prop.get("type") == "array":
        lines.append(f"{pad}- name: {name}")
        lines.append(f"{pad}  description: TODO — describe {name}.")
        lines.append(f"{pad}  logicalType: array")
        if required:
            lines.append(f"{pad}  required: true")
        items = prop.get("items") or {}
        items_resolved = _resolve_ref(items, schemas) if isinstance(items, dict) else items
        if isinstance(items_resolved, dict) and (
            items_resolved.get("type") == "object" or items_resolved.get("properties")
        ):
            lines.append(f"{pad}  items:")
            lines.append(f"{pad}    logicalType: object")
            lines.append(f"{pad}    properties:")
            sub_required = set(items_resolved.get("required") or [])
            for sub_name, sub_prop in (items_resolved.get("properties") or {}).items():
                odcs = jsonschema_to_odcs(sub_prop)
                attrs = ", ".join(f"{k}: {v}" for k, v in odcs.items())
                req_str = ", required: true" if sub_name in sub_required else ""
                lines.append(f"{pad}      - {{ name: {sub_name}, {attrs}{req_str} }}")
        return lines
    odcs = jsonschema_to_odcs(prop)
    attrs = ", ".join(f"{k}: {v}" for k, v in odcs.items())
    req_str = ", required: true" if required else ""
    lines.append(f"{pad}- {{ name: {name}, description: TODO, {attrs}{req_str} }}")
    return lines


def render_datacontract(
    domain_name: str,
    events: list[dict],
    availability: str | None,
    retention: str | None,
) -> str:
    domain_slug = domain_name.lower().replace(" ", "-")
    lines: list[str] = []
    lines.append("dataContractSpecification: 1.1.0")
    lines.append(f"id: urn:datacontract:{domain_slug}:{domain_slug}-domain-events:1.0.0")
    lines.append(f"name: {domain_name} Domain Events")
    lines.append("version: 1.0.0")
    lines.append(f"domain: {domain_slug}")
    lines.append(f"dataProduct: {domain_slug}-events")
    lines.append("description:")
    lines.append("  purpose: >")
    lines.append(f"    Historic record of every domain event emitted by the {domain_name}")
    lines.append("    domain. Per SUITE-DESIGN §4.5 every record carries the full")
    lines.append("    state of its affected entity at the moment of the event.")
    lines.append("  usage: >")
    lines.append(f"    Consume this contract to understand the schema of records emitted")
    lines.append(f"    on the `{domain_slug}.*` event channels.")
    lines.append("  limitations: >")
    lines.append("    Covers the event payload only (data envelope). CloudEvents metadata")
    lines.append("    fields are documented in `asyncapi.yaml` and not repeated here.")
    lines.append("")
    lines.append("team:")
    lines.append(f"  name: {domain_name} Domain Spec Set")
    lines.append("  members:")
    lines.append(f"    - username: {domain_slug}-domain")
    lines.append(f"      name: {domain_name} Domain Spec Set")
    lines.append("      role: owner")
    lines.append("")
    lines.append("servers:")
    lines.append("  - server: development")
    lines.append("    type: custom")
    lines.append("    description: Local AMQP broker (development binding)")
    lines.append("    environment: dev")
    lines.append("    customProperties:")
    lines.append("      - property: protocol")
    lines.append("        value: amqp")
    lines.append("      - property: url")
    lines.append("        value: amqp://localhost:5672")
    lines.append("")
    lines.append("schema:")

    groups = group_events_by_entity(events)
    for slug, group_events in groups.items():
        # All events in this group share the same payload shape (full state
        # of the same entity), so emit one record using the first event's
        # data properties.
        first = group_events[0]
        props = first["data_properties"]
        required = set(first["required"])
        schemas = first["schemas"]
        lines.append(f"  - name: {slug}")
        lines.append("    description: >")
        events_str = ", ".join(ev["event"] for ev in group_events)
        lines.append(f"      Records published via {events_str} channels.")
        lines.append("    physicalType: topic")
        lines.append("    properties:")
        for prop_name, prop in props.items():
            lines.extend(render_field(prop_name, prop, prop_name in required, schemas, indent=6))
        lines.append("")

    lines.append("slaProperties:")
    lines.append("  - property: availability")
    lines.append(f'    value: "{availability if availability else "TODO"}"')
    lines.append('    unit: "%"')
    lines.append("    description: TODO — link to NFR-AVAIL-002.")
    lines.append("  - property: retention")
    lines.append(f"    value: {retention if retention else 'TODO'}")
    lines.append("    unit: d")
    lines.append("    description: TODO — link to NFR-DATA-001.")

    return "\n".join(lines).rstrip() + "\n"


# ── main ────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a contracts/datacontract.yaml skeleton from asyncapi.yaml + nfr.md."
    )
    parser.add_argument(
        "--asyncapi",
        default="docs/specifications/contracts/asyncapi.yaml",
    )
    parser.add_argument(
        "--nfr",
        default="docs/specifications/nfr.md",
    )
    parser.add_argument(
        "--datacontract",
        default="docs/specifications/contracts/datacontract.yaml",
    )
    parser.add_argument(
        "--domain-model",
        default="docs/specifications/domain-model.md",
        help="Used only to derive the domain name for the info section.",
    )
    parser.add_argument("--domain-name", default=None)
    parser.add_argument("--stdout", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    try:
        import yaml as pyyaml
    except ImportError:
        print(
            "datacontract_skeleton: pyyaml is required. Install via `pip install pyyaml`.",
            file=sys.stderr,
        )
        return 1

    asyncapi_path = pathlib.Path(args.asyncapi).resolve()
    if not asyncapi_path.is_file():
        print(
            f"datacontract_skeleton: {asyncapi_path} not found. Run "
            "`task asyncapi:skeleton` first or author asyncapi.yaml.",
            file=sys.stderr,
        )
        return 1
    asyncapi = pyyaml.safe_load(asyncapi_path.read_text(encoding="utf-8"))

    nfr_path = pathlib.Path(args.nfr).resolve()
    nfr_text = nfr_path.read_text(encoding="utf-8") if nfr_path.is_file() else ""

    dm_path = pathlib.Path(args.domain_model).resolve()
    domain_name = args.domain_name
    if domain_name is None and dm_path.is_file():
        m = re.match(
            r"#\s+Domain Model\s*[—-]\s*(?P<name>.+)",
            dm_path.read_text(encoding="utf-8"),
        )
        domain_name = m.group("name").strip() if m else "[Domain]"
    elif domain_name is None:
        domain_name = "[Domain]"

    events = extract_event_payloads(asyncapi)
    if not events:
        print(
            "datacontract_skeleton: no resolvable event payloads in "
            f"{asyncapi_path}. Author asyncapi.yaml first.",
            file=sys.stderr,
        )
        return 1

    availability = parse_nfr_value(nfr_text, "NFR-AVAIL-002")
    retention = parse_nfr_value(nfr_text, "NFR-DATA-001")

    rendered = render_datacontract(domain_name, events, availability, retention)

    if args.stdout:
        sys.stdout.write(rendered)
        return 0

    out_path = pathlib.Path(args.datacontract).resolve()
    if out_path.is_file() and not args.force:
        existing = out_path.read_text(encoding="utf-8")
        looks_template = (
            len(existing) < 200 or "[Domain]" in existing or "TODO — describe" in existing
        )
        if not looks_template:
            print(
                f"datacontract_skeleton: {out_path} already exists and doesn't "
                "look like a template. Pass --force to overwrite.",
                file=sys.stderr,
            )
            return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")
    print(
        f"Wrote datacontract skeleton to {out_path}: "
        f"{len(events)} events into {len({ev['channel'].split('.')[1] if len(ev['channel'].split('.')) >= 3 else ev['event'] for ev in events})} record families."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
