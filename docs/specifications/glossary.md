# Glossary — Dog Walking

> The ubiquitous language for the Dog Walking domain. Every entity
> name and every attribute name used in `domain-model.md` (and the
> later contracts files) appears here exactly as it is used. Code,
> docs, and conversation must use these terms.

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

A dog owner from the walker's perspective. Created when the walker
invites someone; linked 1:1 to the User with role=`owner` and to the
Walker who invited them.

### Invite

A single-use registration token issued by the walker via the add-
client flow. Carries the prospective client's email and a 1-day TTL.

### PasswordResetToken

A single-use token used to reset a forgotten password. 1-hour TTL.
Confirming a reset revokes all of the User's existing refresh tokens.

### Dog

A dog owned by a Client. Carries the operational details the walker
needs mid-walk: name, breed, age, medication, vet, free-text notes.

### Walk

A booked walk for a Dog. Status state machine: `requested → scheduled
→ completed`, with `declined` and `cancelled` as terminal paths.
Carries the walk type, duration, and scheduled start time.

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

## User attributes

### id

UUID. Unique identifier.

### email

String (email format). Login email; unique and case-folded across
all users.

### passwordHash

String. Adaptive password-hash output. Never returned in API
responses, never logged.

### role

Enum. One of `walker` or `owner`. Set at registration; immutable
afterwards.

### createdAt

ISO 8601 timestamp. Registration time.

### updatedAt

ISO 8601 timestamp. Last update time.

---

## Walker attributes

### id

UUID. Unique identifier.

### userId

UUID. FK to the User with role=`walker`. Immutable.

### displayName

String. Name shown on invoices and client invites.

### createdAt

ISO 8601 timestamp.

### updatedAt

ISO 8601 timestamp.

---

## Client attributes

### id

UUID. Unique identifier.

### userId

UUID. FK to the User with role=`owner`. Immutable.

### invitedByWalkerId

UUID. FK to the Walker who issued the invite. Immutable; clients
never move between walkers.

### displayName

String. Name the walker uses to refer to this client.

### createdAt

ISO 8601 timestamp.

### updatedAt

ISO 8601 timestamp.

---

## Invite attributes

### id

UUID. Unique identifier.

### walkerId

UUID. FK to the Walker issuing the invite.

### email

String (email format). The prospective client's email.

### token

String (opaque URL-safe). Single-use registration token.

### status

Enum. One of `pending` / `accepted` / `expired`.

### expiresAt

ISO 8601 timestamp. 24 hours after `createdAt`.

### createdAt

ISO 8601 timestamp.

### updatedAt

ISO 8601 timestamp.

---

## PasswordResetToken attributes

### id

UUID. Unique identifier.

### userId

UUID. FK to the User being reset.

### token

String (opaque URL-safe). Single-use reset token.

### status

Enum. One of `pending` / `used` / `expired`.

### expiresAt

ISO 8601 timestamp. 1 hour after `createdAt`.

### createdAt

ISO 8601 timestamp.

### updatedAt

ISO 8601 timestamp.

---

## Dog attributes

### id

UUID. Unique identifier.

### ownerId

UUID. FK to the Client who owns this dog. Immutable.

### name

String. Dog's name.

### breed

Enum (`Breed`, open) or `null`. The dog's breed, from the UK Kennel
Club recognised-breeds list plus `mixed` and `unknown` fallbacks.
Open enumeration: additions to the openapi list are a minor version
bump.

### ageYears

Integer or `null`. Age in whole years.

### medication

String or `null`. Free-text medication notes.

### vetName

String or `null`. Vet practice name.

### vetPhone

String or `null`. Vet contact number.

### notes

String or `null`. Free-text quirks / handling notes.

### createdAt

ISO 8601 timestamp.

### updatedAt

ISO 8601 timestamp.

---

## Walk attributes

### id

UUID. Unique identifier.

### dogId

UUID. FK to the Dog being walked.

### walkerId

UUID. FK to the Walker assigned to the walk.

### walkType

String. Matches a `walkType` on the walker's current rate card.

### durationMinutes

Integer. Matches a `durationMinutes` on the matching rate-card entry.

### startAt

ISO 8601 timestamp. Scheduled start time; must be in the future at
creation.

### requesterRole

Enum. One of `walker` or `owner` — who created the walk.

### notes

String or `null`. Free-text booking notes.

### priceCents

Integer or `null`. The walk's recorded price in the rate card's
currency, minor units — snapshotted from the matching rate-card entry
when the walk enters `scheduled`, and never repriced by later
rate-card changes. `null` while `requested`, or when the walk left
the lifecycle before ever being scheduled.

### status

Enum. One of `requested` / `scheduled` / `declined` / `cancelled` /
`completed`. See domain-model Walk Status lifecycle.

### declinedReason

String or `null`. Walker's reason when status=`declined`.

### cancelledByRole

Enum or `null`. One of `walker` or `owner` — set when
status=`cancelled`.

### completedAt

ISO 8601 timestamp or `null`. Set when status=`completed`.

### createdAt

ISO 8601 timestamp.

### updatedAt

ISO 8601 timestamp.

---

## WalkUpdate attributes

### id

UUID. Unique identifier.

### walkId

UUID. FK to the Walk this update belongs to.

### notes

String or `null`. Free-text note. At least one of `notes` or an
attached Photo must be present.

### createdAt

ISO 8601 timestamp.

### updatedAt

ISO 8601 timestamp.

---

## Photo attributes

### id

UUID. Unique identifier.

### walkUpdateId

UUID. FK to the WalkUpdate this photo belongs to.

### contentType

String. MIME type — one of `image/jpeg` / `image/png` / `image/heic`.

### sizeBytes

Integer. Stored size in bytes. Maximum 10 MB.

### capturedAt

ISO 8601 timestamp or `null`. Capture time from EXIF, if present.

### createdAt

ISO 8601 timestamp.

### updatedAt

ISO 8601 timestamp.

---

## RateCard attributes

### id

UUID. Unique identifier.

### walkerId

UUID. FK to the Walker who owns this rate card.

### currency

String (ISO 4217). e.g. `GBP`, `USD`. Set at creation; immutable.

### createdAt

ISO 8601 timestamp.

### updatedAt

ISO 8601 timestamp.

---

## RateCardEntry attributes

### id

UUID. Unique identifier.

### rateCardId

UUID. FK to parent RateCard.

### walkType

String. e.g. `solo`, `group`.

### durationMinutes

Integer. e.g. 30, 45, 60.

### priceCents

Integer. Positive; price in the rate card's currency, minor units.

### createdAt

ISO 8601 timestamp.

### updatedAt

ISO 8601 timestamp.

---

## Invoice attributes

### id

UUID. Unique identifier.

### walkerId

UUID. FK to the Walker issuing the invoice.

### clientId

UUID. FK to the Client being billed.

### periodStart

ISO 8601 date (no time). Inclusive start of billing period.

### periodEnd

ISO 8601 date (no time). Inclusive end of billing period.

### currency

String (ISO 4217). Copied from the RateCard at issue.

### totalCents

Integer. Sum of line-item `priceCents`. Computed at issue; never
recomputed.

### status

Enum. One of `issued` / `paid`.

### paidAt

ISO 8601 timestamp or `null`. Set when status=`paid`.

### paidVia

String or `null`. Free-text payment channel (e.g. "bank transfer",
"cash"). Set with status=`paid`.

### tipCents

Integer, non-negative. Tip amount in the invoice's currency, minor
units. Defaults to `0` at issue; can be set to a non-negative integer
at mark-paid (US-019). Recorded on the InvoicePaid event payload.

### createdAt

ISO 8601 timestamp. Issue time.

### updatedAt

ISO 8601 timestamp.

---

## InvoiceLineItem attributes

### id

UUID. Unique identifier.

### invoiceId

UUID. FK to parent Invoice.

### walkId

UUID. FK to the completed Walk this line bills. A walk appears on at
most one issued invoice (uniqueness on `walkId`).

### walkType

String. Copied from the Walk at issue.

### durationMinutes

Integer. Copied from the Walk at issue.

### priceCents

Integer. Price from the rate-card entry in force at the Walk's
`scheduled` transition.

### createdAt

ISO 8601 timestamp.

### updatedAt

ISO 8601 timestamp.
