# Implementing this domain from its spec set

Guidance for anyone — human engineer or AI coding agent — building a
service from the specs in this repository. It is deliberately
technology-agnostic: it never chooses your language, framework,
database, or hosting. It tells you how to consume the spec set so any
implementation, in any stack, converges on the same behaviour.

## The contract between specs and code

**Specs are upstream. Code conforms to specs, never the reverse.**
If the implementation needs something the specs don't say, that is a
spec change: raise it through the spec repo's update flow (the
`domain-orchestrator` skill), get it signed off, then implement. Do
not quietly diverge — the conformance audit and the acceptance
scenarios are written against the specs, and drift between the two is
a defect in the code.

## Reading order

Read in this order; each document assumes the ones before it.

1. `docs/specifications/prd.md` — why the domain exists: problem,
   personas, user stories, non-goals, constraints.
2. `docs/specifications/domain-model.md` — the authoritative
   structural truth: entities, attributes (the only place attributes
   are documented), relationships, business rules, status lifecycles,
   enumerations, aggregates, domain events.
3. `docs/specifications/glossary.md` — the ubiquitous language. Use
   these exact names in code, APIs, and conversation.
4. `docs/specifications/auth-matrix.md` — roles, per-operation
   permissions, ownership/visibility rules, failure semantics.
5. `docs/specifications/error-catalogue.md` — every error code, its
   HTTP status, meaning, and trigger.
6. `docs/specifications/sequence-diagrams.md` — how the operations
   and events compose into flows, including event-publish ordering.
7. `docs/specifications/nfr.md` — measurable thresholds the
   implementation must meet (performance, availability, security,
   privacy/retention, observability).
8. `docs/specifications/acceptance-scenarios.md` — the testable
   definition of done, one Given/When/Then set per user story.
9. `docs/specifications/contracts/` — `openapi.yaml` (REST surface),
   `asyncapi.yaml` (event surface), `datacontract.yaml` (historic
   event-payload record + its SLAs).

The generated views (`domain-overview.html`, the traceability matrix,
and the API/AsyncAPI/data-contract references) are orientation aids —
derived, never authoritative.

## Authority hierarchy

When two artefacts appear to disagree, precedence for each surface:

- **Naming** — `domain-model.md` (and `glossary.md` for language).
- **Access control** — `auth-matrix.md`.
- **REST API shape** — `contracts/openapi.yaml`.
- **Event shape and channels** — `contracts/asyncapi.yaml`.
- **Historic event payload data** — `contracts/datacontract.yaml`.
- **Error semantics** — `error-catalogue.md`.

An apparent disagreement is usually a misreading; if it is real, it is
a spec bug — report it upstream rather than picking a side in code.

## Build workflow

A dependency-ordered sequence that works in any stack:

1. **Generate or hand-derive types from the contracts.** Entity and
   request/response types from `openapi.yaml`; event envelope and
   payload types from `asyncapi.yaml`. Do not hand-invent shapes the
   contracts already define.
2. **Persistence.** Design storage from `domain-model.md`: entity
   attribute tables give you fields and nullability; business rules
   give you uniqueness and immutability constraints; lifecycles give
   you legal state transitions; aggregates tell you what is written
   (and published) atomically. Storage layout is your choice — the
   model constrains behaviour, not schema style.
3. **Authentication and authorisation middleware** from
   `auth-matrix.md`, including its failure semantics (which denials
   are 403 vs 404) — get this layer right before any endpoint, since
   every scenario assumes it.
4. **Error surface.** Implement the error envelope and every code in
   `error-catalogue.md` at its documented status. Nothing else is a
   legal error body.
5. **Endpoints + events, story by story.** Work through
   `acceptance-scenarios.md` in user-story order; each story names
   the operations it needs. Publish the domain events the model's
   Domain Events table binds to each transition — after the HTTP
   response, carrying full entity state (see the asyncapi payloads),
   with the delivery guarantee `nfr.md` specifies.
6. **NFR pass.** Rate limiting, retention/privacy jobs, observability
   and performance budgets from `nfr.md` — these are requirements
   with thresholds, not suggestions.

## Verification loop

- **Acceptance scenarios are the test suite.** Automate every
  scenario in `acceptance-scenarios.md` as an end-to-end test at the
  HTTP/event level — the Given/When/Then blocks use concrete legal
  literals, real paths, and schema property paths precisely so they
  can be executed verbatim. A story's scenarios passing is the
  definition of that story being done.
- **Validate against the contracts continuously**: responses against
  `openapi.yaml`, published events against `asyncapi.yaml` (contract
  tests or schema validation in CI).
- **Keep the spec repo's audit green.** If you changed specs along
  the way, `task audit` in the spec repo must pass before the change
  counts.

## For AI coding agents specifically

- Treat this file plus the reading order above as your context
  priming; do not skim-sample random spec files.
- Never edit `docs/specifications/` as a side effect of
  implementation work — spec changes go through the suite's
  orchestrator with sign-off.
- When a spec is ambiguous, prefer the stricter reading and surface
  the ambiguity; do not fill gaps with invented behaviour.
- Use the glossary's exact terms for identifiers and API surface —
  synonyms and casing drift are defects.
