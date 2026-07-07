# Product Requirements Document — Dog Walking

## Problem Statement

Solo dog walkers run their business across five disconnected places:
WhatsApp threads for bookings, a wall calendar for scheduling, fridge-
board sticky notes for daily reminders, a manual invoicing process,
and a paper folder for dog and owner details. Every booking or change
forces the walker to re-enter the same information across all five —
and when they need to look up a dog's medication or an owner's contact
mid-walk, they're flipping through paper. The cost is lookup time,
missed reminders that turn into missed walks, and invoicing errors
that turn into late or wrong payments.

The **Dog Walking** domain is the single place a solo walker can
manage clients, dogs, scheduled walks, and invoices — so that
information lives in one place and a booking made once flows through
every downstream concern without re-entry. The single authoritative
schedule replaces the fridge board as the place both sides check
what's happening; proactive reminder delivery is deferred (see
Non-Goals).

## Target Users / Personas

### Solo Dog Walker — Alison

Alison runs her own one-person dog-walking business. She onboards new
dogs, takes bookings from owners, plans her week, walks the dogs,
keeps owners updated, and invoices. Today she does all of that across
WhatsApp, a wall calendar, fridge-board reminders, a separate
invoicing tool, and a paper folder of dog and owner details.

- **Goal:** Manage every step of her dog-walking business from one
  place — onboarding dogs, taking and responding to bookings,
  planning and completing walks, keeping owners updated, and getting
  invoices and payments out without re-entering data anywhere.
- **Frustration:** A single one-off booking request — say a regular
  client asking for an extra walk on Thursday — fans out into
  four-or-five manual steps: jot it in notes, add it to Google
  Calendar, remember to enter it in the invoicing tool, remember the
  walk doesn't fit the usual pattern, and keep the WhatsApp thread in
  sync with the client. Any step missed and the walk gets dropped,
  double-booked, or unbilled.

### Dog Owner — Clancy

Clancy owns a dog and books walks with Alison. She lives the
client-side of every interaction: requesting walks, cancelling them
when plans change, keeping her dog's details (medication, vet, quirks)
up to date with Alison, paying invoices, and receiving updates
after each walk.

- **Goal:** Book walks, cancel them, see the schedule and status of
  upcoming and past walks, keep her dog's details current, pay
  invoices, and receive updates from each walk so she knows it
  happened and how it went.
- **Frustration:** No single view of her dog's upcoming and past
  walks — when she wants to know "did I book a walk for Thursday?"
  she has to scroll back through WhatsApp threads to find the
  request and Alison's confirmation. Same on the money side: she has
  no running view of what's been billed or what's still owed, so
  invoices get missed and balances drift.

## Goals

1. Give Alison a single place to manage clients, dogs, walks, and
   invoices so a piece of information entered once flows through
   every downstream concern without re-entry.
2. Give Clancy a single view of her dog's upcoming and completed
   walks plus a clear running balance of what's been billed and paid.
3. Replace the WhatsApp / calendar / fridge-board / paper-folder
   workflow with one source of truth that both Alison and her clients
   see consistently — so neither side has to scroll a message thread
   to reconstruct what was agreed.

## Non-Goals

1. **Multi-walker teams or franchises.** v1 is one walker per domain
   instance. Coordinating shifts across multiple walkers, walker-to-
   walker handoffs, and franchise-level reporting are out of scope.
2. **Live GPS tracking of walks in progress.** The domain captures
   walk updates posted during or after the walk (notes and optional photos), not
   a moving dot on a map. Real-time location belongs in a different
   product.
3. **Payment processing.** The domain handles invoices and records
   what's been paid; the actual money movement (Stripe, bank
   transfer, cash receipt) sits in the client's own payment tooling.
4. **A marketplace for finding walkers.** Alison's clients are
   already her clients; the domain doesn't onboard strangers,
   surface walkers to new owners, or rank/review walkers.
5. **Proactive walk reminders / notifications.** v1 replaces the
   fridge board with a single authoritative schedule both sides can
   check at any time; pushing reminders out ahead of walks (email,
   push, SMS) is a notification subsystem deferred to a later
   release (Decision Log: REMINDERS-DESCOPED-TO-NON-GOAL).

## User Stories

### Auth / Onboarding

#### US-000: Register as a walker

**As a** solo dog walker,
**I want to** create my account with email, password, and display name,
**So that** I have a domain instance of my own to run my business in.

**Acceptance Criteria:**
- POST /v1/auth/register creates the walker account with
  `{email, password, displayName}` and returns access + refresh tokens
- Registration is walker-only; dog owners join by invitation (US-001,
  US-002), never by self-registration
- Returns 409 with `EMAIL_ALREADY_REGISTERED` if the email is already
  in use
- Returns 400 with `VALIDATION_ERROR` if the password is shorter than
  8 characters
- A `WalkerRegistered` event is published

*Scenarios: [US-000](acceptance-scenarios.md#us-000-register-as-a-walker)*

#### US-001: Add a new client

**As a** solo dog walker,
**I want to** add a new client with their name and email,
**So that** they exist as a record I can later attach dogs and bookings to.

**Acceptance Criteria:**
- POST /v1/clients issues an invite with name + email and queues an
  invite email containing a single-use registration link; an
  `InviteCreated` event is published
- The Client record itself is created when the invite is accepted
  (US-002), so every client on the books has a registered user behind
  it (Decision Log: CLIENT-CREATED-AT-ACCEPTANCE)
- The invite is associated with the authenticated walker
- Returns 409 with `EMAIL_ALREADY_REGISTERED` if the email is already in use

*Scenarios: [US-001](acceptance-scenarios.md#us-001-add-a-new-client)*

#### US-002: Accept invite and set password

**As a** new client,
**I want to** follow my invite link and choose a password,
**So that** I can log in to manage my dog and bookings.

**Acceptance Criteria:**
- POST /v1/invites/{token}/accept accepts the registration with a chosen password
- Returns 410 with `INVITE_EXPIRED` if the token is older than 1 day;
  an invite that passes its expiry is marked `expired` and an
  `InviteExpired` event is published
- Returns 410 with `INVITE_ALREADY_USED` if the token was already redeemed
- Returns 404 with `RESOURCE_NOT_FOUND` if the token never existed
- On success the Client record is created and linked to the walker who
  invited them, access + refresh tokens are returned, and
  `InviteAccepted` and `ClientRegistered` events are published (both
  carrying the invite id so the lineage is joinable from the stream)

*Scenarios: [US-002](acceptance-scenarios.md#us-002-accept-invite-and-set-password)*

#### US-003: Log in

**As a** registered dog owner or solo dog walker,
**I want to** log in with my email and password,
**So that** I can get a fresh access token without re-registering.

**Acceptance Criteria:**
- POST /v1/auth/login returns 200 with tokens on valid credentials
- Returns 401 with `INVALID_CREDENTIALS` on wrong email or password
  (indistinguishable, to avoid leaking which was wrong)

*Scenarios: [US-003](acceptance-scenarios.md#us-003-log-in)*

#### US-004: Reset forgotten password

**As a** registered dog owner or solo dog walker,
**I want to** reset my password if I've forgotten it,
**So that** I can regain access without contacting Alison.

**Acceptance Criteria:**
- POST /v1/auth/password-reset/request accepts an email and queues a reset
  email (always returns 204, never reveals whether the email is registered,
  to avoid account enumeration)
- POST /v1/auth/password-reset/confirm accepts a token + new password
- Returns 410 with `RESET_TOKEN_EXPIRED` if the token is older than 1 hour
- Returns 410 with `RESET_TOKEN_ALREADY_USED` if the token was already redeemed
- Returns 404 with `RESOURCE_NOT_FOUND` if the token never existed
- On success the password is updated and all existing refresh tokens for that
  user are revoked — observable because a subsequent POST /v1/auth/refresh
  with a pre-reset refresh token returns 401 (forces re-login on other
  devices)

*Scenarios: [US-004](acceptance-scenarios.md#us-004-reset-forgotten-password)*

#### US-021: Stay logged in without re-entering credentials

**As a** registered dog owner or solo dog walker,
**I want to** exchange my refresh token for a fresh access token,
**So that** my session continues across the short access-token
lifetime (15 minutes, NFR-SEC-001) without logging in again on my
phone mid-walk.

**Acceptance Criteria:**
- POST /v1/auth/refresh accepts `{refreshToken}` and returns a fresh
  access + refresh token pair (the presented refresh token is rotated
  and can't be reused)
- Returns 401 with `INVALID_REFRESH_TOKEN` if the token is expired,
  revoked, already rotated, or never existed (indistinguishable, to
  avoid token probing)

*Scenarios: [US-021](acceptance-scenarios.md#us-021-stay-logged-in-without-re-entering-credentials)*

#### US-022: Log out

**As a** registered dog owner or solo dog walker,
**I want to** log out and have my refresh token revoked,
**So that** a device I've stopped using can't silently keep my session
alive.

**Acceptance Criteria:**
- POST /v1/auth/logout revokes the presented refresh token and returns
  204
- Subsequent POST /v1/auth/refresh with the revoked token returns 401
  with `INVALID_REFRESH_TOKEN`

*Scenarios: [US-022](acceptance-scenarios.md#us-022-log-out)*

#### US-023: See whether this instance already has its walker

**As a** solo dog walker (or anyone landing on the sign-in screen),
**I want** the app to know whether this instance's walker is already
registered,
**So that** first-run walker setup is only offered on a genuinely fresh
instance and clients can see whose business they are signing in to.

**Acceptance Criteria:**
- GET /v1/instance is public (no authentication) and returns
  `{walkerRegistered, walkerDisplayName}`
- Before any walker registers it returns
  `{walkerRegistered: false, walkerDisplayName: null}`
- After registration it returns
  `{walkerRegistered: true, walkerDisplayName}` with the walker's
  display name
- Deliberately public: the walker's display name is the instance's
  storefront and already reaches invitees out of band; no other data
  is exposed
- Rate-limited per source IP, looser than the credential endpoints
  (see the Security NFRs); read-only — no domain event

*Scenarios: [US-023](acceptance-scenarios.md#us-023-see-whether-this-instance-already-has-its-walker)*

### Clients

#### US-024: View a client and their dogs

**As a** solo dog walker,
**I want to** open one client and see their contact email and their dogs,
**So that** Alison can reach Clancy and see which dogs she walks for him
without digging through walk history.

**Acceptance Criteria:**
- GET /v1/clients/{clientId} returns the client, including `email` —
  the login email the walker originally invited, projected from the
  linked user account (not stored on the Client record and absent from
  Client events; consumers join on `userId`)
- GET /v1/clients list entries carry the same projected `email`
- Returns 404 with `RESOURCE_NOT_FOUND` if the id doesn't exist or the
  client belongs to a different instance (not-yours indistinguishable
  from not-there)
- Owner callers receive 403 with `FORBIDDEN` (the client book belongs
  to the walker)
- GET /v1/dogs?ownerId={clientId} filters the dog list to that client's
  dogs; an unknown or cross-instance `ownerId` returns 404 with
  `RESOURCE_NOT_FOUND` (same tenancy rule as US-005)

*Scenarios: [US-024](acceptance-scenarios.md#us-024-view-a-client-and-their-dogs)*

### Dogs

#### US-005: Add a dog

**As a** dog owner or the solo dog walker,
**I want to** add a dog with name, breed, age, medication, vet contact, and
free-text quirks/notes,
**So that** the dog exists as a record both sides can read and update.

**Acceptance Criteria:**
- POST /v1/dogs creates a dog; a `DogAdded` event is published
- If the requester is an owner, the dog is associated with them automatically
- If the requester is the walker, the request must include `ownerId` (a
  client they invited); returns 404 with `RESOURCE_NOT_FOUND` if the
  named owner doesn't exist or isn't one of their clients (no
  existence oracle — Decision Log: TENANCY-404-FOR-BOTH)
- Required: name. Optional: breed, age, medication, vet contact, notes
- Breed values come from the UK Kennel Club breed list, modelled as an
  open enumeration — unlisted breeds are added as a minor contract
  change (Decision Log: BREED-UK-KENNEL-CLUB-OPEN-ENUM)
- Returns 400 with `VALIDATION_ERROR` if `name` is missing

*Scenarios: [US-005](acceptance-scenarios.md#us-005-add-a-dog)*

#### US-006: Update dog details

**As a** dog owner or the solo dog walker who manages this owner,
**I want to** edit any of the dog's fields,
**So that** medication / vet / quirks stay current without WhatsApp ping-pong.

**Acceptance Criteria:**
- PATCH /v1/dogs/{dogId} edits the named fields
- Returns 404 with `RESOURCE_NOT_FOUND` if the dog doesn't exist or the
  requester is neither the owner nor the walker assigned to the owner
  (not-yours is indistinguishable from not-there)
- A `DogUpdated` event is published

*Scenarios: [US-006](acceptance-scenarios.md#us-006-update-dog-details)*

#### US-020: View a single dog

**As a** dog owner or the solo dog walker who manages this owner,
**I want to** view the full details of a single dog (medication, vet,
notes, owner),
**So that** I can confirm the dog's current state — mid-walk when
Alison needs to check medication, or pre-booking when Clancy wants
to verify she's updated her dog's details since last week.

**Acceptance Criteria:**
- GET /v1/dogs/{dogId} returns the full dog record
- Returns 404 with `RESOURCE_NOT_FOUND` if the id does not exist or
  the requester is neither the owner nor the walker assigned to the
  owner (same ownership rule as US-006; not-yours is
  indistinguishable from not-there)

*Scenarios: [US-020](acceptance-scenarios.md#us-020-view-a-single-dog)*

#### US-025: Keep a photo gallery on a dog's profile

**As a** dog owner or the solo dog walker who manages this owner,
**I want to** add and remove photos on the dog's profile,
**So that** the dog is recognisable at a glance — for Alison meeting a
new dog, and for Clancy keeping the profile current.

**Acceptance Criteria:**
- POST /v1/dogs/{dogId}/photos adds one photo per request
  (`multipart/form-data`); the response carries the photo's metadata
  and a `DogPhotoAdded` event is published
- A dog's gallery holds at most 5 photos; adding a sixth returns 409
  with `PHOTO_LIMIT_EXCEEDED` (delete one to free a slot)
- Photos are JPEG/PNG/HEIC, max 10MB each; anything else returns 400
  with `INVALID_PHOTO`; stored bytes count toward the instance photo
  storage cap (see the Data NFRs) and the quota is reclaimed on delete
- Photo bytes are served only via the authenticated
  GET /v1/dogs/{dogId}/photos/{photoId} — never a public URL
- DELETE /v1/dogs/{dogId}/photos/{photoId} removes the photo and
  publishes a `DogPhotoRemoved` event
- Ownership follows US-006: the dog's owner and their walker may add,
  view, and delete; anyone else gets 404 with `RESOURCE_NOT_FOUND`
  (not-yours indistinguishable from not-there)
- Dog responses carry the gallery's metadata as `photos`

*Scenarios: [US-025](acceptance-scenarios.md#us-025-keep-a-photo-gallery-on-a-dogs-profile)*

### Bookings

#### US-007: Schedule a walk

**As a** dog owner or the solo dog walker,
**I want to** create a walk for a dog at a specific date, start time, duration,
walk-type, and optional notes,
**So that** it appears on the schedule.

**Acceptance Criteria:**
- POST /v1/walks creates the walk with `{dogId, startAt, durationMinutes,
  walkType, notes?}`
- If the requester is the owner → walk is in status `requested` (waiting
  for Alison)
- If the requester is the walker → walk is in status `scheduled` directly
- Returns 400 with `VALIDATION_ERROR` if `startAt` is in the past
- Returns 404 with `RESOURCE_NOT_FOUND` if `dogId` doesn't exist or
  the dog isn't visible to the requester (walker booking for a
  non-client's dog, owner booking for someone else's dog)
- Returns 400 with `INVALID_WALK_TYPE` if `walkType` / `durationMinutes`
  doesn't match an entry on the walker's rate card
- A walk entering `scheduled` records the rate-card price for its
  (walkType, durationMinutes) at that moment; later rate-card changes
  don't reprice it (Decision Log: WALK-PRICE-SNAPSHOT-AT-SCHEDULING)
- A `WalkRequested` (owner path) or `WalkScheduled` (walker path) event
  is published

*Scenarios: [US-007](acceptance-scenarios.md#us-007-schedule-a-walk)*

#### US-008: Decide on a walk request

**As a** solo dog walker,
**I want to** schedule or decline a walk request from a client,
**So that** the client knows the walk is confirmed or that they need to
find another option.

**Acceptance Criteria:**
- PATCH /v1/walks/{walkId}/decision accepts `{decision: scheduled |
  declined, reason?: string}`
- Returns 404 with `RESOURCE_NOT_FOUND` if the walk doesn't exist or
  isn't for one of my clients
- Returns 409 with `WALK_NOT_PENDING` if the walk is not in status
  `requested`
- On `scheduled`: walk moves to `scheduled`, `WalkScheduled` event published
- On `declined`: walk moves to `declined`, `WalkDeclined` event published

*Scenarios: [US-008](acceptance-scenarios.md#us-008-decide-on-a-walk-request)*

#### US-009: Cancel a walk

**As a** dog owner or the solo dog walker,
**I want to** cancel a walk before it happens,
**So that** the schedule reflects reality.

**Acceptance Criteria:**
- POST /v1/walks/{walkId}/cancel cancels the walk
- Returns 404 with `RESOURCE_NOT_FOUND` if the walk doesn't exist or
  isn't visible to the requester (owner of the dog or the assigned
  walker)
- Returns 409 with `WALK_NOT_CANCELLABLE` if the walk is already
  `completed`, `declined`, or `cancelled`
- The walk moves to status `cancelled`; the cancelling party is recorded
- A `WalkCancelled` event is published

*Scenarios: [US-009](acceptance-scenarios.md#us-009-cancel-a-walk)*

#### US-010: List walks

**As a** dog owner or the solo dog walker,
**I want to** list walks filtered by status and date range,
**So that** I have one view of past, scheduled, and cancelled walks.

**Acceptance Criteria:**
- GET /v1/walks?status=&from=&to= returns a paginated list
- Owners see only their own dogs' walks; walkers see all walks for their
  clients
- Page size is capped at 50

### Walks

*Scenarios: [US-010](acceptance-scenarios.md#us-010-list-walks)*

#### US-011: Complete a walk

**As a** solo dog walker,
**I want to** mark a walk as completed,
**So that** the schedule reflects which walks have happened.

**Acceptance Criteria:**
- POST /v1/walks/{walkId}/complete
- Returns 404 with `RESOURCE_NOT_FOUND` if the walk doesn't exist or
  isn't visible to the requester
- Returns 403 with `FORBIDDEN` if the walk is visible but the
  requester isn't the assigned walker (an owner can't complete their
  own walk)
- Returns 409 with `WALK_NOT_SCHEDULED` if not in status `scheduled`
- Walk moves to `completed`; completion timestamp recorded
- A `WalkCompleted` event is published

*Scenarios: [US-011](acceptance-scenarios.md#us-011-complete-a-walk)*

#### US-012: Post a walk update

**As a** solo dog walker,
**I want to** post one or more updates to a walk with free-text notes
and/or attached photos,
**So that** the client can see how the walk is going or how it went.

**Acceptance Criteria:**
- POST /v1/walks/{walkId}/updates accepts `multipart/form-data` with
  `notes?: string` and zero or more `photo` file parts
- At least one of `notes` or photos must be present (returns 400 with
  `VALIDATION_ERROR` if both empty)
- Photos: max 5 per update, max 10MB each, JPEG/PNG/HEIC only (returns
  400 with `INVALID_PHOTO` otherwise)
- Returns 404 with `RESOURCE_NOT_FOUND` if the walk doesn't exist or
  isn't visible to the requester; 403 with `FORBIDDEN` if it's visible
  but the requester isn't the assigned walker (owners can't post
  updates)
- Returns 409 with `WALK_UPDATE_NOT_ALLOWED` if walk is in `requested`,
  `declined`, or `cancelled`
- A `WalkUpdatePosted` event is published; payload includes the update id
  and photo count

*Scenarios: [US-012](acceptance-scenarios.md#us-012-post-a-walk-update)*

#### US-013: View walk updates

**As a** dog owner or the assigned solo dog walker,
**I want to** view all updates posted against a walk including the
photos in chronological order,
**So that** I have the full timeline of how the walk went.

**Acceptance Criteria:**
- GET /v1/walks/{walkId}/updates returns updates in posted-at order, each
  with notes + an array of photo metadata (id, content-type, size,
  captured-at)
- GET /v1/walk-updates/{updateId}/photos/{photoId} returns the photo bytes
- Both endpoints return 404 with `RESOURCE_NOT_FOUND` if the resource
  doesn't exist or the requester is neither the owner nor the assigned
  walker

### Invoicing

*Scenarios: [US-013](acceptance-scenarios.md#us-013-view-walk-updates)*

#### US-014: Generate an invoice

**As a** solo dog walker,
**I want to** generate an invoice for a client covering a date range of
completed walks,
**So that** I can bill them in one go (e.g. monthly).

**Acceptance Criteria:**
- POST /v1/invoices accepts `{clientId, periodStart, periodEnd}`
- The invoice contains line items for every `completed` walk in the
  period for that client's dogs, priced at the rate recorded on each
  walk when it entered `scheduled` — not the rate card at invoicing
  time (Decision Log: WALK-PRICE-SNAPSHOT-AT-SCHEDULING)
- Returns 400 with `NO_BILLABLE_WALKS` if no completed walks fall in the
  period
- Returns 404 with `RESOURCE_NOT_FOUND` if `clientId` doesn't exist or
  isn't one of the walker's clients
- Invoice is created in status `issued`; an `InvoiceIssued` event is
  published

*Scenarios: [US-014](acceptance-scenarios.md#us-014-generate-an-invoice)*

#### US-015: List invoices

**As a** dog owner or the solo dog walker,
**I want to** list invoices with status and balance owed,
**So that** both sides have a running view of money.

**Acceptance Criteria:**
- GET /v1/invoices?status=&from=&to= returns a paginated list
- Walkers see all of their issued invoices; owners see only invoices
  addressed to them

*Scenarios: [US-015](acceptance-scenarios.md#us-015-list-invoices)*

#### US-016: Record an invoice as paid

**As a** solo dog walker,
**I want to** mark an invoice as paid when the client pays (via any
channel — bank transfer, cash, etc.),
**So that** the balance reflects reality. Payment processing itself is
out of scope (see Non-Goals); this is bookkeeping only.

**Acceptance Criteria:**
- POST /v1/invoices/{invoiceId}/mark-paid accepts `{paidAt: ISO-8601,
  paidVia: string}`
- Returns 403 with `FORBIDDEN` if the requester is not the assigned
  walker (owners cannot mark their own invoices paid)
- Returns 409 with `INVOICE_NOT_ISSUED` if not in status `issued`
- Invoice moves to `paid`; `InvoicePaid` event is published

### Pricing

*Scenarios: [US-016](acceptance-scenarios.md#us-016-record-an-invoice-as-paid)*

#### US-017: Set my rate card

**As a** solo dog walker,
**I want to** set prices per walk-type (e.g. solo walk, group walk) and
duration (e.g. 30 / 45 / 60 min) as a structured table,
**So that** invoices auto-compute the right amount per completed walk.

**Acceptance Criteria:**
- PUT /v1/rate-card replaces the walker's full rate card with
  `{currency, entries: [{walkType, durationMinutes, priceCents}]}` —
  currency is card-level, not per-entry (Decision Log:
  CURRENCY-CARD-LEVEL)
- Returns 400 with `VALIDATION_ERROR` if any entry has a zero or
  negative price, or if there's a duplicate (walkType, durationMinutes)
  tuple
- Returns 409 with `CURRENCY_IMMUTABLE` if the request's currency
  differs from the card's established currency (currency is fixed once
  set)
- The rate card is per-walker; changes apply prospectively to walks
  entering `scheduled` after the change (already-scheduled walks keep
  their recorded price)
- A `RateCardUpdated` event is published

*Scenarios: [US-017](acceptance-scenarios.md#us-017-set-my-rate-card)*

#### US-018: View the rate card

**As a** solo dog walker or a dog owner who is one of their clients,
**I want to** view the walker's current rate card,
**So that** Alison knows what she'll charge and Clancy knows what to
expect before booking.

**Acceptance Criteria:**
- GET /v1/rate-card returns the walker's current rate card
- Returns 404 with `RESOURCE_NOT_FOUND` if no rate card has ever been
  set (empty state; see auth-matrix singleton rule)

*Scenarios: [US-018](acceptance-scenarios.md#us-018-view-the-rate-card)*

> **Removed — US-019 (tip at mark-paid).** A tip is the client's
> declaration, not the walker's data entry, and v1 has no owner-side
> payment surface, so the walker recording a tip put one party's money
> in the other party's hands. Invoices are total-only in v1. The story
> number is retired, not reused.

## Constraints

<!-- Technical, legal, or business constraints. -->

1. **UK-only.** The service operates in the United Kingdom: UK GDPR
   governs personal data (see the Privacy & data rights NFRs), prices
   are GBP, and the product ships in English only.
2. **One walker per domain instance.** The data model, auth matrix,
   and rate card all assume a single walker; there is no
   walker-discovery, team, or franchise capability (see Non-Goals 1
   and 4).
3. **Walker-initiated, invite-only client onboarding.** Owners cannot
   self-register; they join only via a walker's invite (US-001/US-002).
   Self-registration exists solely for walkers (US-000).
4. **No payment processing.** Invoices are bookkeeping records;
   settlement happens off-platform and is recorded after the fact
   (US-016, Non-Goal 3).
5. **API-first.** The domain is exposed as a versioned REST API plus
   published domain events; mobile-first clients consume it online
   (no offline mode in v1).

## Success Metrics

1. **Walk-booking re-entry count drops to 1.** Today Alison enters a
   single booking into approximately 5 places (WhatsApp confirmation,
   wall calendar, fridge-board reminder, invoicing tool, paper folder
   cross-reference); with the domain, the same booking exists once and
   is visible everywhere it's needed. *Measured by:* user interview at
   30 days — Alison reports 1 place to update when a booking changes,
   not 5.
2. **Invoice issuance time drops by at least 50%.** Today Alison spends
   approximately 30 minutes per client per month reconstructing
   invoices from her notes; with auto-pricing from the rate card and
   completed walks, target is 15 minutes or less per client per month.
   *Measured by:* time-tracked sample over one billing cycle compared
   against Alison's pre-domain baseline.
