"""Generate a contracts/asyncapi.yaml skeleton from upstream specs.

Reads:
- `docs/specifications/domain-model.md` —
  `## Domain Events` table for channels + messages,
  `## Entities` for payload `data` properties (every published
  attribute, skipping `[secret]`),
  `## Aggregates` for aggregate-root child collections,
  `## Enumerations` for named enums referenced by payload fields.

Emits:
- AsyncAPI 2.6.0 with CloudEvents 1.0 envelope (`CloudEventsBase`
  declared once and `allOf`-extended per event).
- One channel per event row + one message + one
  `<Event>Envelope` schema carrying the full state of the
  affected entity.
- Aggregate-root events carry their child collections via array
  fields with `$ref`s to `<Child>Payload` schemas (per
  SUITE-DESIGN §4.5 and the suite v1.0.8 convention).
- Removal events (`removed` / `deleted` / `expired`) get a
  minimal payload (`id` + `removedAt`) per the SUITE removal
  exemption.

Usage:

    python scripts/asyncapi_skeleton.py            # writes asyncapi.yaml
    python scripts/asyncapi_skeleton.py --stdout   # prints to stdout

Refuses to overwrite an existing non-template asyncapi.yaml
(size > 200 bytes and no `[Domain]` placeholder). Use --force.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

REMOVAL_ACTIONS = {"removed", "deleted", "expired"}


def _section(text: str, heading_pattern: str) -> str:
    start = re.search(heading_pattern, text, re.MULTILINE)
    if start is None:
        return ""
    after = text[start.end() :]
    nxt = re.search(r"(?m)^##\s+\S", after)
    return after[: nxt.start()] if nxt else after


# ── parsers ─────────────────────────────────────────────────────────


def parse_events(text: str) -> list[dict]:
    """Parse `## Domain Events` → [{event, trigger, channel}, ...]."""
    section = _section(text, r"^##\s+Domain Events\s*$")
    if not section:
        return []
    out: list[dict] = []
    for row in re.finditer(
        r"^\|\s*`?(?P<event>\w+)`?\s*\|\s*(?P<trigger>[^|]+?)\s*\|\s*`?(?P<channel>[\w.-]+)`?\s*\|",
        section,
        re.MULTILINE,
    ):
        event = row.group("event").strip()
        if event.lower() in {"event", "---"}:
            continue
        out.append(
            {
                "event": event,
                "trigger": row.group("trigger").strip(),
                "channel": row.group("channel").strip(),
            }
        )
    return out


def parse_entities(text: str) -> list[tuple[str, list[dict]]]:
    """Return [(entity_name, [{name, type, required, description, secret}, ...])]."""
    section = _section(text, r"^##\s+Entities\s*$")
    if not section:
        return []
    out: list[tuple[str, list[dict]]] = []
    blocks = re.split(r"(?m)(?=^###\s+\S)", section)
    for block in blocks:
        heading = re.match(r"###\s+(?P<name>\S[^\n]*)", block)
        if heading is None:
            continue
        name = re.split(r"\s*—\s*", heading.group("name").strip(), maxsplit=1)[0].strip()
        attrs: list[dict] = []
        for row in re.finditer(
            r"^\|\s*`(?P<n>[^`]+)`\s*\|\s*(?P<t>[^|]+?)\s*\|\s*(?P<r>[^|]+?)\s*\|\s*(?P<d>[^|\n]*)\s*\|",
            block,
            re.MULTILINE,
        ):
            desc = row.group("d").strip()
            attrs.append(
                {
                    "name": row.group("n"),
                    "type": row.group("t").strip(),
                    "required": row.group("r").strip().lower().startswith("y"),
                    "description": desc,
                    "secret": "[secret]" in desc,
                }
            )
        if attrs:
            out.append((name, attrs))
    return out


def parse_aggregates(text: str) -> dict[str, list[dict]]:
    """Parse `## Aggregates` → {root: [{child, collection}, ...]}."""
    section = _section(text, r"^##\s+Aggregates\s*$")
    if not section:
        return {}
    out: dict[str, list[dict]] = {}
    for row in re.finditer(
        r"^\|\s*`(?P<root>[^`]+)`\s*\|\s*`(?P<child>[^`]+)`\s*\|\s*`(?P<collection>[^`]+)`\s*\|",
        section,
        re.MULTILINE,
    ):
        root = row.group("root").strip()
        out.setdefault(root, []).append(
            {"child": row.group("child").strip(), "collection": row.group("collection").strip()}
        )
    return out


def parse_enumerations(text: str) -> dict[str, list[str]]:
    section = _section(text, r"^##\s+Enumerations\s*$")
    if not section:
        return {}
    out: dict[str, list[str]] = {}
    for block in re.split(r"(?m)(?=^###\s+\S)", section):
        heading = re.match(r"###\s+(?P<name>\S[^\n]*)", block)
        if heading is None:
            continue
        name = heading.group("name").strip()
        values = [m.group(1) for m in re.finditer(r"^\|\s*`([^`]+)`\s*\|", block, re.MULTILINE)]
        if values:
            out[name] = values
    return out


# ── helpers ─────────────────────────────────────────────────────────


def model_type_to_jsonschema(type_hint: str) -> str:
    """Inline-flow JSON Schema snippet from a model type cell."""
    t = type_hint.strip()
    low = t.lower()
    enum_match = re.match(r"enum:(?P<n>\S+)", t)
    if enum_match:
        return f"{{ $ref: '#/components/schemas/{enum_match.group('n')}' }}"
    if "uuid" in low:
        return "{ type: string, format: uuid }"
    if "iso 8601" in low or "iso8601" in low or "date-time" in low:
        if "(date)" in low or low.endswith("(date)") or "date)" in low:
            return "{ type: string, format: date }"
        return "{ type: string, format: date-time }"
    if low.startswith("date"):
        return "{ type: string, format: date }"
    if low.startswith("integer") or low.startswith("int"):
        return "{ type: integer }"
    if low.startswith("number") or low.startswith("float") or low.startswith("decimal"):
        return "{ type: number }"
    if low.startswith("bool"):
        return "{ type: boolean }"
    if "| null" in t or "nullable" in low:
        return "{ type: string, nullable: true }"
    return "{ type: string }"


def entity_id_field(entity: str) -> str:
    """Convention: model `id` becomes `<entity>Id` in event payloads
    (per the dog-walking suite convention). E.g. Dog → dogId."""
    return entity[0].lower() + entity[1:] + "Id"


def resolve_entity(channel: str, entity_names: set[str]) -> str | None:
    """Channel `<domain>.<entity-slug>.<action>` → entity name (case-
    insensitive match against the known entities)."""
    parts = channel.split(".")
    if len(parts) < 3:
        return None
    slug = parts[1].lower()
    for name in entity_names:
        if name.lower() == slug:
            return name
    return None


def channel_action(channel: str) -> str:
    parts = channel.split(".")
    return parts[-1].lower() if parts else ""


# ── renderer ────────────────────────────────────────────────────────


def render_asyncapi(
    domain_name: str,
    events: list[dict],
    entities: list[tuple[str, list[dict]]],
    aggregates: dict[str, list[dict]],
    enums: dict[str, list[str]],
) -> str:
    entity_attrs = {name: attrs for name, attrs in entities}
    entity_names = set(entity_attrs.keys())

    lines: list[str] = []
    lines.append("asyncapi: 2.6.0")
    lines.append("info:")
    lines.append(f"  title: {domain_name} Domain Events")
    lines.append("  version: 1.0.0")
    lines.append("  description: |")
    lines.append(f"    Domain event contract for the **{domain_name}** domain.")
    lines.append("")
    lines.append("    Per SUITE-DESIGN §4.5, every event payload carries the")
    lines.append("    **full domain state** of its affected entity at the moment")
    lines.append("    of the event (minus [secret]-marked fields). The data")
    lines.append("    contract records that state.")
    lines.append("  contact:")
    lines.append(f"    name: {domain_name} Domain Spec Set")
    lines.append("    url: https://example.com")
    lines.append("    email: noreply@example.com")
    lines.append("  license:")
    lines.append("    name: MIT")
    lines.append("    url: https://opensource.org/licenses/MIT")
    lines.append("")
    lines.append("servers:")
    lines.append("  development:")
    lines.append("    url: amqp://localhost:5672")
    lines.append("    protocol: amqp")
    lines.append("    description: Local AMQP broker (development binding)")
    lines.append("")
    lines.append("defaultContentType: application/json")
    lines.append("")

    # ── channels ──
    lines.append("channels:")
    for ev in events:
        lines.append(f"  {ev['channel']}:")
        lines.append(f"    description: {ev['event']} — TODO describe trigger.")
        lines.append("    publish:")
        lines.append(f"      operationId: on{ev['event']}")
        lines.append(f"      summary: {ev['event']}")
        lines.append(f"      description: TODO — describe {ev['event']}.")
        lines.append(f"      message: {{ $ref: '#/components/messages/{ev['event']}' }}")

    # ── components ──
    lines.append("")
    lines.append("components:")
    lines.append("  messages:")
    for ev in events:
        lines.append(f"    {ev['event']}:")
        lines.append(f"      name: {ev['event']}")
        lines.append(f"      title: {ev['event']}")
        lines.append("      contentType: application/json")
        lines.append(f"      payload: {{ $ref: '#/components/schemas/{ev['event']}Envelope' }}")

    lines.append("")
    lines.append("  schemas:")
    # CloudEvents base envelope
    lines.append("    CloudEventsBase:")
    lines.append("      type: object")
    lines.append("      required: [specversion, type, source, id, time, datacontenttype]")
    lines.append("      properties:")
    lines.append("        specversion: { type: string, const: '1.0' }")
    lines.append("        type: { type: string }")
    lines.append("        source: { type: string, format: uri-reference }")
    lines.append("        id: { type: string, format: uuid }")
    lines.append("        time: { type: string, format: date-time }")
    lines.append("        datacontenttype: { type: string, const: application/json }")

    # Named enums
    for enum_name, values in enums.items():
        lines.append(f"    {enum_name}:")
        lines.append("      type: string")
        lines.append(f"      enum: [{', '.join(values)}]")

    # Aggregate child payload schemas (so each can be $ref'd).
    emitted_child_payloads: set[str] = set()
    for root, children in aggregates.items():
        for child_info in children:
            child = child_info["child"]
            if child in emitted_child_payloads:
                continue
            emitted_child_payloads.add(child)
            child_attrs = entity_attrs.get(child, [])
            published = [a for a in child_attrs if not a["secret"]]
            required_names = [
                ("id" if a["name"] == "id" else a["name"]) for a in published if a["required"]
            ]
            lines.append(f"    {child}Payload:")
            lines.append("      type: object")
            if required_names:
                lines.append(f"      required: [{', '.join(required_names)}]")
            lines.append("      properties:")
            for attr in published:
                schema = model_type_to_jsonschema(attr["type"])
                lines.append(f"        {attr['name']}: {schema}")

    # Event envelopes
    for ev in events:
        envelope = f"{ev['event']}Envelope"
        entity = resolve_entity(ev["channel"], entity_names)
        action = channel_action(ev["channel"])
        is_removal = action in REMOVAL_ACTIONS

        lines.append(f"    {envelope}:")
        if is_removal:
            lines.append(
                "      description: Removal event — minimal payload (id + timestamp) per SUITE-DESIGN §4.5 exemption."
            )
        elif entity is None:
            lines.append(
                "      description: TODO — channel does not resolve to an entity; agent must define payload."
            )
        else:
            lines.append(
                f"      description: Carries the full state of the affected {entity} at the moment of the event."
            )

        lines.append("      allOf:")
        lines.append("        - $ref: '#/components/schemas/CloudEventsBase'")
        lines.append("        - type: object")
        lines.append("          required: [data]")
        lines.append("          properties:")
        lines.append("            data:")
        lines.append("              type: object")

        if is_removal and entity is not None:
            id_field = entity_id_field(entity)
            lines.append(f"              required: [{id_field}, removedAt]")
            lines.append("              properties:")
            lines.append(f"                {id_field}: {{ type: string, format: uuid }}")
            lines.append("                removedAt: { type: string, format: date-time }")
        elif entity is not None:
            attrs = entity_attrs.get(entity, [])
            published = [a for a in attrs if not a["secret"]]
            required_names = []
            for a in published:
                if not a["required"]:
                    continue
                if a["name"] == "id":
                    required_names.append(entity_id_field(entity))
                else:
                    required_names.append(a["name"])
            agg_children = aggregates.get(entity, [])
            for child_info in agg_children:
                required_names.append(child_info["collection"])
            if required_names:
                lines.append(f"              required: [{', '.join(required_names)}]")
            lines.append("              properties:")
            for a in published:
                if a["name"] == "id":
                    lines.append(
                        f"                {entity_id_field(entity)}: {{ type: string, format: uuid }}"
                    )
                else:
                    schema = model_type_to_jsonschema(a["type"])
                    lines.append(f"                {a['name']}: {schema}")
            # Aggregate children
            for child_info in agg_children:
                collection = child_info["collection"]
                child = child_info["child"]
                lines.append(f"                {collection}:")
                lines.append("                  type: array")
                lines.append(
                    f"                  items: {{ $ref: '#/components/schemas/{child}Payload' }}"
                )
        else:
            lines.append(
                "              # TODO — fill payload (channel did not resolve to a known entity)"
            )

    return "\n".join(lines).rstrip() + "\n"


# ── main ────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a contracts/asyncapi.yaml skeleton from upstream specs."
    )
    parser.add_argument(
        "--domain-model",
        default="docs/specifications/domain-model.md",
    )
    parser.add_argument(
        "--asyncapi",
        default="docs/specifications/contracts/asyncapi.yaml",
    )
    parser.add_argument("--domain-name", default=None)
    parser.add_argument("--stdout", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    dm_path = pathlib.Path(args.domain_model).resolve()
    if not dm_path.is_file():
        print(f"asyncapi_skeleton: {dm_path} not found", file=sys.stderr)
        return 1
    dm_text = dm_path.read_text(encoding="utf-8")

    domain_name = args.domain_name
    if domain_name is None:
        m = re.match(r"#\s+Domain Model\s*[—-]\s*(?P<name>.+)", dm_text)
        domain_name = m.group("name").strip() if m else "[Domain]"

    events = parse_events(dm_text)
    if not events:
        print(
            f"asyncapi_skeleton: no events found under `## Domain Events` in {dm_path}",
            file=sys.stderr,
        )
        return 1
    entities = parse_entities(dm_text)
    aggregates = parse_aggregates(dm_text)
    enums = parse_enumerations(dm_text)

    rendered = render_asyncapi(domain_name, events, entities, aggregates, enums)

    if args.stdout:
        sys.stdout.write(rendered)
        return 0

    out_path = pathlib.Path(args.asyncapi).resolve()
    if out_path.is_file() and not args.force:
        existing = out_path.read_text(encoding="utf-8")
        looks_template = (
            len(existing) < 200 or "[Domain]" in existing or "TODO — describe" in existing
        )
        if not looks_template:
            print(
                f"asyncapi_skeleton: {out_path} already exists and doesn't "
                "look like a template. Pass --force to overwrite.",
                file=sys.stderr,
            )
            return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")
    print(
        f"Wrote asyncapi skeleton to {out_path}: "
        f"{len(events)} events, {len(entities)} entities, "
        f"{len(aggregates)} aggregate roots, {len(enums)} enums."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
