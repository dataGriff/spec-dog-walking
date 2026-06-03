# Domain Model — Dog Walking

## Overview

The **Dog Walking** domain models a solo dog walker's business and
the clients they serve. There is exactly one **Walker** per domain
instance (multi-walker is a non-goal per the PRD). Walkers invite
**Clients**; clients own **Dogs**; walks are booked against dogs,
posted-against with notes and photos, and rolled up into invoices
once a billing period closes. Two roles cover every interaction:
`walker` (Alison) and `owner` (Clancy and other clients).

---

## Entities

### User

The authentication record for any human who logs in — either the
solo walker or one of their clients. Holds the identity primitives
(email, password hash) and the role discriminator that determines
which profile entity (Walker or Client) is attached.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | UUID | Yes | Unique identifier |
| `email` | string (email) | Yes | Login email (unique across all users) |
| `passwordHash` | string | Yes | [secret] Adaptive password-hash output. Never returned in API responses, never published to events. |
| `role` | enum:Role | Yes | Set at registration; immutable. |
| `createdAt` | ISO 8601 | Yes | Registration timestamp |
| `updatedAt` | ISO 8601 | Yes | Last update timestamp (refresh-token rotation, etc.) |

**Business Rules:**
- Email is unique across all users; case-folded on store and lookup.
- `passwordHash` is the adaptive hash output (algorithm chosen by NFR);
  the plaintext is never logged or returned.
- `role` is set at registration (via invite for owners, by self-
  registration for the walker) and cannot be changed via the API.

---

### Walker

The profile of the solo dog walker. Exactly one Walker exists per
domain instance, linked 1:1 to the User with role=`walker`.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | UUID | Yes | Unique identifier |
| `userId` | UUID | Yes | FK to User (where role=`walker`) |
| `displayName` | string | Yes | Name shown on invoices and client invites |
| `createdAt` | ISO 8601 | Yes | Created at first walker registration |
| `updatedAt` | ISO 8601 | Yes | Last update timestamp |

**Business Rules:**
- Exactly one Walker per domain instance (enforced at registration —
  a second `role=walker` registration is rejected).
- `userId` is immutable once set.
- **No dedicated Walker API surface in v1.** The single-walker
  constraint means `GET /v1/walkers` / `GET /v1/walkers/{walkerId}`
  would always return the same one record; `POST /v1/walkers` is
  covered by walker self-registration via `POST /v1/auth/register`.
  Walker data reaches owners indirectly through `GET /v1/rate-card`
  and the assigned walker on Walk responses. Multi-walker support
  would introduce these endpoints.

---

### Client

The profile of a dog owner from the walker's perspective. Linked 1:1
to a User with role=`owner` and 1:1 to the Walker who invited them.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | UUID | Yes | Unique identifier |
| `userId` | UUID | Yes | FK to User (where role=`owner`) |
| `invitedByWalkerId` | UUID | Yes | FK to Walker who issued the invite |
| `displayName` | string | Yes | Name the walker uses to refer to this client |
| `createdAt` | ISO 8601 | Yes | When the Client record was created (at invite acceptance) |
| `updatedAt` | ISO 8601 | Yes | Last update timestamp |

**Business Rules:**
- A client always traces back to the walker who invited them via
  `invitedByWalkerId`. Cross-walker visibility is forbidden.
- `userId` and `invitedByWalkerId` are immutable.

---

### Invite

A single-use token issued when the walker adds a new client. The
invite carries the prospective client's email and a 1-day TTL.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | UUID | Yes | Unique identifier |
| `walkerId` | UUID | Yes | FK to Walker issuing the invite |
| `email` | string (email) | Yes | Prospective client's email |
| `token` | string (opaque) | Yes | [secret] URL-safe single-use token. Never published to events. |
| `status` | enum:InviteStatus | Yes | Lifecycle state of the invite |
| `expiresAt` | ISO 8601 | Yes | Timestamp at which the invite auto-transitions to `expired` |
| `createdAt` | ISO 8601 | Yes | When the invite was queued |
| `updatedAt` | ISO 8601 | Yes | Last update timestamp |

**Business Rules:**
- TTL is 24 hours from `createdAt`. After that the status auto-moves
  to `expired` (lazily evaluated on accept attempts).
- `token` is single-use: accepting one moves status to `accepted` and
  any subsequent accept attempt with the same token returns
  `INVITE_ALREADY_USED`.
- Email must not already correspond to a registered User at the
  moment of acceptance.

---

### PasswordResetToken

A single-use token issued by the password-reset request endpoint
with a 1-hour TTL.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | UUID | Yes | Unique identifier |
| `userId` | UUID | Yes | FK to User the reset targets |
| `token` | string (opaque) | Yes | [secret] URL-safe single-use token. Never published to events. |
| `status` | enum:PasswordResetTokenStatus | Yes | Lifecycle state of the token |
| `expiresAt` | ISO 8601 | Yes | Timestamp at which the token auto-transitions to `expired` |
| `createdAt` | ISO 8601 | Yes | When the reset was requested |
| `updatedAt` | ISO 8601 | Yes | Last update timestamp |

**Business Rules:**
- TTL is 1 hour from `createdAt`. Lazily evaluated on confirm.
- Single-use: confirming once moves status to `used`.
- On successful confirm, every refresh token for the target User is
  revoked (forces re-login on other devices).

---

### Dog

A dog owned by a Client. Carries the operational details the walker
needs mid-walk (medication, vet, quirks). Editable by either the
owner or the walker assigned to that owner.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | UUID | Yes | Unique identifier |
| `ownerId` | UUID | Yes | FK to Client who owns this dog |
| `name` | string | Yes | Dog's name |
| `breed` | enum:Breed \| null | No | Breed (use `mixed` when not in the closed list, `unknown` if the owner doesn't know) |
| `ageYears` | integer \| null | No | Age in whole years |
| `medication` | string \| null | No | Free-text medication notes |
| `vetName` | string \| null | No | Vet practice name |
| `vetPhone` | string \| null | No | Vet contact number |
| `notes` | string \| null | No | Free-text quirks / handling notes |
| `createdAt` | ISO 8601 | Yes | Creation timestamp |
| `updatedAt` | ISO 8601 | Yes | Last update timestamp |

**Business Rules:**
- `ownerId` is immutable; transfers are out of scope for v1.
- Either the owner or the walker assigned to that owner may edit any
  field.

---

### Walk

A single scheduled or completed walk for a Dog. The status state
machine captures the booking lifecycle (request → schedule →
complete) plus the failure / cancellation paths.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | UUID | Yes | Unique identifier |
| `dogId` | UUID | Yes | FK to Dog being walked |
| `walkerId` | UUID | Yes | FK to Walker assigned to the walk |
| `walkType` | string | Yes | Matches a `walkType` on the walker's rate card |
| `durationMinutes` | integer | Yes | Matches `durationMinutes` on the rate-card entry |
| `startAt` | ISO 8601 | Yes | Scheduled start time |
| `requesterRole` | enum:Role | Yes | Who created the walk |
| `notes` | string \| null | No | Free-text booking notes |
| `status` | enum:WalkStatus | Yes | Lifecycle state of the walk |
| `declinedReason` | string \| null | No | Walker's reason when status=`declined` |
| `cancelledByRole` | enum:Role \| null | No | Set when status=`cancelled` |
| `completedAt` | ISO 8601 \| null | No | Set when status=`completed` |
| `createdAt` | ISO 8601 | Yes | When the walk was first recorded |
| `updatedAt` | ISO 8601 | Yes | Last status change |

**Business Rules:**
- `(walkType, durationMinutes)` must match an entry on the walker's
  current rate card at creation; otherwise `INVALID_WALK_TYPE`.
- `startAt` must be in the future at creation (`VALIDATION_ERROR`
  otherwise).
- Walker-created walks start in `scheduled`; owner-created walks
  start in `requested`.
- The walker assigned to the walk is the only party who can move
  status to `scheduled` / `declined` / `completed`.
- Either party can move status to `cancelled` while the walk is in
  `requested` or `scheduled`.

---

### WalkUpdate

A note (and optional photos) posted against a walk by the walker.
Many updates may be posted against one walk over its lifetime
(during, after, or both).

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | UUID | Yes | Unique identifier |
| `walkId` | UUID | Yes | FK to Walk this update belongs to |
| `notes` | string \| null | No | Free-text note |
| `createdAt` | ISO 8601 | Yes | When the update was posted |
| `updatedAt` | ISO 8601 | Yes | Last update timestamp |

**Business Rules:**
- Either `notes` is non-empty OR at least one Photo is attached
  (`VALIDATION_ERROR` if both empty).
- Updates may be posted while the walk is in status `scheduled` or
  `completed`; never in `requested`, `declined`, `cancelled`.

---

### Photo

A single image attached to a WalkUpdate. Stored by the domain
(direct upload, signed retrieval) rather than as a public URL.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | UUID | Yes | Unique identifier |
| `walkUpdateId` | UUID | Yes | FK to WalkUpdate this photo belongs to |
| `contentType` | enum:PhotoContentType | Yes | MIME type of the stored bytes |
| `sizeBytes` | integer | Yes | Stored size in bytes |
| `capturedAt` | ISO 8601 \| null | No | Capture time from EXIF, if present |
| `createdAt` | ISO 8601 | Yes | When the photo was uploaded |
| `updatedAt` | ISO 8601 | Yes | Last update timestamp |

**Business Rules:**
- Maximum 5 photos per WalkUpdate.
- Maximum size 10 MB per photo.
- `contentType` must be one of the three permitted MIMEs;
  `INVALID_PHOTO` otherwise.
- Bytes are served via a signed authenticated endpoint, never as a
  public URL.

---

### RateCard

The pricing table for the Walker. Exactly one RateCard exists per
Walker; changes apply prospectively (existing walks keep their
recorded price).

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | UUID | Yes | Unique identifier |
| `walkerId` | UUID | Yes | FK to Walker who owns this rate card |
| `currency` | string (ISO 4217) | Yes | e.g. `GBP`, `USD` |
| `createdAt` | ISO 8601 | Yes | Creation timestamp |
| `updatedAt` | ISO 8601 | Yes | Last update timestamp |

**Business Rules:**
- One RateCard per Walker.
- Currency is set at creation and cannot be changed (creates accounting
  ambiguity on invoices that span the change).

---

### RateCardEntry

A single (walkType, durationMinutes, priceCents) row on a RateCard.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | UUID | Yes | Unique identifier |
| `rateCardId` | UUID | Yes | FK to parent RateCard |
| `walkType` | string | Yes | e.g. `solo`, `group` |
| `durationMinutes` | integer | Yes | e.g. 30, 45, 60 |
| `priceCents` | integer | Yes | Positive integer; price in the rate card's currency, minor units |
| `createdAt` | ISO 8601 | Yes | Creation timestamp |
| `updatedAt` | ISO 8601 | Yes | Last update timestamp |

**Business Rules:**
- `(walkType, durationMinutes)` is unique per RateCard (`VALIDATION_ERROR`
  on duplicate at PUT).
- `priceCents` must be strictly positive.

---

### Invoice

A bill for a Client covering completed walks in a date range, with
line items pricing each walk at the rate-card amount in force when
that walk was scheduled.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | UUID | Yes | Unique identifier |
| `walkerId` | UUID | Yes | FK to Walker issuing the invoice |
| `clientId` | UUID | Yes | FK to Client being billed |
| `periodStart` | ISO 8601 (date) | Yes | Inclusive start of billing period |
| `periodEnd` | ISO 8601 (date) | Yes | Inclusive end of billing period |
| `currency` | string (ISO 4217) | Yes | Copied from the RateCard at issue |
| `totalCents` | integer | Yes | Sum of line-item priceCents |
| `status` | enum:InvoiceStatus | Yes | Lifecycle state of the invoice |
| `paidAt` | ISO 8601 \| null | No | Set when status=`paid` |
| `paidVia` | string \| null | No | Free-text payment channel (set with status=`paid`) |
| `tipCents` | integer | Yes | Tip amount in the invoice's currency, minor units. Defaults to `0` at issue; can be set to a non-negative integer at mark-paid (US-019). |
| `createdAt` | ISO 8601 | Yes | Issue timestamp |
| `updatedAt` | ISO 8601 | Yes | Last update timestamp |

**Business Rules:**
- Immutable after issue: no PATCH endpoint on invoices.
- `mark-paid` is the only state transition; it must include `paidAt`
  and `paidVia`, and MAY include `tipCents` (defaults to `0`,
  non-negative, US-019).
- Only the assigned walker can mark an invoice paid (owners cannot).
- `totalCents` is computed at issue and never recomputed.

---

### InvoiceLineItem

One line on an Invoice, one per completed Walk in the billing period.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | UUID | Yes | Unique identifier |
| `invoiceId` | UUID | Yes | FK to parent Invoice |
| `walkId` | UUID | Yes | FK to the completed Walk this line bills |
| `walkType` | string | Yes | Copied from the Walk at issue |
| `durationMinutes` | integer | Yes | Copied from the Walk at issue |
| `priceCents` | integer | Yes | Price from the rate-card entry in force at the Walk's `scheduled` transition |
| `createdAt` | ISO 8601 | Yes | Creation timestamp |
| `updatedAt` | ISO 8601 | Yes | Last update timestamp |

**Business Rules:**
- A walk can appear on at most one issued invoice (uniqueness on
  `walkId`).
- `priceCents` is captured from the rate-card entry that was in force
  at the Walk's `scheduled` transition (matching the attribute
  description above). The InvoiceLineItem row is created when the
  invoice is generated, but the *value* it carries is the
  scheduled-time price, not the issue-time price. Later rate-card
  edits do not alter historical line items.

---

## Relationships

```
User                ──── has-one  ────  Walker
Walker              ──── belongs-to ──  User

User                ──── has-one  ────  Client
Client              ──── belongs-to ──  User

Walker              ──── has-many ────  Client
Client              ──── belongs-to ──  Walker

Walker              ──── has-many ────  Invite
Invite              ──── belongs-to ──  Walker

User                ──── has-many ────  PasswordResetToken
PasswordResetToken  ──── belongs-to ──  User

Client              ──── has-many ────  Dog
Dog                 ──── belongs-to ──  Client

Dog                 ──── has-many ────  Walk
Walk                ──── belongs-to ──  Dog

Walker              ──── has-many ────  Walk
Walk                ──── assigned-to ── Walker

Walk                ──── has-many ────  WalkUpdate
WalkUpdate          ──── belongs-to ──  Walk

WalkUpdate          ──── has-many ────  Photo
Photo               ──── belongs-to ──  WalkUpdate

Walker              ──── has-one  ────  RateCard
RateCard            ──── belongs-to ──  Walker

RateCard            ──── has-many ────  RateCardEntry
RateCardEntry       ──── belongs-to ──  RateCard

Walker              ──── has-many ────  Invoice
Invoice             ──── issued-by ───  Walker

Client              ──── has-many ──── Invoice
Invoice             ──── addressed-to ──── Client

Invoice             ──── has-many ────  InvoiceLineItem
InvoiceLineItem     ──── belongs-to ──  Invoice

InvoiceLineItem     ──── references ──  Walk
Walk                ──── billed-by ───  InvoiceLineItem
```

---

## Domain Events

| Event | Trigger | Channel |
|-------|---------|---------|
| `InviteCreated` | POST /v1/clients → 201 | `dogwalking.invite.created` |
| `ClientRegistered` | POST /v1/invites/{token}/accept → 200 | `dogwalking.client.registered` |
| `DogAdded` | POST /v1/dogs → 201 | `dogwalking.dog.added` |
| `DogUpdated` | PATCH /v1/dogs/{dogId} → 200 | `dogwalking.dog.updated` |
| `WalkRequested` | POST /v1/walks → 201 by owner | `dogwalking.walk.requested` |
| `WalkScheduled` | POST /v1/walks by walker OR PATCH /v1/walks/{id}/decision=scheduled | `dogwalking.walk.scheduled` |
| `WalkDeclined` | PATCH /v1/walks/{id}/decision=declined | `dogwalking.walk.declined` |
| `WalkCancelled` | POST /v1/walks/{id}/cancel | `dogwalking.walk.cancelled` |
| `WalkCompleted` | POST /v1/walks/{id}/complete | `dogwalking.walk.completed` |
| `WalkUpdatePosted` | POST /v1/walks/{id}/updates → 201 | `dogwalking.walkupdate.posted` |
| `RateCardUpdated` | PUT /v1/rate-card → 200 | `dogwalking.ratecard.updated` |
| `InvoiceIssued` | POST /v1/invoices → 201 | `dogwalking.invoice.issued` |
| `InvoicePaid` | POST /v1/invoices/{id}/mark-paid → 200 | `dogwalking.invoice.paid` |

---

## Status Lifecycle

### Walk Status

```
requested ──── (walker accepts) ────── scheduled ──── (walker completes) ──── completed
   │                                       │
   │── (walker declines) ── declined       │── (either cancels) ── cancelled
   │
   └── (owner withdraws) ── cancelled
```

| From | To | Trigger |
|------|----|---------|
| `requested` | `scheduled` | PATCH /v1/walks/{id}/decision=scheduled (walker accepts) |
| `requested` | `declined` | PATCH /v1/walks/{id}/decision=declined (walker declines) |
| `requested` | `cancelled` | POST /v1/walks/{id}/cancel (owner withdraws) |
| `scheduled` | `cancelled` | POST /v1/walks/{id}/cancel (either party) |
| `scheduled` | `completed` | POST /v1/walks/{id}/complete (walker) |

### Invoice Status

```
issued ──── (walker marks paid) ──── paid
```

| From | To | Trigger |
|------|----|---------|
| `issued` | `paid` | POST /v1/invoices/{id}/mark-paid (walker only) |

### Invite Status

```
pending ──── (recipient accepts) ──── accepted
   │
   └── (TTL elapses) ── expired
```

| From | To | Trigger |
|------|----|---------|
| `pending` | `accepted` | POST /v1/invites/{token}/accept (valid + unexpired) |
| `pending` | `expired` | Lazy: any accept attempt after `expiresAt` |

### PasswordResetToken Status

```
pending ──── (user confirms) ──── used
   │
   └── (TTL elapses) ── expired
```

| From | To | Trigger |
|------|----|---------|
| `pending` | `used` | POST /v1/auth/password-reset/confirm (valid + unexpired) |
| `pending` | `expired` | Lazy: any confirm attempt after `expiresAt` |

## Enumerations

<!--
Each enum named here must appear in contracts/openapi.yaml as
components.schemas.<Name> with matching values (enforced by
ENUM-VALUES-CONSISTENT). Cross-contract declarations (asyncapi,
datacontract) must also match if present.

Headings carry an `(open)` marker for expandable enums (where the
contract is the authoritative full list and may exceed the model's
representative subset). Default is closed: model values must equal
contract values exactly. See SUITE-DESIGN §5 and the domain-modeling
SKILL.
-->

### Role

The two roles in the dog-walking system. Closed by design — adding
a third role is a domain-redesign event, not a minor version bump.

| Value | Notes |
|---|---|
| `walker` | The single Walker who runs the business |
| `owner` | Dog owners (clients of the walker) |

### WalkStatus

Lifecycle states of a Walk. Closed; transitions are governed by
the Walk Status Lifecycle table above.

| Value | Notes |
|---|---|
| `requested` | Owner-initiated, awaiting walker decision |
| `scheduled` | Confirmed for the proposed time |
| `declined` | Walker declined; terminal |
| `cancelled` | Cancelled by owner or walker; terminal |
| `completed` | Walk completed by walker; terminal |

### InvoiceStatus

Lifecycle states of an Invoice. Closed.

| Value | Notes |
|---|---|
| `issued` | Invoice raised; awaiting payment |
| `paid` | Walker has marked the invoice as paid |

### InviteStatus

Lifecycle states of a client Invite. Closed.

| Value | Notes |
|---|---|
| `pending` | Issued; awaiting acceptance |
| `accepted` | Client accepted; one-shot use complete |
| `expired` | Past `expiresAt` without acceptance |

### PasswordResetTokenStatus

Lifecycle states of a password-reset token. Closed.

| Value | Notes |
|---|---|
| `pending` | Issued; awaiting confirm |
| `used` | Successfully consumed |
| `expired` | Past `expiresAt` without use |

### PhotoContentType

Permitted MIME types for walk-update photos. Closed; expanding to
video or other media is a domain-redesign event (storage costs,
moderation, etc.).

| Value | Notes |
|---|---|
| `image/jpeg` | |
| `image/png` | |
| `image/heic` | |

### Breed (open)

A representative subset of dog breeds the walker workforce
encounters most often, plus `mixed` and `unknown` as fallbacks so
the field is always answerable without forcing the owner into a
free-text workaround.

This enum is **open**: the openapi schema carries the authoritative
full list (the UK Kennel Club's recognised-breeds list — ~220
breeds — plus the two fallbacks). The model below lists the most
common 10 plus the fallbacks as a human-readable reference;
`ENUM-VALUES-CONSISTENT` verifies the model values are a subset of
the openapi schema. Adding a breed to the openapi list is a minor
version bump (per NFR-COMPAT-001); no model change required unless
the new breed deserves to surface in the canonical examples below.

| Value | Notes |
|---|---|
| `labrador-retriever` | The most common breed on the workforce's books |
| `poodle-standard` | Standard variant; KC also lists miniature + toy poodle |
| `golden-retriever` | |
| `german-shepherd` | |
| `bulldog` | English bulldog (KC's "Bulldog" entry) |
| `beagle` | |
| `dachshund-smooth-haired` | KC also lists wire-haired, long-haired, and miniature variants |
| `cocker-spaniel` | English cocker (KC also has the American cocker) |
| `border-collie` | |
| `staffordshire-bull-terrier` | |
| `mixed` | Crossbreed or pedigree not represented in the full list |
| `unknown` | Owner doesn't know |

## Aggregates

<!--
Aggregate roots that own a child collection. Events on the root
entity MUST carry the full child collection in the same payload —
both in the AsyncAPI message and the matching datacontract record —
per SUITE-DESIGN §4.5 and enforced by EVENT-PAYLOAD-COVERS-ENTITY-STATE.
-->

| Root | Child | Collection |
|------|-------|------------|
| `RateCard` | `RateCardEntry` | `entries` |
| `Invoice` | `InvoiceLineItem` | `lineItems` |
| `WalkUpdate` | `Photo` | `photos` |
