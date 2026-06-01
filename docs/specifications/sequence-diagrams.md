# Sequence Diagrams — Dog Walking

Interaction flows for the Dog Walking domain. Diagrams reference
operation paths from `contracts/openapi.yaml` and event channels
from `contracts/asyncapi.yaml` (Phase 6) by name. Participants are
named consistently with the auth-matrix roles (`walker`, `owner`)
and the conventional system actors (`API`, `EventBus`).

---

## Flow 1: Authentication — Walker self-registers and logs in

```mermaid
sequenceDiagram
    participant walker
    participant API
    participant EventBus

    walker->>API: POST /v1/auth/register<br/>{ email, password, role: "walker" }
    API-->>walker: 201 { accessToken, refreshToken, user }

    Note over API: Subsequent logins use POST /v1/auth/login
    walker->>API: POST /v1/auth/login<br/>{ email, password }
    API-->>walker: 200 { accessToken, refreshToken }
```

---

## Flow 2: Authentication — Client invite + registration + login

Covers US-001 (walker adds client), US-002 (client accepts invite),
US-003 (subsequent logins).

```mermaid
sequenceDiagram
    participant walker
    participant API
    participant EventBus
    participant owner

    walker->>API: POST /v1/clients<br/>{ name, email }
    API->>EventBus: publish dogwalking.invite.created
    API-->>walker: 201 { clientId, inviteId }
    Note over API: Invite email queued with 1-day TTL

    owner->>API: POST /v1/invites/{token}/accept<br/>{ password }
    API->>EventBus: publish dogwalking.client.registered
    API-->>owner: 200 { accessToken, refreshToken }

    owner->>API: POST /v1/auth/login<br/>{ email, password }
    API-->>owner: 200 { accessToken, refreshToken }
```

---

## Flow 3a: Authentication — Invite lifecycle (pending → accepted; expired path)

```mermaid
sequenceDiagram
    participant walker
    participant API
    participant owner

    walker->>API: POST /v1/clients
    Note over API: Invite created with status "pending", expiresAt = now + 1 day

    alt Recipient accepts in time
        owner->>API: POST /v1/invites/{token}/accept
        Note over API: Invite transitions pending → accepted
        API-->>owner: 200 (tokens)
    else TTL elapses first
        owner->>API: POST /v1/invites/{token}/accept (more than 1 day later)
        Note over API: Invite lazily transitions pending → expired
        API-->>owner: 410 INVITE_EXPIRED
    end
```

---

## Flow 3: Authentication — Password reset

Covers US-004.

```mermaid
sequenceDiagram
    participant owner
    participant API

    owner->>API: POST /v1/auth/password-reset/request<br/>{ email }
    API-->>owner: 204 No Content
    Note over API: Always 204 regardless of whether email is known<br/>(account enumeration defense)

    owner->>API: POST /v1/auth/password-reset/confirm<br/>{ token, newPassword }
    API-->>owner: 200 OK
    Note over API: All existing refresh tokens for the user are revoked
```

---

## Flow 3b: Authentication — Password-reset token lifecycle (pending → used; expired path)

```mermaid
sequenceDiagram
    participant owner
    participant API

    owner->>API: POST /v1/auth/password-reset/request
    Note over API: Reset token created with status "pending", expiresAt = now + 1 hour

    alt Confirm in time
        owner->>API: POST /v1/auth/password-reset/confirm {token, newPassword}
        Note over API: Token transitions pending → used; refresh tokens revoked
        API-->>owner: 200 OK
    else TTL elapses first
        owner->>API: POST /v1/auth/password-reset/confirm (more than 1 hour later)
        Note over API: Token lazily transitions pending → expired
        API-->>owner: 410 RESET_TOKEN_EXPIRED
    end
```

---

## Flow 4: Dogs — Owner adds and updates a dog

Covers US-005, US-006.

```mermaid
sequenceDiagram
    participant owner
    participant API
    participant EventBus

    owner->>API: POST /v1/dogs<br/>{ name, breed, age, medication, vetName, vetPhone, notes }
    API-->>owner: 201 { dogId, ... }
    API->>EventBus: publish dogwalking.dog.added

    owner->>API: PATCH /v1/dogs/{dogId}<br/>{ medication: "updated" }
    API-->>owner: 200 { dogId, ... }
    API->>EventBus: publish dogwalking.dog.updated
```

---

## Flow 5: Bookings — Owner-requested walk → walker decides

Covers US-007 (owner path), US-008, US-009, US-010.

```mermaid
sequenceDiagram
    participant owner
    participant API
    participant walker
    participant EventBus

    owner->>API: POST /v1/walks<br/>{ dogId, startAt, durationMinutes, walkType }
    API-->>owner: 201 { walkId, status: "requested" }
    API->>EventBus: publish dogwalking.walk.requested

    walker->>API: PATCH /v1/walks/{walkId}/decision<br/>{ decision: "scheduled" }
    API-->>walker: 200 { walkId, status: "scheduled" }
    API->>EventBus: publish dogwalking.walk.scheduled

    Note over walker,owner: Either party may cancel before the walk happens

    owner->>API: POST /v1/walks/{walkId}/cancel
    API-->>owner: 200 { walkId, status: "cancelled" }
    API->>EventBus: publish dogwalking.walk.cancelled

    owner->>API: GET /v1/walks?status=scheduled
    API-->>owner: 200 { data: [...], pagination: { ... } }
```

---

## Flow 6: Bookings — Walker declines a request

Covers the `requested → declined` path of US-008.

```mermaid
sequenceDiagram
    participant owner
    participant API
    participant walker
    participant EventBus

    owner->>API: POST /v1/walks<br/>{ dogId, startAt, durationMinutes, walkType }
    API-->>owner: 201 { walkId, status: "requested" }
    API->>EventBus: publish dogwalking.walk.requested

    walker->>API: PATCH /v1/walks/{walkId}/decision<br/>{ decision: "declined", reason: "already booked" }
    API-->>walker: 200 { walkId, status: "declined" }
    API->>EventBus: publish dogwalking.walk.declined

    owner->>API: GET /v1/walks?status=declined
    API-->>owner: 200 { data: [{walkId, status: "declined", declinedReason}] }
```

---

## Flow 7: Bookings — Walker creates walk directly (skip request stage)

Covers US-007 (walker path) — when Alison takes a booking via
WhatsApp and enters it in the app on the client's behalf.

```mermaid
sequenceDiagram
    participant walker
    participant API
    participant EventBus

    walker->>API: POST /v1/walks<br/>{ dogId, startAt, durationMinutes, walkType }
    API-->>walker: 201 { walkId, status: "scheduled" }
    API->>EventBus: publish dogwalking.walk.scheduled
    Note over API: Walker-created walks skip the `requested` state
```

---

## Flow 8: Walks — Complete + post updates with photos

Covers US-011, US-012, US-013.

```mermaid
sequenceDiagram
    participant walker
    participant API
    participant EventBus
    participant owner

    walker->>API: POST /v1/walks/{walkId}/updates<br/>multipart: notes + photos[]
    API-->>walker: 201 { updateId, photoIds: [...] }
    API->>EventBus: publish dogwalking.walkupdate.posted
    Note over walker: Live update during the walk

    walker->>API: POST /v1/walks/{walkId}/complete
    API-->>walker: 200 { walkId, status: "completed", completedAt }
    API->>EventBus: publish dogwalking.walk.completed
    Note over API: Walk transitions scheduled → completed

    walker->>API: POST /v1/walks/{walkId}/updates<br/>multipart: notes + photos[]
    API-->>walker: 201 { updateId, photoIds: [...] }
    API->>EventBus: publish dogwalking.walkupdate.posted
    Note over walker: Post-hoc update — allowed in `completed` too

    owner->>API: GET /v1/walks/{walkId}/updates
    API-->>owner: 200 [{ updateId, notes, photos: [{id, contentType, ...}] }]

    owner->>API: GET /v1/walk-updates/{updateId}/photos/{photoId}
    API-->>owner: 200 (image bytes)
```

---

## Flow 9: Pricing — Walker sets rate card, owner views it

Covers US-017, US-018.

```mermaid
sequenceDiagram
    participant walker
    participant API
    participant EventBus
    participant owner

    walker->>API: PUT /v1/rate-card<br/>{ entries: [{walkType, durationMinutes, priceCents, currency}] }
    API-->>walker: 200 { entries: [...] }
    API->>EventBus: publish dogwalking.ratecard.updated

    owner->>API: GET /v1/rate-card
    API-->>owner: 200 { entries: [...] }
    Note over API: Owner sees only the rate card of their assigned walker
```

---

## Flow 10: Invoicing & Tipping — Generate, view, mark paid (with optional tip)

Covers US-014, US-015, US-016.

```mermaid
sequenceDiagram
    participant walker
    participant API
    participant EventBus
    participant owner

    walker->>API: POST /v1/invoices<br/>{ clientId, periodStart, periodEnd }
    API-->>walker: 201 { invoiceId, totalCents, lineItems: [...] }
    API->>EventBus: publish dogwalking.invoice.issued
    Note over API: Line-item prices snapshotted from rate card at each walk's scheduled transition

    owner->>API: GET /v1/invoices?status=issued
    API-->>owner: 200 { data: [{invoiceId, totalCents, status: "issued"}], ... }

    walker->>API: POST /v1/invoices/{invoiceId}/mark-paid<br/>{ paidAt, paidVia: "bank transfer", tipCents: 500 }
    Note over walker,API: US-019 — tipCents is optional (defaults to 0)
    API-->>walker: 200 { invoiceId, status: "paid", paidAt, paidVia }
    API->>EventBus: publish dogwalking.invoice.paid

    owner->>API: GET /v1/invoices?status=paid
    API-->>owner: 200 { data: [{invoiceId, status: "paid"}], ... }
```
