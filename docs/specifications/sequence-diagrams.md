# Sequence Diagrams — Dog Walking

Interaction flows for the Dog Walking domain. Diagrams reference
operation paths from `contracts/openapi.yaml` and event channels
from `contracts/asyncapi.yaml` (Phase 6) by name. Participants are
named consistently with the auth-matrix roles (`walker`, `owner`)
and the conventional system actors (`API`, `EventBus`).

---

## Flow 1: Authentication — Walker self-registers, logs in, refreshes, logs out

Covers US-000, US-003, US-021, US-022.

```mermaid
sequenceDiagram
    participant walker
    participant API
    participant EventBus

    walker->>API: POST /v1/auth/register<br/>{ email, password, displayName }
    API-->>walker: 201 { accessToken, refreshToken }
    API->>EventBus: publish dogwalking.user.registered
    API->>EventBus: publish dogwalking.walker.registered

    Note over API: Subsequent logins use POST /v1/auth/login
    walker->>API: POST /v1/auth/login<br/>{ email, password }
    API-->>walker: 200 { accessToken, refreshToken }

    Note over walker: Access token expires after 15 minutes (NFR-SEC-001)
    walker->>API: POST /v1/auth/refresh<br/>{ refreshToken }
    API-->>walker: 200 { accessToken, refreshToken }
    Note over API: Presented refresh token is rotated — reuse returns 401 INVALID_REFRESH_TOKEN

    walker->>API: POST /v1/auth/logout<br/>{ refreshToken }
    API-->>walker: 204 No Content

    walker->>API: POST /v1/auth/refresh<br/>{ refreshToken (revoked) }
    API-->>walker: 401 INVALID_REFRESH_TOKEN
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
    API-->>walker: 201 { id, email, status: "pending", expiresAt }
    API->>EventBus: publish dogwalking.invite.created
    Note over API: Invite email queued with 1-day TTL.<br/>No Client record yet — it is created at acceptance.

    owner->>API: POST /v1/invites/{token}/accept<br/>{ password }
    API-->>owner: 200 { accessToken, refreshToken }
    API->>EventBus: publish dogwalking.invite.accepted
    API->>EventBus: publish dogwalking.user.registered
    API->>EventBus: publish dogwalking.client.registered
    Note over API: Client record created here; invite.accepted and<br/>client.registered both carry inviteId for lineage

    owner->>API: POST /v1/auth/login<br/>{ email, password }
    API-->>owner: 200 { accessToken, refreshToken }
```

---

## Flow 2a: Authentication — Invite lifecycle (pending → accepted; expired path)

```mermaid
sequenceDiagram
    participant walker
    participant API
    participant EventBus
    participant owner

    walker->>API: POST /v1/clients
    Note over API: Invite created with status "pending", expiresAt = now + 1 day
    API->>EventBus: publish dogwalking.invite.created

    alt Recipient accepts in time
        owner->>API: POST /v1/invites/{token}/accept
        Note over API: Invite transitions pending → accepted
        API-->>owner: 200 (tokens)
        API->>EventBus: publish dogwalking.invite.accepted
    else TTL elapses first
        owner->>API: POST /v1/invites/{token}/accept (more than 1 day later)
        Note over API: Invite lazily transitions pending → expired
        API-->>owner: 410 INVITE_EXPIRED
        API->>EventBus: publish dogwalking.invite.expired
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

    owner->>API: POST /v1/auth/refresh<br/>{ refreshToken (issued before the reset) }
    API-->>owner: 401 INVALID_REFRESH_TOKEN
    Note over API: The revocation is observable — pre-reset refresh tokens no longer exchange
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

## Flow 4: Dogs — Owner adds, views, and updates a dog

Covers US-005, US-006, US-020.

```mermaid
sequenceDiagram
    participant owner
    participant API
    participant EventBus

    owner->>API: POST /v1/dogs<br/>{ name, breed, ageYears, medication, vetName, vetPhone, notes }
    API-->>owner: 201 { id, ... }
    API->>EventBus: publish dogwalking.dog.added

    owner->>API: GET /v1/dogs/{dogId}
    API-->>owner: 200 { id, name, breed, ageYears, medication, ... }

    owner->>API: PATCH /v1/dogs/{dogId}<br/>{ medication: "updated" }
    API-->>owner: 200 { id, ... }
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
    API-->>owner: 201 { id, status: "requested", priceCents: null }
    API->>EventBus: publish dogwalking.walk.requested

    walker->>API: PATCH /v1/walks/{walkId}/decision<br/>{ decision: "scheduled" }
    API-->>walker: 200 { id, status: "scheduled", priceCents }
    API->>EventBus: publish dogwalking.walk.scheduled
    Note over API: priceCents snapshotted from the matching rate-card entry at this transition

    Note over walker,owner: Either party may cancel a scheduled walk before it happens

    owner->>API: POST /v1/walks/{walkId}/cancel
    API-->>owner: 200 { id, status: "cancelled" }
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
    API-->>owner: 201 { id, status: "requested" }
    API->>EventBus: publish dogwalking.walk.requested

    walker->>API: PATCH /v1/walks/{walkId}/decision<br/>{ decision: "declined", reason: "already booked" }
    API-->>walker: 200 { id, status: "declined" }
    API->>EventBus: publish dogwalking.walk.declined

    owner->>API: GET /v1/walks?status=declined
    API-->>owner: 200 { data: [{id, status: "declined", declinedReason}] }
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
    API-->>walker: 201 { id, status: "scheduled", priceCents }
    API->>EventBus: publish dogwalking.walk.scheduled
    Note over API: Walker-created walks skip the `requested` state<br/>and record priceCents immediately
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
    API-->>walker: 201 { id, notes, photos: [...] }
    API->>EventBus: publish dogwalking.walkupdate.posted
    Note over walker: Live update during the walk

    walker->>API: POST /v1/walks/{walkId}/complete
    API-->>walker: 200 { id, status: "completed", completedAt }
    API->>EventBus: publish dogwalking.walk.completed
    Note over API: Walk transitions scheduled → completed

    walker->>API: POST /v1/walks/{walkId}/updates<br/>multipart: notes + photos[]
    API-->>walker: 201 { id, notes, photos: [...] }
    API->>EventBus: publish dogwalking.walkupdate.posted
    Note over walker: Post-hoc update — allowed in `completed` too

    owner->>API: GET /v1/walks/{walkId}/updates
    API-->>owner: 200 [{ id, notes, photos: [{id, contentType, ...}] }]

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

    walker->>API: PUT /v1/rate-card<br/>{ currency, entries: [{walkType, durationMinutes, priceCents}] }
    API-->>walker: 200 { id, currency, entries: [...] }
    API->>EventBus: publish dogwalking.ratecard.updated

    owner->>API: GET /v1/rate-card
    API-->>owner: 200 { id, currency, entries: [...] }
    Note over API: Owner sees only the rate card of their assigned walker
```

---

## Flow 10: Invoicing — Generate, view, mark paid

Covers US-014, US-015, US-016.

```mermaid
sequenceDiagram
    participant walker
    participant API
    participant EventBus
    participant owner

    walker->>API: POST /v1/invoices<br/>{ clientId, periodStart, periodEnd }
    API-->>walker: 201 { id, totalCents, lineItems: [...] }
    API->>EventBus: publish dogwalking.invoice.issued
    Note over API: Line-item prices copied from each walk's recorded priceCents<br/>(snapshotted at its scheduled transition)

    owner->>API: GET /v1/invoices?status=issued&from=2026-06-01&to=2026-06-30
    API-->>owner: 200 { data: [{id, totalCents, status: "issued"}], ... }

    walker->>API: POST /v1/invoices/{invoiceId}/mark-paid<br/>{ paidAt, paidVia: "bank transfer" }
    API-->>walker: 200 { id, status: "paid", paidAt, paidVia }
    API->>EventBus: publish dogwalking.invoice.paid

    owner->>API: GET /v1/invoices?status=paid
    API-->>owner: 200 { data: [{id, status: "paid"}], ... }
```

---

## Flow 11: Instance status — first-run detection (US-023)

Covers US-023.

```mermaid
sequenceDiagram
    participant anon as sign-in screen
    participant API

    anon->>API: GET /v1/instance (no auth)
    API-->>anon: 200 { walkerRegistered: false, walkerDisplayName: null }
    Note over anon: Fresh instance — offer "Set up this instance as the walker"

    Note over anon,API: ...walker registers (Flow 1)...

    anon->>API: GET /v1/instance (no auth)
    API-->>anon: 200 { walkerRegistered: true, walkerDisplayName: "Alison" }
    Note over anon: Hide first-run setup; show whose business this is
```

---

## Flow 12: Clients — Walker views a client and their dogs (US-024)

Covers US-024.

```mermaid
sequenceDiagram
    participant walker
    participant API

    walker->>API: GET /v1/clients/{clientId}
    API-->>walker: 200 { id, displayName, email, ... }
    Note over API: email is projected from the linked User —<br/>not stored on Client, absent from Client events

    walker->>API: GET /v1/dogs?ownerId={clientId}
    API-->>walker: 200 { data: [{id, name, ownerId}, ...], ... }
    Note over API: Unknown or cross-tenant ownerId → 404 (no existence oracle)
```

---

## Flow 13: Dogs — Profile photo gallery (US-025)

Covers US-025.

```mermaid
sequenceDiagram
    participant owner
    participant API
    participant EventBus
    participant walker

    owner->>API: POST /v1/dogs/{dogId}/photos (multipart, one photo)
    API-->>owner: 201 { id, dogId, contentType, sizeBytes }
    API->>EventBus: publish dogwalking.dogphoto.added
    Note over API: Max 5 per dog — sixth returns 409 PHOTO_LIMIT_EXCEEDED

    walker->>API: GET /v1/dogs/{dogId}/photos/{photoId}
    API-->>walker: 200 (image bytes, authenticated stream)

    walker->>API: DELETE /v1/dogs/{dogId}/photos/{photoId}
    API-->>walker: 204
    API->>EventBus: publish dogwalking.dogphoto.removed
    Note over API: Slot freed; storage quota reclaimed (NFR-DATA-003)
```
