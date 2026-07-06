# Error Catalogue — Dog Walking

> Canonical error codes returned by the Dog Walking API. Every error
> code referenced in `contracts/openapi.yaml` responses or in
> `auth-matrix.md` appears here with its HTTP status, meaning, and
> the conditions that trigger it. Code implementations must use these
> codes exactly.

---

## Authentication errors (401)

### `AUTHENTICATION_REQUIRED`

**HTTP status:** 401 Unauthorized

**Meaning:** The request reached a protected route but did not
include a bearer token in the `Authorization` header.

**Triggered by:**
- Any authenticated route called with no `Authorization` header.
- An `Authorization` header that does not start with `Bearer `.
- A bearer token whose signature does not verify (tampered, signed
  with the wrong key, or structurally not a JWT) — the most common
  real-world 401.

**Response shape:** `Error` (`code`, `message`).

### `TOKEN_EXPIRED`

**HTTP status:** 401 Unauthorized

**Meaning:** The bearer token presented has a valid signature but its
`exp` claim is in the past. Distinguished from
`AUTHENTICATION_REQUIRED` so clients know a silent refresh will fix
it.

**Triggered by:**
- An access token used after its expiry (lifetime defined in `nfr.md`).

**Resolution path:** Exchange the refresh token via
`POST /v1/auth/refresh`; re-log in only if that also fails.

**Response shape:** `Error` (`code`, `message`).

### `INVALID_REFRESH_TOKEN`

**HTTP status:** 401 Unauthorized

**Meaning:** The refresh token presented cannot be exchanged. It is
expired, revoked (logout or password reset), already rotated, or
never existed — deliberately indistinguishable to prevent token
probing.

**Triggered by:**
- `POST /v1/auth/refresh` with any token that isn't the currently
  active refresh token for a live session.

**Resolution path:** Re-log in via `POST /v1/auth/login`.

**Response shape:** `Error` (`code`, `message`).

### `INVALID_CREDENTIALS`

**HTTP status:** 401 Unauthorized

**Meaning:** Login failed. Either the email is unknown OR the
password is wrong — indistinguishable on purpose to avoid leaking
which field was wrong (account enumeration).

**Triggered by:**
- `POST /v1/auth/login` with an unknown email.
- `POST /v1/auth/login` with a known email and the wrong password.

**Response shape:** `Error` (`code`, `message`).

---

## Authorization errors (403)

### `FORBIDDEN`

**HTTP status:** 403 Forbidden

**Meaning:** The caller is authenticated and can see the resource,
but their role doesn't permit this operation on it. Ownership-trace
failures are **not** 403 — they return `404 RESOURCE_NOT_FOUND` so
that "exists but isn't yours" is indistinguishable from "doesn't
exist" (Decision Log: TENANCY-404-FOR-BOTH).

**Triggered by:**
- An `owner` calling a `walker`-only operation (add client, generate
  invoice, mark paid, set rate card) or a walker-only action on a
  walk they can see (complete, post update, decide).
- A `walker` cancelling a walk still in `requested` (declining via
  the decision endpoint is the walker's route out of `requested`).

**Response shape:** `Error` (`code`, `message`).

---

## Not-found errors (404)

### `RESOURCE_NOT_FOUND`

**HTTP status:** 404 Not Found

**Meaning:** The requested resource is not visible to the caller —
either the id doesn't exist (Dog, Walk, Invoice, WalkUpdate, Photo,
etc.) or it exists but the caller's ownership trace doesn't reach it.
The two cases are deliberately identical (no existence oracle;
Decision Log: TENANCY-404-FOR-BOTH).

**Triggered by:**
- Any GET / PATCH / POST routed against a `{resourceId}` that has
  no matching row.
- Any GET / PATCH / POST routed against a `{resourceId}` owned by a
  different walker's instance or a different owner.
- A body-referenced id (`ownerId` on add-dog, `dogId` on
  schedule-walk, `clientId` on generate-invoice) that doesn't exist
  or isn't in the caller's tenancy.
- `POST /v1/invites/{token}/accept` or
  `POST /v1/auth/password-reset/confirm` with a token that never
  existed (as opposed to expired/used, which return 410).

**Resolution path:** Check the id; refresh the list endpoint to see
the current set.

**Response shape:** `Error` (`code`, `message`).

---

## Conflict errors (409)

### `EMAIL_ALREADY_REGISTERED`

**HTTP status:** 409 Conflict

**Meaning:** The email already corresponds to a registered User.

**Triggered by:**
- `POST /v1/auth/register` with an already-known email (walker
  self-registration).
- `POST /v1/clients` with an email already known to another User.
- `POST /v1/invites/{token}/accept` when, between invite issue and
  acceptance, the email got registered through a different path.

**Response shape:** `Error` (`code`, `message`).

### `WALKER_ALREADY_EXISTS`

**HTTP status:** 409 Conflict

**Meaning:** A walker is already registered for this domain
instance. Only one Walker exists per instance per non-goal #1 (no
multi-walker teams).

**Triggered by:**
- `POST /v1/auth/register` when a Walker record already exists
  (registration is walker-only — owners join via invite, so any
  second registration attempt hits this).

**Response shape:** `Error` (`code`, `message`).

### `WALK_NOT_PENDING`

**HTTP status:** 409 Conflict

**Meaning:** A decision (`scheduled` / `declined`) was issued
against a walk not in status `requested`.

**Triggered by:**
- `PATCH /v1/walks/{walkId}/decision` when the walk is in
  `scheduled`, `declined`, `cancelled`, or `completed`.

**Response shape:** `Error` (`code`, `message`).

### `WALK_NOT_CANCELLABLE`

**HTTP status:** 409 Conflict

**Meaning:** Cancel was issued against a walk that's already in a
terminal state.

**Triggered by:**
- `POST /v1/walks/{walkId}/cancel` when the walk is `completed`,
  `declined`, or `cancelled`.

**Response shape:** `Error` (`code`, `message`).

### `WALK_NOT_SCHEDULED`

**HTTP status:** 409 Conflict

**Meaning:** Complete was issued against a walk that isn't in
`scheduled`.

**Triggered by:**
- `POST /v1/walks/{walkId}/complete` when the walk is in any status
  other than `scheduled`.

**Response shape:** `Error` (`code`, `message`).

### `WALK_UPDATE_NOT_ALLOWED`

**HTTP status:** 409 Conflict

**Meaning:** A walk update was posted against a walk in a state that
doesn't accept updates.

**Triggered by:**
- `POST /v1/walks/{walkId}/updates` when the walk is in
  `requested`, `declined`, or `cancelled`. Updates are only allowed
  in `scheduled` (live updates during) and `completed` (post-hoc).

**Response shape:** `Error` (`code`, `message`).

### `INVOICE_NOT_ISSUED`

**HTTP status:** 409 Conflict

**Meaning:** Mark-paid was issued against an invoice that isn't in
`issued`.

**Triggered by:**
- `POST /v1/invoices/{invoiceId}/mark-paid` when the invoice is
  already `paid`.

**Response shape:** `Error` (`code`, `message`).

### `CURRENCY_IMMUTABLE`

**HTTP status:** 409 Conflict

**Meaning:** The rate card's currency is fixed once set (changing it
mid-history creates accounting ambiguity on invoices that span the
change — Decision Log: CURRENCY-CARD-LEVEL).

**Triggered by:**
- `PUT /v1/rate-card` whose `currency` differs from the currency
  already established on the walker's card.

**Resolution path:** Keep the established currency. A currency change
is a domain-migration event, not an API call.

**Response shape:** `Error` (`code`, `message`).

### `IDEMPOTENCY_KEY_CONFLICT`

**HTTP status:** 409 Conflict

**Meaning:** The client reused an `Idempotency-Key` on this
endpoint with a *different* request body. The server stored the
original `{key → request body → response}` triple and refuses to
honour the same key for a semantically different intent.

**Triggered by:**
- Any POST whose `Idempotency-Key` header matches an existing
  stored entry but whose request body has changed since the
  original call.

**Resolution:** Generate a fresh UUID for the new intent.

**Response shape:** `Error` (`code`, `message`).

---

## Rate-limiting errors (429)

### `RATE_LIMITED`

**HTTP status:** 429 Too Many Requests

**Meaning:** The caller exceeded the request-rate threshold on a
rate-limited endpoint (NFR-SEC-004). The response includes a
`Retry-After` header (seconds).

**Triggered by:**
- `POST /v1/auth/register`, `POST /v1/auth/login`,
  `POST /v1/auth/password-reset/request`,
  `POST /v1/auth/password-reset/confirm`,
  `POST /v1/auth/refresh`, or `POST /v1/invites/{token}/accept`
  called beyond the per-IP / per-account threshold. The token-taking
  endpoints are included because single-use opaque tokens are
  brute-forceable.

**Resolution path:** Wait for the `Retry-After` interval and retry.

**Response shape:** `Error` (`code`, `message`).

---

## Gone errors (410)

### `INVITE_EXPIRED`

**HTTP status:** 410 Gone

**Meaning:** The invite token's TTL has elapsed.

**Triggered by:**
- `POST /v1/invites/{token}/accept` with a token older than 24 hours
  (`createdAt + 1 day < now`).

**Resolution path:** The walker re-invites the client.

**Response shape:** `Error` (`code`, `message`).

### `INVITE_ALREADY_USED`

**HTTP status:** 410 Gone

**Meaning:** The invite token has already been redeemed.

**Triggered by:**
- `POST /v1/invites/{token}/accept` against a token whose status is
  `accepted`.

**Resolution path:** The recipient is already registered; log in or
reset password if they've forgotten it.

**Response shape:** `Error` (`code`, `message`).

### `RESET_TOKEN_EXPIRED`

**HTTP status:** 410 Gone

**Meaning:** The password-reset token's TTL has elapsed.

**Triggered by:**
- `POST /v1/auth/password-reset/confirm` with a token older than
  1 hour.

**Resolution path:** Request a fresh reset.

**Response shape:** `Error` (`code`, `message`).

### `RESET_TOKEN_ALREADY_USED`

**HTTP status:** 410 Gone

**Meaning:** The password-reset token has already been redeemed.

**Triggered by:**
- `POST /v1/auth/password-reset/confirm` against a token whose
  status is `used`.

**Resolution path:** Request a fresh reset (or, if the user's
already logged in elsewhere, simply re-log in).

**Response shape:** `Error` (`code`, `message`).

---

## Validation errors (400)

### `VALIDATION_ERROR`

**HTTP status:** 400 Bad Request

**Meaning:** The request body or query parameters failed validation
against the OpenAPI schema for the operation.

**Triggered by:**
- Missing required fields.
- Type mismatches.
- Constraint violations (string too short, integer out of range, ...).
- Walk creation with `startAt` in the past.
- Walk update with both `notes` empty AND zero photos.
- Rate-card PUT with a duplicate `(walkType, durationMinutes)` tuple
  or a non-positive `priceCents`.

**Response shape:** `ValidationError` (`code`, `message`, `details[]`).
The `details[]` array carries per-field error info.

### `INVALID_WALK_TYPE`

**HTTP status:** 400 Bad Request

**Meaning:** A walk-creation request referenced a `(walkType,
durationMinutes)` tuple that doesn't exist on the walker's current
rate card.

**Triggered by:**
- `POST /v1/walks` with a (type, duration) tuple the rate card
  doesn't price.

**Resolution path:** Either add the entry to the rate card, or pick
an existing tuple.

**Response shape:** `Error` (`code`, `message`).

### `INVALID_PHOTO`

**HTTP status:** 400 Bad Request

**Meaning:** A photo upload violated the content-type or size
constraints.

**Triggered by:**
- A `photo` part with `Content-Type` not in `image/jpeg`,
  `image/png`, `image/heic`.
- A `photo` part larger than 10 MB.
- More than 5 `photo` parts in a single update.

**Response shape:** `Error` (`code`, `message`).

### `NO_BILLABLE_WALKS`

**HTTP status:** 400 Bad Request

**Meaning:** Invoice generation was requested for a date range with
no completed walks for the client.

**Triggered by:**
- `POST /v1/invoices` where the count of `completed` walks for the
  client between `periodStart` and `periodEnd` (inclusive) is zero.

**Response shape:** `Error` (`code`, `message`).
