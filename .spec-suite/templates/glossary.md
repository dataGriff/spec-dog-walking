# Glossary — [Domain]

> The ubiquitous language for the [Domain] domain. Every entity name
> and every attribute name used in `domain-model.md`,
> `contracts/openapi.yaml`, `contracts/asyncapi.yaml`, and
> `contracts/datacontract.yaml` appears here exactly as it is used.
> Code, docs, and conversation must use these terms.

---

## Entities

### [Resource1]

[One- or two-sentence description of what a [Resource1] is in this
domain. Reference its lifecycle and ownership relationships in plain
language.]

---

## [Resource1] attributes

### id

UUID. Unique identifier of a [Resource1]. Immutable.

### [attribute1]

[Describe each attribute in turn: type, format, what it means in
business terms, whether it's immutable, any uniqueness or relational
constraints.]

### createdAt

ISO 8601 timestamp. The moment the [Resource1] was first persisted.
Immutable.

### updatedAt

ISO 8601 timestamp. The moment the [Resource1] was last modified.

---

## Roles

### [role1]

[Describe what this role can do, and how it maps to a PRD persona.]

---

## Domain events

### [Resource1]Created

Published on `[domain].[resource1].created` whenever a new
[Resource1] is added. Payload is the full record.

### [Resource1]Updated

Published on `[domain].[resource1].updated` whenever a [Resource1]
changes. Payload is the full record post-change.

---

## Other terms

### [domain-specific concept]

[Define every other term that appears in code or specs and would not
be obvious from name alone. Keep entries short.]
