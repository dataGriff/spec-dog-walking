# Glossary — Dog Walking

> The ubiquitous language for the Dog Walking domain — a lexicon, not
> a reference manual. Every entity, role, domain event, enumeration,
> and key term has a one- or two-sentence entry here under the exact
> name the other documents use. Attribute-level detail lives in
> `domain-model.md`'s entity tables (the single attribute authority).
> Code, docs, and conversation must use these terms.

---

## Entities

### User

The authentication record for any human who logs in — either the
solo walker or one of their clients. Holds email, password hash, and
the role discriminator.

### Walker

The solo dog walker. Exactly one Walker exists per domain instance,
linked 1:1 to the User with role=`walker`. Owns the rate card, issues
invites, books and completes walks, marks invoices paid.

### Client

A dog owner from the walker's perspective. Created when the invite is
accepted; linked 1:1 to the User with role=`owner` and to the Walker
who invited them.

### Invite

A single-use registration token issued by the walker via the add-
client flow. Carries the prospective client's email and a 1-day TTL.

### Dog

A dog owned by a Client. Carries the operational details the walker
needs mid-walk: name, breed, age, medication, vet, free-text notes.

### Walk

A booked walk for a Dog. Status state machine: `requested → scheduled
→ completed`, with `declined` and `cancelled` as terminal paths.
Carries the walk type, duration, scheduled start time, and the
price snapshot taken at scheduling.

### WalkUpdate

A note (and optional photos) posted against a Walk while it's
`scheduled` or `completed`. Many updates may attach to one walk
(live, during, post-hoc).

### Photo

A single image attached to a WalkUpdate. Stored by the domain;
served via signed authenticated endpoints, not public URLs. Max 5
per WalkUpdate, max 10 MB, JPEG/PNG/HEIC.

### RateCard

The Walker's pricing table. Exactly one per Walker. Entries are
indexed by `(walkType, durationMinutes)`. Changes apply
prospectively.

### RateCardEntry

A single `(walkType, durationMinutes, priceCents)` row on a
RateCard.

### Invoice

A bill for a Client covering completed walks in a date range. Status
starts at `issued` and may move to `paid` (via mark-paid); an invoice
can remain `issued` indefinitely if never paid. Immutable after
issue except for the mark-paid transition.

### InvoiceLineItem

A single line on an Invoice, one per completed Walk in the billing
period. Snapshots `walkType`, `durationMinutes`, `priceCents` from
the rate card in force at the Walk's `scheduled` transition.

---

## Roles

### walker

The single Walker who runs the business (Alison in the PRD). Full
control over their client roster, bookings, rate card, and invoices.
Maps to the "Alison the walker" persona.

### owner

A dog owner (client of the walker; Clancy in the PRD). Manages their
own dogs, requests and cancels walks, views updates, rate card, and
invoices — always scoped to their own records. Maps to the "Clancy
the owner" persona.

---

## Domain events

### UserRegistered

Published on `dogwalking.user.registered` whenever a User record is
created — walker self-registration or client invite acceptance.
Payload is the full published User state.

### WalkerRegistered

Published on `dogwalking.walker.registered` when the solo walker
self-registers. Payload is the full Walker profile.

### InviteCreated

Published on `dogwalking.invite.created` when the walker adds a
client and an invite is queued. Payload is the full published Invite
state (token excluded as `[secret]`).

### InviteAccepted

Published on `dogwalking.invite.accepted` when a recipient accepts in
time; the invite transitions `pending → accepted`.

### InviteExpired

Published on `dogwalking.invite.expired` when an accept attempt lands
after `expiresAt` and the invite lazily transitions `pending →
expired`. Removal-shaped payload (id + timestamps).

### ClientRegistered

Published on `dogwalking.client.registered` when invite acceptance
creates the Client record. Carries `inviteId` for lineage back to
the invite.

### DogAdded

Published on `dogwalking.dog.added` when an owner adds a dog.
Payload is the full Dog state.

### DogUpdated

Published on `dogwalking.dog.updated` when a dog's details change.
Payload is the full Dog state post-change.

### WalkRequested

Published on `dogwalking.walk.requested` when an owner requests a
walk (`priceCents` still null).

### WalkScheduled

Published on `dogwalking.walk.scheduled` when a walk enters
`scheduled` — walker-created directly or via the decision endpoint.
Carries the freshly snapshotted `priceCents`.

### WalkDeclined

Published on `dogwalking.walk.declined` when the walker declines a
requested walk; carries `declinedReason`.

### WalkCancelled

Published on `dogwalking.walk.cancelled` when a walk is cancelled —
owner withdrawal from `requested`, or either party from `scheduled`.

### WalkCompleted

Published on `dogwalking.walk.completed` when the walker completes a
scheduled walk; carries `completedAt`.

### WalkUpdatePosted

Published on `dogwalking.walkupdate.posted` when the walker posts a
note/photos against a walk. Aggregate payload includes the `photos`
collection.

### RateCardUpdated

Published on `dogwalking.ratecard.updated` on every rate-card PUT.
Aggregate payload includes the full `entries` collection.

### InvoiceIssued

Published on `dogwalking.invoice.issued` when an invoice is
generated. Aggregate payload includes the full `lineItems`
collection.

### InvoicePaid

Published on `dogwalking.invoice.paid` when the walker marks an
invoice paid; carries `paidAt`, `paidVia`, and `tipCents`.

---

## Enumerations

### Role

Classifies a User as `walker` or `owner`. Closed — a third role is a
domain redesign, not a version bump. Authoritative values in the
domain model's Enumerations section.

### WalkStatus

The Walk lifecycle states (`requested` / `scheduled` / `declined` /
`cancelled` / `completed`). Closed; transitions governed by the Walk
Status Lifecycle table in the domain model.

### InvoiceStatus

The Invoice lifecycle states (`issued` / `paid`). Closed.

### InviteStatus

The Invite lifecycle states (`pending` / `accepted` / `expired`).
Closed.

### PhotoContentType

The permitted photo MIME types (`image/jpeg` / `image/png` /
`image/heic`). Closed — other media is a domain redesign.

### Breed

The dog-breed classification. **Open** enumeration: the openapi
schema carries the authoritative full list (UK Kennel Club
recognised breeds plus `mixed` and `unknown` fallbacks); the domain
model lists a representative subset. Additions are a minor version
bump.

---

## Supporting auth records

### PasswordResetToken

A single-use token used to reset a forgotten password. 1-hour TTL.
Confirming a reset revokes all of the User's refresh tokens. Not a
domain entity — excluded from events and the data contract by design.

### RefreshToken

The long-lived (30-day) session credential issued alongside every
access token; rotated on every refresh, revoked by logout and
password reset. Not a domain entity — excluded from events and the
data contract by design.

---

## Other terms

### price snapshot

The rule that a Walk records `priceCents` from the matching
rate-card entry at the moment it enters `scheduled`, and is never
repriced by later rate-card changes. Invoice line items copy this
snapshotted value.

### billing period

The inclusive `periodStart`–`periodEnd` date range an Invoice
covers. Each completed walk in the period becomes one line item; a
walk appears on at most one issued invoice.

### access token

A short-lived JWT (15 minutes, NFR-SEC-001) carried in the
`Authorization: Bearer <token>` header on every authenticated
request.
