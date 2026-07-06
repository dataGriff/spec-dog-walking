"""Generate a glossary.md lexicon skeleton from domain-model.md.

The glossary is a lexicon (gate 1.4): one- or two-sentence entries
for the domain's vocabulary — entities, roles, domain events,
enumerations, other terms. Attribute detail lives in domain-model.md's
entity tables and is deliberately NOT repeated here.

Walks `docs/specifications/domain-model.md` and writes a glossary.md
skeleton with:

- `### <Entity>` stubs under `## Entities`
- `### <Event>` stubs under `## Domain events` (from the
  `## Domain Events` table, if present)
- `### <Enum>` stubs under `## Enumerations` (from the model's
  `## Enumerations` section, if present)
- empty `## Roles` and `## Other terms` sections for the agent to
  fill by hand (roles come from the auth matrix / PRD, not the model)

Usage:

    python scripts/glossary_skeleton.py            # writes to docs/specifications/glossary.md
    python scripts/glossary_skeleton.py --stdout   # prints to stdout instead

Refuses to overwrite an existing non-template glossary.md (size > 200
bytes and no `[Domain]` placeholder present). Use --force to override.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

ENTITY_BLOCK_RE = re.compile(
    r"(?m)^###\s+(?P<name>\S[^\n]*)\n(?P<body>.*?)(?=^###\s+|\Z)", re.DOTALL
)
EVENT_ROW_RE = re.compile(
    r"^\|\s*`?(?P<event>[\w]+)`?\s*\|\s*(?P<trigger>[^|]+?)\s*\|\s*`?(?P<channel>[\w.-]+)`?\s*\|",
    re.MULTILINE,
)


def _section(text: str, heading_pattern: str) -> str:
    start = re.search(heading_pattern, text, re.MULTILINE)
    if not start:
        return ""
    after = text[start.end() :]
    next_section = re.search(r"(?m)^##\s+\S", after)
    return after[: next_section.start()] if next_section else after


def parse_entities(domain_model_text: str) -> list[str]:
    """Return entity names in source order."""
    section = _section(domain_model_text, r"(?m)^##\s+Entities\s*$")
    out: list[str] = []
    for match in ENTITY_BLOCK_RE.finditer(section):
        raw_name = match.group("name").strip()
        name = re.split(r"\s*—\s*", raw_name, maxsplit=1)[0].strip()
        if name:
            out.append(name)
    return out


def parse_events(domain_model_text: str) -> list[tuple[str, str]]:
    """Return [(event_name, channel), ...] from the Domain Events table."""
    section = _section(domain_model_text, r"(?m)^##\s+Domain Events\s*$")
    out: list[tuple[str, str]] = []
    for row in EVENT_ROW_RE.finditer(section):
        event = row.group("event").strip()
        if event.lower() in {"event", "---"}:
            continue
        out.append((event, row.group("channel").strip()))
    return out


def parse_enums(domain_model_text: str) -> list[str]:
    """Return enumeration names (with any (open) marker stripped)."""
    section = _section(domain_model_text, r"(?m)^##\s+Enumerations\s*$")
    out: list[str] = []
    for match in re.finditer(r"(?m)^###\s+(\S[^\n]*)$", section):
        raw = match.group(1).strip()
        name = re.sub(r"\s*[\(\[]\s*open\s*[\)\]]\s*$", "", raw, flags=re.IGNORECASE).strip()
        if name:
            out.append(name)
    return out


def render_glossary(
    entities: list[str],
    events: list[tuple[str, str]],
    enums: list[str],
    domain_name: str,
) -> str:
    lines: list[str] = []
    lines.append(f"# Glossary — {domain_name}")
    lines.append("")
    lines.append(f"> The ubiquitous language for the {domain_name} domain — a lexicon,")
    lines.append("> not a reference manual. Every entity, role, domain event,")
    lines.append("> enumeration, and key term has a one- or two-sentence entry here.")
    lines.append("> Attribute-level detail lives in `domain-model.md`'s entity tables.")
    lines.append("> Code, docs, and conversation must use these terms.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Entities")
    lines.append("")
    for name in entities:
        lines.append(f"### {name}")
        lines.append("")
        lines.append(
            f"<!-- TODO: one or two sentence description of what a {name} is in this domain. -->"
        )
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Roles")
    lines.append("")
    lines.append(
        "<!-- TODO: one `### <role>` entry per role — what it can do and "
        "which PRD persona it maps to. -->"
    )
    lines.append("")

    if events:
        lines.append("---")
        lines.append("")
        lines.append("## Domain events")
        lines.append("")
        for event, channel in events:
            lines.append(f"### {event}")
            lines.append("")
            lines.append(
                f"<!-- TODO: published on `{channel}` when… ; what the payload carries. -->"
            )
            lines.append("")

    if enums:
        lines.append("---")
        lines.append("")
        lines.append("## Enumerations")
        lines.append("")
        for enum_name in enums:
            lines.append(f"### {enum_name}")
            lines.append("")
            lines.append(
                "<!-- TODO: what this enumeration classifies; open or closed; "
                "where the authoritative value list lives. -->"
            )
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Other terms")
    lines.append("")
    lines.append(
        "<!-- TODO: define any other term that appears in code or specs and "
        "wouldn't be obvious from name alone. -->"
    )
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a glossary.md lexicon skeleton from domain-model.md."
    )
    parser.add_argument(
        "--domain-model",
        default="docs/specifications/domain-model.md",
        help="Path to domain-model.md (default: docs/specifications/domain-model.md)",
    )
    parser.add_argument(
        "--glossary",
        default="docs/specifications/glossary.md",
        help="Path to write glossary.md (default: docs/specifications/glossary.md)",
    )
    parser.add_argument(
        "--domain-name",
        default=None,
        help="Domain name for the glossary heading. Defaults to the first word "
        "after `# Domain Model — ` in domain-model.md.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print to stdout instead of writing the glossary file.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing non-template glossary.md.",
    )
    args = parser.parse_args(argv)

    dm_path = pathlib.Path(args.domain_model).resolve()
    if not dm_path.is_file():
        print(f"glossary_skeleton: {dm_path} not found", file=sys.stderr)
        return 1

    text = dm_path.read_text(encoding="utf-8")

    domain_name = args.domain_name
    if domain_name is None:
        m = re.match(r"#\s+Domain Model\s*[—-]\s*(?P<name>.+)", text)
        domain_name = m.group("name").strip() if m else "[Domain]"

    entities = parse_entities(text)
    if not entities:
        print(
            f"glossary_skeleton: no entities found under `## Entities` in {dm_path}",
            file=sys.stderr,
        )
        return 1

    events = parse_events(text)
    enums = parse_enums(text)
    rendered = render_glossary(entities, events, enums, domain_name)

    if args.stdout:
        sys.stdout.write(rendered)
        return 0

    glossary_path = pathlib.Path(args.glossary).resolve()
    if glossary_path.is_file() and not args.force:
        existing = glossary_path.read_text(encoding="utf-8")
        looks_template = len(existing) < 200 or "[Domain]" in existing or "[Resource1]" in existing
        if not looks_template:
            print(
                f"glossary_skeleton: {glossary_path} already exists and "
                "doesn't look like a template (>200 bytes, no [Domain] "
                "placeholder). Pass --force to overwrite.",
                file=sys.stderr,
            )
            return 1

    glossary_path.parent.mkdir(parents=True, exist_ok=True)
    glossary_path.write_text(rendered, encoding="utf-8")
    print(
        f"Wrote glossary lexicon skeleton to {glossary_path}: "
        f"{len(entities)} entities, {len(events)} events, {len(enums)} enumerations."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
