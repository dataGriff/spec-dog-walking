"""Generate a glossary.md skeleton from domain-model.md.

Walks `docs/specifications/domain-model.md`, extracts every entity
and its attributes from the attribute tables, and writes a
glossary.md skeleton with:

- `### <Entity>` headings under `## Entities` with placeholder
  one-line descriptions
- `### <attribute>` headings under `## <Entity> attributes` with
  placeholder descriptions

The agent then walks each entry and fills in the real prose. Saves
the ~90-entry typing tax on any non-trivial domain.

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
ATTR_ROW_RE = re.compile(r"^\|\s*`(?P<name>[^`]+)`\s*\|", re.MULTILINE)


def parse_entities(domain_model_text: str) -> list[tuple[str, list[str]]]:
    """Return [(entity_name, [attribute_name, ...]), ...] in source order."""
    # Find the Entities section (between `## Entities` and the next `## ` heading)
    entities_start = re.search(r"(?m)^##\s+Entities\s*$", domain_model_text)
    if not entities_start:
        return []
    after = domain_model_text[entities_start.end():]
    next_section = re.search(r"(?m)^##\s+\S", after)
    section = after[: next_section.start()] if next_section else after

    out: list[tuple[str, list[str]]] = []
    for match in ENTITY_BLOCK_RE.finditer(section):
        raw_name = match.group("name").strip()
        # Strip "Entity — qualifier" style suffix
        name = re.split(r"\s*—\s*", raw_name, maxsplit=1)[0].strip()
        body = match.group("body")
        attrs = [m.group("name") for m in ATTR_ROW_RE.finditer(body)]
        # De-dupe preserving order (first occurrence wins)
        seen: set[str] = set()
        attrs = [a for a in attrs if not (a in seen or seen.add(a))]
        if name:
            out.append((name, attrs))
    return out


def render_glossary(entities: list[tuple[str, list[str]]], domain_name: str) -> str:
    lines: list[str] = []
    lines.append(f"# Glossary — {domain_name}")
    lines.append("")
    lines.append(
        f"> The ubiquitous language for the {domain_name} domain. Every entity"
    )
    lines.append(
        "> name and every attribute name used in `domain-model.md` (and the"
    )
    lines.append(
        "> later contracts files) appears here exactly as it is used. Code,"
    )
    lines.append("> docs, and conversation must use these terms.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Entities")
    lines.append("")

    for name, _ in entities:
        lines.append(f"### {name}")
        lines.append("")
        lines.append(
            f"<!-- TODO: one or two sentence description of what a {name} is "
            "in this domain. -->"
        )
        lines.append("")

    lines.append("---")
    lines.append("")

    for name, attrs in entities:
        if not attrs:
            continue
        lines.append(f"## {name} attributes")
        lines.append("")
        for attr in attrs:
            lines.append(f"### {attr}")
            lines.append("")
            lines.append(
                "<!-- TODO: type, constraints, business meaning that a "
                "reader couldn't guess from the name alone. -->"
            )
            lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a glossary.md skeleton from domain-model.md."
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

    # Derive domain name if not supplied
    domain_name = args.domain_name
    if domain_name is None:
        m = re.match(r"#\s+Domain Model\s*[—-]\s*(?P<name>.+)", text)
        domain_name = m.group("name").strip() if m else "[Domain]"

    entities = parse_entities(text)
    if not entities:
        print(
            "glossary_skeleton: no entities found under `## Entities` in "
            f"{dm_path}",
            file=sys.stderr,
        )
        return 1

    rendered = render_glossary(entities, domain_name)

    if args.stdout:
        sys.stdout.write(rendered)
        return 0

    glossary_path = pathlib.Path(args.glossary).resolve()
    if glossary_path.is_file() and not args.force:
        existing = glossary_path.read_text(encoding="utf-8")
        looks_template = (
            len(existing) < 200
            or "[Domain]" in existing
            or "[Resource1]" in existing
        )
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
    n_attrs = sum(len(a) for _, a in entities)
    print(
        f"Wrote glossary skeleton to {glossary_path}: "
        f"{len(entities)} entities, {n_attrs} attributes."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
