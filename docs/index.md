# DogWalking

A design-and-contracts-only workspace for the long-lived business
requirements, rules, and contracts of the DogWalking domain.
Written for two audiences: **humans** reviewing the domain's
behaviour, and **AI coding agents** implementing it.

---

## Read in this order

Each document assumes the ones before it.

| # | Document | What it answers | Authoritative for |
|---|----------|-----------------|-------------------|
| 1 | [Domain Overview](specifications/domain-overview.html) | 60-second orientation: operations, events, entities, ER diagram | Nothing — generated view |
| 2 | [Product Requirements](specifications/prd.md) | Why the domain exists: problem, personas, stories, non-goals | Product intent |
| 3 | [Domain Model](specifications/domain-model.md) | Entities, attributes, rules, lifecycles, events | Naming & structure |
| 4 | [Glossary](specifications/glossary.md) | The ubiquitous language, one definition per term | Domain language |
| 5 | [Auth Matrix](specifications/auth-matrix.md) | Who may do what, and how denials behave | Access control |
| 6 | [Error Catalogue](specifications/error-catalogue.md) | Every error code, status, meaning, trigger | Error semantics |
| 7 | [Sequence Diagrams](specifications/sequence-diagrams.md) | How operations and events compose into flows | — (illustrative) |
| 8 | [Non-Functional Requirements](specifications/nfr.md) | Measurable thresholds: performance, availability, security, privacy | Quality thresholds |
| 9 | [Acceptance Scenarios](specifications/acceptance-scenarios.md) | The testable definition of done, per user story | Testable behaviour |
| 10 | Contracts: [API Reference](specifications/api-reference.html) · [AsyncAPI Events](specifications/asyncapi-reference.html) · [Data Contract](specifications/datacontract-reference.html) | The exact REST, event, and historic-data surfaces | REST / event / historic payload shape |
| 11 | [Implementation Guide](implementation-guide.md) | How an engineer or AI agent builds a service from all of the above | Build workflow |

Raw contract sources: [`openapi.yaml`](specifications/contracts/openapi.yaml) · [`asyncapi.yaml`](specifications/contracts/asyncapi.yaml) · [`datacontract.yaml`](specifications/contracts/datacontract.yaml)

## Generated views

Derived from the specs on every docs build (`task docs:generate`) —
orientation and QA views, **never authoritative**.

| View | Purpose |
|------|---------|
| [Domain Overview](specifications/domain-overview.html) | One-page orientation: operations, events, correlation, enumerations, ER diagram |
| [Traceability Matrix](specifications/traceability.html) | Coverage dashboard: story → scenarios → operations → events → error codes, with gap flags |
| [API Reference](specifications/api-reference.html) | Interactive OpenAPI (try-it-out) |
| [AsyncAPI Event Reference](specifications/asyncapi-reference.html) | Interactive event catalogue (CloudEvents) |
| [Data Contract Reference](specifications/datacontract-reference.html) | ODCS record browser + SLAs |

---

## Tasks

All automation is in `Taskfile.yml`.
Always use `task`.

```bash
task                # list all available tasks
task lint           # lint OpenAPI + AsyncAPI + data contract
task lint:datacontract  # lint ODCS data contract only
task domain:check   # lint + regenerate generated views
task docs:generate  # (re)generate domain overview, traceability matrix, and data contract reference
task docs:serve     # serve this documentation site locally
```

---

## Authority Map

When two artifacts appear to disagree, this is the precedence — an
apparent disagreement is usually a misreading; a real one is a spec
bug to fix upstream, not a side to pick in code.

| Surface | Authoritative artifact |
|---------|------------------------|
| Naming & structure (entities, attributes, relationships, lifecycles) | `domain-model.md` |
| Ubiquitous language | `glossary.md` |
| Access control & denial semantics | `auth-matrix.md` |
| REST surface (paths, methods, shapes, status codes) | `contracts/openapi.yaml` |
| Event surface (channels, messages, CloudEvents attributes) | `contracts/asyncapi.yaml` |
| Historic event payloads + data SLAs | `contracts/datacontract.yaml` |
| Error codes, statuses, triggers | `error-catalogue.md` |
| Testable behaviour | `acceptance-scenarios.md` |
| **Open-enum full value lists** | **The contract** — the domain model deliberately holds a representative subset for enums marked `(open)`; the contract carries the complete list, and additions are a minor version bump |

## Key Principles

1. **Specs drive code.** If code and spec disagree, fix the code — not the spec.
2. **Do not edit `docs/specifications/` incidentally.** Spec changes are deliberate business decisions, made through the suite's `domain-orchestrator` skill.
3. **Task-first.** Run `task` to discover commands. If no task exists for an operation, add one before running it.
4. **Business language over CRUD.** Use domain verbs in specs, user stories, descriptions, and comments. Prefer "add / edit / remove / archive" over "create / update / delete" in any human-readable context. HTTP methods and technical identifiers keep their technical names.
5. **Implementation guidance lives once.** [`implementation-guide.md`](implementation-guide.md) is the canonical build playbook; `AGENTS.md` and `.github/instructions/` are thin pointers to it for agent-native discovery.

---

## About This Repository

This repository was bootstrapped by the
[`domain-spec-suite`](https://github.com/dataGriff/domain-spec-suite),
which drives a user through an eight-phase walk (Bootstrap → Discovery
→ Modeling → Access Control → Flows → NFRs → Contracts → Audit) and
produces a complete, internally-consistent spec set whose every
cross-reference can be verified.

To continue or update this spec set, invoke the
`domain-orchestrator` skill from the suite — it reads
`.spec-suite/progress.yaml` and routes you to the right
phase.
