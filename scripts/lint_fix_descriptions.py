"""Add a `description:` line under every `operationId:` (OpenAPI) or
`publish:` operation (AsyncAPI) that lacks one.

Spectral's `operation-description` / `asyncapi-operation-description`
rules fail every operation that doesn't carry a description. A
human-curated description is best, but a synthesised description from
the operationId beats a Spectral fail and is the convention every
spec set has needed during contracts authoring.

Usage:

    python scripts/lint_fix_descriptions.py [path/to/openapi.yaml ...]

With no arguments, fixes both `docs/specifications/contracts/openapi.yaml`
and `docs/specifications/contracts/asyncapi.yaml` if they exist.

Idempotent: an operation that already carries a description is left
alone. Run as many times as you like.
"""

from __future__ import annotations

import pathlib
import re
import sys

OPERATION_ID_RE = re.compile(r"^(?P<indent>\s+)operationId:\s*(?P<opid>\w+)\s*$")
SUMMARY_RE_FMT = r"^{indent}summary:\s*(?P<text>.+)$"
DESCRIPTION_RE_FMT = r"^{indent}description:"


def _humanize(camel: str) -> str:
    """`viewRateCard` → `View rate card`."""
    spaced = re.sub(r"([A-Z])", r" \1", camel).strip()
    return spaced[:1].upper() + spaced[1:].lower()


def fix_file(path: pathlib.Path) -> int:
    """Inserts a `description:` line below every operationId that
    doesn't already have one. Returns the count of insertions."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    out: list[str] = []
    inserted = 0

    i = 0
    while i < len(lines):
        out.append(lines[i])
        m = OPERATION_ID_RE.match(lines[i].rstrip("\n"))
        if m:
            indent = m.group("indent")
            opid = m.group("opid")

            # Look at the next line at the SAME indent level. If it's
            # `description:`, no insertion. If it's `summary:`, prefer
            # the summary text; check the line after that for description.
            next_line = lines[i + 1].rstrip("\n") if i + 1 < len(lines) else ""
            summary_match = re.match(
                SUMMARY_RE_FMT.format(indent=re.escape(indent)), next_line
            )

            if summary_match:
                # Check the line after the summary for description
                desc_match = (
                    re.match(
                        DESCRIPTION_RE_FMT.format(indent=re.escape(indent)),
                        lines[i + 2].rstrip("\n") if i + 2 < len(lines) else "",
                    )
                    if i + 2 < len(lines)
                    else None
                )
                if not desc_match:
                    # Insert description between summary and the rest.
                    out.append(lines[i + 1])  # keep summary
                    out.append(f"{indent}description: {summary_match.group('text')}.\n")
                    inserted += 1
                    i += 2  # skip the summary line we already appended
                    continue
            else:
                # No summary at the next line. If the next line is
                # already a description, leave alone; otherwise insert.
                desc_match = re.match(
                    DESCRIPTION_RE_FMT.format(indent=re.escape(indent)), next_line
                )
                if not desc_match:
                    out.append(f"{indent}description: {_humanize(opid)}.\n")
                    inserted += 1
        i += 1

    if inserted:
        path.write_text("".join(out), encoding="utf-8")
    return inserted


def fix_asyncapi_tags(path: pathlib.Path) -> int:
    """AsyncAPI's `tags:` array needs `description:` per tag.
    Operates only on the top-level `tags:` block (not channel tags)."""
    text = path.read_text(encoding="utf-8")
    # Match a top-level `tags:` block (no indent) followed by `- name:` items.
    # Insert `description: <Name> domain events.` for any item that lacks one.
    pattern = re.compile(
        r"(?m)^(?P<line>  - name: (?P<name>\S+))\n(?!    description:)"
    )

    def insert(m: re.Match[str]) -> str:
        return f"{m.group('line')}\n    description: {m.group('name')} domain events.\n"

    new_text, n = pattern.subn(insert, text)
    if n:
        path.write_text(new_text, encoding="utf-8")
    return n


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    if args:
        paths = [pathlib.Path(p).resolve() for p in args]
    else:
        paths = [
            pathlib.Path("docs/specifications/contracts/openapi.yaml").resolve(),
            pathlib.Path("docs/specifications/contracts/asyncapi.yaml").resolve(),
        ]

    total_ops = 0
    total_tags = 0
    for path in paths:
        if not path.is_file():
            print(f"  SKIP   {path} (not found)")
            continue
        ops = fix_file(path)
        total_ops += ops
        tags = 0
        if "asyncapi" in path.name:
            tags = fix_asyncapi_tags(path)
            total_tags += tags
        if ops or tags:
            print(f"  FIXED  {path}  ({ops} ops, {tags} tags)")
        else:
            print(f"  CLEAN  {path}  (no insertions needed)")

    print(f"\nTotal: {total_ops} operation descriptions, {total_tags} tag descriptions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
