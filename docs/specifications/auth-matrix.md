# Auth Matrix — Dog Walking

## Roles

| Role | Description | Traces to persona |
|------|-------------|-------------------|
| `walker` | Can manage clients, dogs, walks, rate card, invoices. Exactly one Walker per domain instance. | Solo Dog Walker (PRD §Target Users) |
| `owner` | Can request walks, manage own dogs, view own invoices and walk history. | Dog Owner (PRD §Target Users) |

## Authentication

All protected routes require a `Bearer` JWT in the `Authorization`
header. Unauthenticated requests to protected routes return `401`
with code `AUTHENTICATION_REQUIRED`.

Tokens are issued via `POST /v1/auth/register`, `POST
/v1/auth/login`, and `POST /v1/invites/{token}/accept`. Expired
access tokens return `401 TOKEN_EXPIRED`; callers exchange their
refresh token for a fresh pair via `POST /v1/auth/refresh` (US-021).
Refresh tokens are rotated on every use, live 30 days (NFR-SEC-001),
and are revoked by `POST /v1/auth/logout` and by password-reset
confirm. An expired, revoked, rotated, or never-existed refresh token
returns `401 INVALID_REFRESH_TOKEN` — the cases are deliberately
indistinguishable.

Invite acceptance (`POST /v1/invites/{token}/accept`) is public —
the single-use invite token is the authentication for that one call.
Same for password-reset request and confirm, and for token refresh
(the refresh token in the body is the credential).

The public auth endpoints (register, login, password-reset request /
confirm, invite accept, refresh) are rate-limited per NFR-SEC-004 and
return `429 RATE_LIMITED` beyond the threshold — invite accept and
refresh included, since single-use opaque tokens are brute-forceable.

`GET /v1/instance` (US-023) is the one public non-auth read: it takes
no credential and guards no secret, so it is rate-limited per source
IP at a looser threshold than the credential endpoints (see
NFR-SEC-004) — sign-in screens fetch it on every load.

## Auth Matrix

| Operation | Endpoint | Public | walker | owner |
|-----------|----------|--------|--------|-------|
| Instance status | `GET /v1/instance` | 🌐 | 🌐 | 🌐 |
| Walker self-register | `POST /v1/auth/register` | 🌐 | 🌐 | 🌐 |
| Log in | `POST /v1/auth/login` | 🌐 | 🌐 | 🌐 |
| Request password reset | `POST /v1/auth/password-reset/request` | 🌐 | 🌐 | 🌐 |
| Confirm password reset | `POST /v1/auth/password-reset/confirm` | 🌐 | 🌐 | 🌐 |
| Accept invite | `POST /v1/invites/{token}/accept` | 🌐 | 🌐 | 🌐 |
| Refresh session | `POST /v1/auth/refresh` | 🌐 | 🌐 | 🌐 |
| Log out | `POST /v1/auth/logout` | ❌ | ✅ | ✅ |
| Add client | `POST /v1/clients` | ❌ | ✅ | ❌ |
| List clients | `GET /v1/clients` | ❌ | ✅ | ❌ |
| View client | `GET /v1/clients/{clientId}` | ❌ | 🔒 own client | ❌ |
| Add dog | `POST /v1/dogs` | ❌ | 🔒 own client | 🔒 own |
| List dogs | `GET /v1/dogs` | ❌ | 🔒 own clients' | 🔒 own |
| View dog | `GET /v1/dogs/{dogId}` | ❌ | 🔒 own client | 🔒 own |
| Edit dog | `PATCH /v1/dogs/{dogId}` | ❌ | 🔒 own client | 🔒 own |
| Add dog photo | `POST /v1/dogs/{dogId}/photos` | ❌ | 🔒 own client | 🔒 own |
| Get dog photo | `GET /v1/dogs/{dogId}/photos/{photoId}` | ❌ | 🔒 own client | 🔒 own |
| Delete dog photo | `DELETE /v1/dogs/{dogId}/photos/{photoId}` | ❌ | 🔒 own client | 🔒 own |
| Schedule walk | `POST /v1/walks` | ❌ | 🔒 own client | 🔒 own dog |
| List walks | `GET /v1/walks` | ❌ | 🔒 own clients' | 🔒 own |
| Decide on walk request | `PATCH /v1/walks/{walkId}/decision` | ❌ | 🔒 assigned | ❌ |
| Cancel walk | `POST /v1/walks/{walkId}/cancel` | ❌ | 🔒 assigned, `scheduled` walks only (declining is the walker's route out of `requested`) | 🔒 own |
| Complete walk | `POST /v1/walks/{walkId}/complete` | ❌ | 🔒 assigned | ❌ |
| Post walk update | `POST /v1/walks/{walkId}/updates` | ❌ | 🔒 assigned | ❌ |
| List walk updates | `GET /v1/walks/{walkId}/updates` | ❌ | 🔒 assigned | 🔒 own walk |
| Get walk-update photo | `GET /v1/walk-updates/{updateId}/photos/{photoId}` | ❌ | 🔒 assigned | 🔒 own walk |
| Generate invoice | `POST /v1/invoices` | ❌ | ✅ | ❌ |
| List invoices | `GET /v1/invoices` | ❌ | ✅ | 🔒 own |
| Mark invoice paid | `POST /v1/invoices/{invoiceId}/mark-paid` | ❌ | ✅ | ❌ |
| Set rate card | `PUT /v1/rate-card` | ❌ | ✅ | ❌ |
| View rate card | `GET /v1/rate-card` | ❌ | ✅ | 🔒 own walker |

**Legend:**

- 🌐 Public — no auth required
- ✅ Allowed — any user holding this role may call the operation
- 🔒 own — Allowed only if the resource's ownership trace matches the
  caller (see Ownership Rule below for the exact comparisons)
- ❌ Forbidden

## Ownership Rule

The 🔒 marker resolves at request time as follows:

- **For a `walker` caller** on a resource that references a Client
  (Dog, Walk, Invoice, WalkUpdate): the Client's `invitedByWalkerId`
  must equal the caller's Walker `id`.
- **For an `owner` caller** on a resource that references a Client
  (Dog, Walk, Invoice, WalkUpdate): the Client's `userId` must equal
  the caller's User `id`.
- **For Walk-specific operations** (decision, cancel, complete,
  updates): the Walk's `walkerId` (for walker callers) or the Walk's
  Dog's `ownerId` → Client's `userId` (for owner callers) must match.
- **For rate-card operations**: `GET`/`PUT /v1/rate-card` is a
  singleton — it takes no walker id and always resolves to the
  instance's single Walker's card. Walkers own it outright; an owner
  may view it because being a client of this instance's walker is
  what admitted them (`GET` before any card exists returns `404
  RESOURCE_NOT_FOUND`).

### Failure semantics: 404 for invisible, 403 for not-permitted

When the ownership trace **fails** on an id-addressed resource, the
response is `404 RESOURCE_NOT_FOUND` — identical to the id not
existing. "Exists but isn't yours" must be indistinguishable from
"doesn't exist", or UUID probing becomes a resource-existence oracle
(Decision Log: TENANCY-404-FOR-BOTH). The same applies to
body-referenced ids (`ownerId`, `dogId`, `clientId`): unknown and
cross-tenant both return `404`.

`403 FORBIDDEN` is reserved for operations on a resource the caller
**can** see but may not act on — the *wrong role* case: an owner
completing their own walk, an owner posting a walk update, an owner
marking their own invoice paid, a walker cancelling a `requested`
walk (decline is the walker's path).

## Error Responses

The auth-matrix references these error codes; each is defined in
`error-catalogue.md`:

- `AUTHENTICATION_REQUIRED` — missing, malformed, or
  invalid-signature bearer token
- `TOKEN_EXPIRED` — bearer token's `exp` is past (signature valid)
- `INVALID_CREDENTIALS` — login failed (email or password wrong)
- `INVALID_REFRESH_TOKEN` — refresh token expired, revoked, rotated,
  or never existed (indistinguishable)
- `RATE_LIMITED` — public auth endpoint called beyond the NFR-SEC-004
  threshold
- `FORBIDDEN` — caller can see the resource but their role doesn't
  permit the operation
- `EMAIL_ALREADY_REGISTERED` — registration or invite acceptance to
  an already-known email
- `INVITE_EXPIRED` / `INVITE_ALREADY_USED` — invite-token failures
- `RESET_TOKEN_EXPIRED` / `RESET_TOKEN_ALREADY_USED` — reset-token
  failures
- `VALIDATION_ERROR` — request body / query failed validation
- `INVALID_WALK_TYPE` — walk creation references a `(walkType,
  durationMinutes)` not on the walker's current rate card
- `INVALID_PHOTO` — photo upload violates MIME / size constraints
- `WALK_NOT_PENDING` — decision on a walk not in `requested`
- `WALK_NOT_CANCELLABLE` — cancel on a walk already terminal
- `WALK_NOT_SCHEDULED` — complete on a walk not in `scheduled`
- `WALK_UPDATE_NOT_ALLOWED` — update post on a walk in `requested` /
  `declined` / `cancelled`
- `NO_BILLABLE_WALKS` — invoice generation with no completed walks
  in the period
- `INVOICE_NOT_ISSUED` — mark-paid on a non-`issued` invoice
- `WALKER_ALREADY_EXISTS` — second walker registration attempt
- `RESOURCE_NOT_FOUND` — the id doesn't exist **or** the ownership
  trace failed (deliberately indistinguishable; see Failure
  semantics above). Also covers never-existed invite / reset tokens.
