# Sequence Diagrams

> **Template placeholder.** Do not edit in place. The suite's flows
> skill copies this into `docs/specifications/sequence-diagrams.md`
> when Phase 4 starts (or run `task domain:init` to copy every template
> at once).

---

## Overview

This document contains Mermaid sequence diagrams for the key interaction flows in this domain.

Each diagram shows the sequence of API calls and system events for a specific user journey.

---

## Flow 1: [Name — e.g. Registration and Login]

> TODO: Replace with your domain's registration/login flow, or remove if not applicable.

```mermaid
sequenceDiagram
    participant Client
    participant API

    Client->>API: POST /v1/auth/register (email, password, role)
    API-->>Client: 201 { accessToken, refreshToken }

    Client->>API: POST /v1/auth/login (email, password)
    API-->>Client: 200 { accessToken, refreshToken }
```

---

## Flow 2: [Name — e.g. Create and List Resource1]

> TODO: Replace with your domain's primary resource creation flow.

```mermaid
sequenceDiagram
    participant [role1] as [Role1 Client]
    participant API

    [role1]->>API: POST /v1/[resource1] (body)
    API-->>role1]: 201 { id, ... }

    [role1]->>API: GET /v1/[resource1]
    API-->>role1]: 200 [{ id, ... }, ...]
```

---

## Flow 3: [Name — e.g. Cross-role interaction]

> TODO: Replace with a flow showing how two roles interact through the API.

```mermaid
sequenceDiagram
    participant [role1] as [Role1 Client]
    participant [role2] as [Role2 Client]
    participant API

    [role1]->>API: POST /v1/[resource1] (create)
    API-->>role1]: 201 { id, status: "pending" }

    [role2]->>API: GET /v1/[resource2]?status=pending
    API-->>role2]: 200 [{ id, ... }]

    [role2]->>API: POST /v1/[resource2]/{id}/accept
    API-->>role2]: 200 { id, status: "accepted" }
```

---

## Flow 4: [Name — e.g. State transition]

> TODO: Add flows for each significant state transition in your domain.

```mermaid
sequenceDiagram
    participant [role] as [Role Client]
    participant API

    [role]->>API: POST /v1/[resource]/{id}/[action]
    API-->>role]: 200 { id, status: "[new_status]" }
```

---

## Notes

- All authenticated requests include `Authorization: Bearer <token>` header (omitted from diagrams for brevity)
- `4xx` error paths are omitted from diagrams; see `auth-matrix.md` for access control rules
