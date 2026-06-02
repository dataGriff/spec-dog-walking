"""Generate a contracts/openapi.yaml skeleton from upstream specs.

Reads:
- `docs/specifications/auth-matrix.md` — the `## Auth Matrix` section
  (single-table OR `### <Resource>` subsections) for paths, methods,
  operations, and public/protected scope.
- `docs/specifications/domain-model.md` — `## Entities` for schemas,
  `## Enumerations` for named enums.
- `docs/specifications/error-catalogue.md` — for 4xx/5xx response
  references (best-effort; the agent prunes).

Emits:
- OpenAPI 3.0.3 skeleton with `info`, `servers`, global
  `security: [bearerAuth: []]`, `paths`, `components.schemas`
  (one per entity + one per enum), `components.parameters`
  (Page, PageSize, IdempotencyKey), `components.responses`
  (one per error code), `components.securitySchemes.bearerAuth`.
- Every POST op gets `parameters: [- $ref:
  '#/components/parameters/IdempotencyKey']` and a `409
  IdempotencyKeyConflict` response (per the Idempotency-Key
  convention).
- Public ops carry `security: []` to opt out of global bearer
  auth.

The agent then walks each operation and fills in `requestBody`
schemas, response shapes, and free-text descriptions. Spectral
will complain about TODO descriptions on operations — run
`task lint:fix-descriptions` to auto-stub them after this.

Usage:

    python scripts/openapi_skeleton.py            # writes openapi.yaml
    python scripts/openapi_skeleton.py --stdout   # prints to stdout

Refuses to overwrite an existing non-template openapi.yaml (size
> 200 bytes and no `[Domain]` placeholder marker). Use --force
to override.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

# ── parsers: auth matrix ─────────────────────────────────────────────

AUTH_OP_ROW_RE = re.compile(
    r"^\|\s*(?P<op>[^|]+?)\s*\|\s*`(?P<method>GET|POST|PUT|PATCH|DELETE)\s+(?P<path>[^`]+)`\s*\|\s*(?P<public>[^|]+?)\s*\|",
    re.MULTILINE,
)


def _section(text: str, heading_pattern: str) -> str:
    """Return the slice under the heading matched by `heading_pattern`,
    up to the next same-level (## ) heading."""
    start = re.search(heading_pattern, text, re.MULTILINE)
    if start is None:
        return ""
    after = text[start.end() :]
    nxt = re.search(r"(?m)^##\s+\S", after)
    return after[: nxt.start()] if nxt else after


def parse_auth_matrix(text: str) -> list[dict]:
    """Parse the `## Auth Matrix` section into a list of operations.

    Returns [{operation, method, path, public, tag}, ...] in source
    order. Handles both flat tables and `### <Tag>` subsections.
    """
    section = _section(text, r"^##\s+Auth Matrix\s*$")
    if not section:
        return []

    out: list[dict] = []
    # Split into per-tag blocks by ### headings; if there are no ###s
    # the whole section is one untagged block (tag derived per-row from path).
    blocks = re.split(r"(?m)(?=^###\s+\S)", section)
    for block in blocks:
        tag_match = re.match(r"###\s+(?P<tag>[^\n]+)", block)
        block_tag = tag_match.group("tag").strip() if tag_match else None
        for row in AUTH_OP_ROW_RE.finditer(block):
            op = row.group("op").strip()
            if op.lower() in {"operation", "---"}:
                continue
            public_cell = row.group("public").strip()
            is_public = "🌐" in public_cell
            path = row.group("path").strip()
            tag = block_tag if block_tag else _tag_from_path(path)
            out.append(
                {
                    "operation": op,
                    "method": row.group("method"),
                    "path": path,
                    "public": is_public,
                    "tag": tag,
                }
            )
    return out


def _tag_from_path(path: str) -> str:
    """Derive a tag from the first non-versioned path segment.
    `/v1/auth/login` → `Auth`; `/v1/dogs/{dogId}` → `Dogs`;
    `/v1/walk-updates/...` → `WalkUpdates`. Returns 'Default' if
    nothing usable."""
    segs = [s for s in path.split("/") if s and not s.startswith("{")]
    # Skip a leading version segment like 'v1'.
    if segs and re.match(r"^v\d+$", segs[0]):
        segs = segs[1:]
    if not segs:
        return "Default"
    raw = segs[0]
    # 'walk-updates' → 'WalkUpdates'
    return "".join(part.capitalize() for part in raw.split("-"))


# ── parsers: domain model entities + enums ──────────────────────────


def parse_entities(text: str) -> list[tuple[str, list[dict]]]:
    """Return [(entity_name, [{name, type, required, description}, ...])].

    Walks `## Entities` and its `### <Entity>` subsections, parsing
    the 4-column attribute table.
    """
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
        # Match the 4-column attribute table: | `name` | type | required | description |
        for row in re.finditer(
            r"^\|\s*`(?P<n>[^`]+)`\s*\|\s*(?P<t>[^|]+?)\s*\|\s*(?P<r>[^|]+?)\s*\|\s*(?P<d>[^|\n]*)\s*\|",
            block,
            re.MULTILINE,
        ):
            desc = row.group("d").strip()
            if "[secret]" in desc:
                # Sensitive attrs are excluded from event payloads, but they
                # still belong in the openapi entity schema (think requestBody
                # for a password change). Keep them with a comment.
                attrs.append(
                    {
                        "name": row.group("n"),
                        "type": row.group("t").strip(),
                        "required": row.group("r").strip().lower().startswith("y"),
                        "description": desc,
                        "secret": True,
                    }
                )
                continue
            attrs.append(
                {
                    "name": row.group("n"),
                    "type": row.group("t").strip(),
                    "required": row.group("r").strip().lower().startswith("y"),
                    "description": desc,
                    "secret": False,
                }
            )
        if attrs:
            out.append((name, attrs))
    return out


def parse_enumerations(text: str) -> dict[str, list[str]]:
    """Parse `## Enumerations` → {EnumName: [values]}."""
    section = _section(text, r"^##\s+Enumerations\s*$")
    if not section:
        return {}
    out: dict[str, list[str]] = {}
    blocks = re.split(r"(?m)(?=^###\s+\S)", section)
    for block in blocks:
        heading = re.match(r"###\s+(?P<name>\S[^\n]*)", block)
        if heading is None:
            continue
        name = heading.group("name").strip()
        values: list[str] = []
        for row in re.finditer(r"^\|\s*`([^`]+)`\s*\|", block, re.MULTILINE):
            values.append(row.group(1))
        if values:
            out[name] = values
    return out


# ── parsers: error catalogue ────────────────────────────────────────


def parse_error_codes(text: str) -> list[dict]:
    """Parse `### \`CODE_NAME\`` headings and the HTTP status line beneath
    each. Returns [{code, status}, ...]."""
    out: list[dict] = []
    for match in re.finditer(
        r"###\s+`(?P<code>[A-Z_]+)`\s*\n+\*\*HTTP status:\*\*\s*(?P<status>\d{3})",
        text,
    ):
        out.append({"code": match.group("code"), "status": match.group("status")})
    return out


# ── type mapping ────────────────────────────────────────────────────


def model_type_to_openapi(type_hint: str, name: str) -> str:
    """Map a domain-model type cell to an OpenAPI property schema as a
    one-line inline-flow string. Falls back to `type: string` with a
    TODO comment for anything unrecognised.

    `name` is used to spot id-like fields for format: uuid.
    """
    t = type_hint.strip()
    low = t.lower()
    # enum:<Name> reference
    enum_match = re.match(r"enum:(?P<n>\S+)", t)
    if enum_match:
        return f"{{ $ref: '#/components/schemas/{enum_match.group('n')}' }}"
    # UUID
    if "uuid" in low:
        return "{ type: string, format: uuid }"
    # ISO 8601 datetime
    if "iso 8601" in low or "iso8601" in low or "date-time" in low:
        if "date)" in low or low.endswith("date"):
            return "{ type: string, format: date }"
        return "{ type: string, format: date-time }"
    if low.startswith("date"):
        return "{ type: string, format: date }"
    # email
    if "email" in low:
        return "{ type: string, format: email }"
    # integer
    if low.startswith("integer") or low.startswith("int"):
        return "{ type: integer }"
    # number / float / decimal
    if low.startswith("number") or low.startswith("float") or low.startswith("decimal"):
        return "{ type: number }"
    # boolean
    if low.startswith("bool"):
        return "{ type: boolean }"
    # nullable string
    if "| null" in t or "nullable" in low:
        return "{ type: string, nullable: true }"
    # inline enum cell: "enum | Yes | a / b / c"
    if low.startswith("enum"):
        return "{ type: string }"  # agent will fill values or migrate to named enum
    # default
    return "{ type: string }"


# ── operationId derivation ──────────────────────────────────────────


def derive_operation_id(operation: str, method: str, path: str) -> str:
    """Best-effort operationId from the Operation column.

    "Add client" → "addClient", "Walker self-register" →
    "walkerSelfRegister", "Cancel walk" → "cancelWalk". The agent
    refines if business-verb conventions need a different form.
    """
    # Strip non-word chars except spaces; lowercase-camel-case.
    words = re.split(r"[\s/_-]+", operation.strip())
    words = [w for w in words if w]
    if not words:
        # Fallback: derive from method + path last segment.
        last = re.findall(r"/([^/{]+)", path)
        last_seg = last[-1] if last else "op"
        return f"{method.lower()}{last_seg.title().replace('-', '')}"
    head = re.sub(r"\W+", "", words[0].lower())
    tail = "".join(re.sub(r"\W+", "", w).capitalize() for w in words[1:])
    return head + tail


# ── renderer ────────────────────────────────────────────────────────


def render_openapi(
    domain_name: str,
    auth_ops: list[dict],
    entities: list[tuple[str, list[dict]]],
    enums: dict[str, list[str]],
    error_codes: list[dict],
) -> str:
    lines: list[str] = []
    lines.append("openapi: 3.0.3")
    lines.append("info:")
    lines.append(f"  title: {domain_name} API")
    lines.append(f"  description: REST API for the {domain_name} domain.")
    lines.append("  version: 1.0.0")
    lines.append("  contact:")
    lines.append(f"    name: {domain_name} Domain Spec Set")
    lines.append("    url: https://example.com")
    lines.append("    email: noreply@example.com")
    lines.append("  license:")
    lines.append("    name: MIT")
    lines.append("    url: https://opensource.org/licenses/MIT")
    lines.append("")
    lines.append("servers:")
    lines.append("  - url: https://api.example.com")
    lines.append("    description: Production")
    lines.append("")
    lines.append("security:")
    lines.append("  - bearerAuth: []")
    lines.append("")
    lines.append("tags:")
    seen_tags: set[str] = set()
    for op in auth_ops:
        if op["tag"] not in seen_tags:
            seen_tags.add(op["tag"])
            lines.append(f"  - name: {op['tag']}")
    lines.append("")
    lines.append("paths:")

    # Group ops by path so we emit one path entry with method children.
    by_path: dict[str, list[dict]] = {}
    for op in auth_ops:
        by_path.setdefault(op["path"], []).append(op)

    error_status_to_response = {
        "400": "ValidationError",
        "401": "Unauthorized",
        "403": "Forbidden",
        "404": "NotFound",
        "409": "Conflict",
        "410": "Gone",
    }
    seen_statuses: set[str] = {ec["status"] for ec in error_codes}

    for path, ops in by_path.items():
        lines.append(f"  {path}:")
        # Path-level parameters from {param} segments
        path_params = re.findall(r"\{(\w+)\}", path)
        if path_params:
            lines.append("    parameters:")
            for param in path_params:
                fmt = "uuid" if param.endswith("Id") or param == "id" else ""
                schema = f"{{ type: string, format: {fmt} }}" if fmt else "{ type: string }"
                lines.append(
                    f"      - {{ name: {param}, in: path, required: true, schema: {schema} }}"
                )
        for op in ops:
            method = op["method"].lower()
            op_id = derive_operation_id(op["operation"], method, path)
            lines.append(f"    {method}:")
            lines.append(f"      tags: [{op['tag']}]")
            lines.append(f"      operationId: {op_id}")
            lines.append(f"      summary: {op['operation']}")
            lines.append(f"      description: TODO — describe {op['operation']}.")
            if op["public"]:
                lines.append("      security: []")
            # Idempotency-Key on POSTs (per suite v1.0.9 convention).
            if method == "post":
                lines.append("      parameters:")
                lines.append("        - $ref: '#/components/parameters/IdempotencyKey'")
            # Request body for write methods
            if method in {"post", "patch", "put"}:
                lines.append("      requestBody:")
                lines.append("        required: true")
                lines.append("        content:")
                lines.append("          application/json:")
                lines.append("            schema: { type: object }  # TODO — define request shape")
            # Responses
            lines.append("      responses:")
            success = "201" if method == "post" else "200"
            lines.append(f"        '{success}':")
            lines.append(f"          description: {op['operation']} succeeded")
            lines.append("          content:")
            lines.append("            application/json:")
            lines.append("              schema: { type: object }  # TODO — define response shape")
            # Generic error responses; the agent prunes those not relevant.
            if method != "get":
                lines.append("        '400': { $ref: '#/components/responses/ValidationError' }")
            if not op["public"]:
                lines.append("        '401': { $ref: '#/components/responses/Unauthorized' }")
                lines.append("        '403': { $ref: '#/components/responses/Forbidden' }")
            if path_params:
                lines.append("        '404': { $ref: '#/components/responses/NotFound' }")
            if method == "post":
                lines.append(
                    "        '409': { $ref: '#/components/responses/IdempotencyKeyConflict' }"
                )

    # ── components ──
    lines.append("")
    lines.append("components:")
    lines.append("  securitySchemes:")
    lines.append("    bearerAuth:")
    lines.append("      type: http")
    lines.append("      scheme: bearer")
    lines.append("      bearerFormat: JWT")
    lines.append("")
    lines.append("  parameters:")
    lines.append("    IdempotencyKey:")
    lines.append("      name: Idempotency-Key")
    lines.append("      in: header")
    lines.append("      required: true")
    lines.append("      description: >")
    lines.append("        Client-generated UUID per intent. Lets the server replay the")
    lines.append("        original response on retry. See SUITE-DESIGN §4.6.")
    lines.append("      schema:")
    lines.append("        type: string")
    lines.append("        format: uuid")
    lines.append("    Page:")
    lines.append("      name: page")
    lines.append("      in: query")
    lines.append("      schema: { type: integer, minimum: 1, default: 1 }")
    lines.append("    PageSize:")
    lines.append("      name: pageSize")
    lines.append("      in: query")
    lines.append("      schema: { type: integer, minimum: 1, maximum: 50, default: 20 }")
    lines.append("")
    lines.append("  responses:")
    lines.append("    Unauthorized:")
    lines.append("      description: Missing or invalid bearer token")
    lines.append("      content:")
    lines.append("        application/json:")
    lines.append("          schema: { $ref: '#/components/schemas/Error' }")
    lines.append("    Forbidden:")
    lines.append("      description: Caller lacks the required role or ownership")
    lines.append("      content:")
    lines.append("        application/json:")
    lines.append("          schema: { $ref: '#/components/schemas/Error' }")
    lines.append("    NotFound:")
    lines.append("      description: Resource does not exist")
    lines.append("      content:")
    lines.append("        application/json:")
    lines.append("          schema: { $ref: '#/components/schemas/Error' }")
    lines.append("    Conflict:")
    lines.append("      description: Resource is in a state that disallows the operation")
    lines.append("      content:")
    lines.append("        application/json:")
    lines.append("          schema: { $ref: '#/components/schemas/Error' }")
    lines.append("    IdempotencyKeyConflict:")
    lines.append("      description: >")
    lines.append("        The Idempotency-Key was previously used with a different")
    lines.append("        request body. Generate a new key for a different intent.")
    lines.append("      content:")
    lines.append("        application/json:")
    lines.append("          schema: { $ref: '#/components/schemas/Error' }")
    lines.append("    ValidationError:")
    lines.append("      description: Request failed validation")
    lines.append("      content:")
    lines.append("        application/json:")
    lines.append("          schema: { $ref: '#/components/schemas/ValidationError' }")
    if "410" in seen_statuses:
        lines.append("    Gone:")
        lines.append("      description: Token has expired or been used")
        lines.append("      content:")
        lines.append("        application/json:")
        lines.append("          schema: { $ref: '#/components/schemas/Error' }")
    lines.append("")
    lines.append("  schemas:")
    # Error schemas
    lines.append("    Error:")
    lines.append("      type: object")
    lines.append("      required: [code, message]")
    lines.append("      properties:")
    lines.append("        code: { type: string }")
    lines.append("        message: { type: string }")
    lines.append("    ValidationError:")
    lines.append("      type: object")
    lines.append("      required: [code, message]")
    lines.append("      properties:")
    lines.append("        code: { type: string }")
    lines.append("        message: { type: string }")
    lines.append("        details:")
    lines.append("          type: array")
    lines.append("          items:")
    lines.append("            type: object")
    lines.append("            properties:")
    lines.append("              field: { type: string }")
    lines.append("              message: { type: string }")

    # Named enums
    for enum_name, values in enums.items():
        lines.append(f"    {enum_name}:")
        lines.append("      type: string")
        values_yaml = ", ".join(values)
        lines.append(f"      enum: [{values_yaml}]")

    # Entity schemas
    for entity_name, attrs in entities:
        lines.append(f"    {entity_name}:")
        lines.append("      type: object")
        required_attrs = [a["name"] for a in attrs if a["required"] and not a["secret"]]
        if required_attrs:
            lines.append(f"      required: [{', '.join(required_attrs)}]")
        lines.append("      properties:")
        for attr in attrs:
            if attr["secret"]:
                # Sensitive attrs: comment to flag for the agent.
                lines.append(
                    f"        # {attr['name']}: [secret] — omit from response shapes; include in request shapes only where required."
                )
                continue
            schema = model_type_to_openapi(attr["type"], attr["name"])
            lines.append(f"        {attr['name']}: {schema}")

    return "\n".join(lines).rstrip() + "\n"


# ── main ────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a contracts/openapi.yaml skeleton from upstream specs."
    )
    parser.add_argument(
        "--domain-model",
        default="docs/specifications/domain-model.md",
        help="Path to domain-model.md",
    )
    parser.add_argument(
        "--auth-matrix",
        default="docs/specifications/auth-matrix.md",
        help="Path to auth-matrix.md",
    )
    parser.add_argument(
        "--error-catalogue",
        default="docs/specifications/error-catalogue.md",
        help="Path to error-catalogue.md",
    )
    parser.add_argument(
        "--openapi",
        default="docs/specifications/contracts/openapi.yaml",
        help="Path to write openapi.yaml",
    )
    parser.add_argument(
        "--domain-name",
        default=None,
        help="Domain name for the openapi info.title. Defaults to the first "
        "word(s) after `# Domain Model — ` in domain-model.md.",
    )
    parser.add_argument("--stdout", action="store_true", help="Print to stdout instead of writing.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing non-template openapi.yaml.",
    )
    args = parser.parse_args(argv)

    dm_path = pathlib.Path(args.domain_model).resolve()
    am_path = pathlib.Path(args.auth_matrix).resolve()
    ec_path = pathlib.Path(args.error_catalogue).resolve()

    for p, label in [(dm_path, "domain-model"), (am_path, "auth-matrix")]:
        if not p.is_file():
            print(f"openapi_skeleton: {label} not found at {p}", file=sys.stderr)
            return 1

    dm_text = dm_path.read_text(encoding="utf-8")
    am_text = am_path.read_text(encoding="utf-8")
    ec_text = ec_path.read_text(encoding="utf-8") if ec_path.is_file() else ""

    domain_name = args.domain_name
    if domain_name is None:
        m = re.match(r"#\s+Domain Model\s*[—-]\s*(?P<name>.+)", dm_text)
        domain_name = m.group("name").strip() if m else "[Domain]"

    auth_ops = parse_auth_matrix(am_text)
    if not auth_ops:
        print(
            f"openapi_skeleton: no operations found under `## Auth Matrix` in {am_path}",
            file=sys.stderr,
        )
        return 1
    entities = parse_entities(dm_text)
    enums = parse_enumerations(dm_text)
    error_codes = parse_error_codes(ec_text)

    rendered = render_openapi(domain_name, auth_ops, entities, enums, error_codes)

    if args.stdout:
        sys.stdout.write(rendered)
        return 0

    out_path = pathlib.Path(args.openapi).resolve()
    if out_path.is_file() and not args.force:
        existing = out_path.read_text(encoding="utf-8")
        looks_template = (
            len(existing) < 200 or "[Domain]" in existing or "TODO — describe" in existing
        )
        if not looks_template:
            print(
                f"openapi_skeleton: {out_path} already exists and doesn't look "
                "like a template. Pass --force to overwrite.",
                file=sys.stderr,
            )
            return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")
    print(
        f"Wrote openapi skeleton to {out_path}: "
        f"{len(auth_ops)} operations, {len(entities)} entities, "
        f"{len(enums)} enums, {len(error_codes)} error codes."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
