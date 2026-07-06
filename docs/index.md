# DogWalking

A design-and-contracts-only workspace for the long-lived business
requirements, rules, and contracts of the DogWalking domain.

---

## Start here

This spec set is written for two audiences: **humans** reviewing the
domain's behaviour, and **AI coding agents** implementing it. Both
should read in dependency order — each document assumes the ones
before it:

1. [Domain Overview](specifications/domain-overview.html) — generated
   orientation: operations, events, entities, ER diagram
2. [Product Requirements](specifications/prd.md) — why the domain exists
3. [Domain Model](specifications/domain-model.md) — entities,
   attributes, rules, lifecycles, events (the structural authority)
4. [Auth Matrix](specifications/auth-matrix.md) and
   [Error Catalogue](specifications/error-catalogue.md) — access and
   failure semantics
5. [Sequence Diagrams](specifications/sequence-diagrams.md) — how it
   composes
6. [Acceptance Scenarios](specifications/acceptance-scenarios.md) and
   [NFRs](specifications/nfr.md) — the testable definition of done
7. [Contracts](specifications/contracts/openapi.yaml) — the exact
   REST/event/data surfaces

Implementing this domain? Follow the
[implementation guide](https://github.com/dataGriff/spec-dog-walking/blob/main/.github/instructions/api-implementation.instructions.md)
(`.github/instructions/api-implementation.instructions.md`) — reading
order, authority hierarchy, build workflow, verification loop.

---

## Specifications

All authoritative business requirements live in `docs/specifications/`.
**Code must conform to specs, not the other way around.**

| Document | Description |
|---|---|
| [Product Requirements](specifications/prd.md) | Problem statement, personas, user stories, goals |
| [Domain Model](specifications/domain-model.md) | Entities, attributes, relationships, business rules |
| [Glossary](specifications/glossary.md) | Ubiquitous language — every entity, attribute, role, event, and key term |
| [Auth Matrix](specifications/auth-matrix.md) | Roles and which operations each role may perform |
| [Error Catalogue](specifications/error-catalogue.md) | Canonical error codes with HTTP status, meaning, and triggers |
| [Sequence Diagrams](specifications/sequence-diagrams.md) | Key interaction flows (Mermaid) |
| [Non-Functional Requirements](specifications/nfr.md) | Measurable thresholds: performance, availability, security, observability |
| [Acceptance Scenarios](specifications/acceptance-scenarios.md) | Given/When/Then scenarios mapped to user stories at contract level |
| [**Domain Overview →**](specifications/domain-overview.html) | Auto-generated: operations, events, entities, ER diagram and data contract in one page |
| [**Traceability Matrix →**](specifications/traceability.html) | Auto-generated: user story → scenarios → operations → events → error codes, with coverage flags |
| [**Interactive API Reference →**](specifications/api-reference.html) | OpenAPI 3.0.3 contract — live try-it-out |
| [**AsyncAPI Event Reference →**](specifications/asyncapi-reference.html) | Domain event catalogue — CloudEvents schemas |
| [**Data Contract Reference →**](specifications/datacontract-reference.html) | ODCS 3.1 data contract — historical event payload schema + SLAs |

Raw contract files: [`specifications/contracts/openapi.yaml`](specifications/contracts/openapi.yaml) · [`specifications/contracts/asyncapi.yaml`](specifications/contracts/asyncapi.yaml) · [`specifications/contracts/datacontract.yaml`](specifications/contracts/datacontract.yaml)

---

## Tasks

All automation is in `Taskfile.yml`.
Always use `task`.

```bash
task                # list all available tasks
task lint           # lint OpenAPI + AsyncAPI + data contract
task lint:datacontract  # lint ODCS data contract only
task domain:check   # lint + regenerate domain overview
task docs:generate  # (re)generate the domain overview HTML page from specs
task docs:serve     # serve this documentation site locally
```

---

## Key Principles

1. **Specs drive code.** If code and spec disagree, fix the code — not the spec.
2. **Do not edit `docs/specifications/` incidentally.** Spec changes are deliberate business decisions.
3. **Domain model is authoritative for naming.** Entity and attribute names defined here must be used consistently across implementations.
4. **Auth matrix is authoritative for access control.** Implementation access logic must match it exactly.
5. **OpenAPI contract is authoritative for the REST API.** Paths, methods, request/response shapes, and status codes must match.
6. **AsyncAPI contract is authoritative for domain events.** Event channel names, message schemas, and CloudEvents attributes must match `docs/specifications/contracts/asyncapi.yaml`.
7. **Data contract is authoritative for historical event payload schema.** Field names, types, and constraints in `docs/specifications/contracts/datacontract.yaml` must match the published event payloads.
8. **Task-first.** Run `task` to discover commands. If no task exists for an operation, add one before running it.
9. **Business language over CRUD.** Use domain verbs in specs, user stories, descriptions, and comments. Prefer "add / edit / remove / archive" over "create / update / delete" in any human-readable context. HTTP methods and technical identifiers keep their technical names.
10. **Implementation guidance is reusable and technology-agnostic.** Use `.github/instructions/api-implementation.instructions.md` to implement these contracts consistently, without prescribing a framework/runtime.

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
