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

Tokens are issued via `POST /v1/auth/login`. Expired access tokens
return `401 TOKEN_EXPIRED`; callers obtain a fresh access token by
re-logging in (a dedicated refresh endpoint is out of scope for v1;
the longer-lived refresh tokens issued at login feed implementations'
own refresh strategy if needed).

Invite acceptance (`POST /v1/invites/{token}/accept`) is public —
the single-use invite token is the authentication for that one call.
Same for password-reset request and confirm.

## Auth Matrix

| Operation | Endpoint | Public | walker | owner |
|-----------|----------|--------|--------|-------|
| Walker self-register | `POST /v1/auth/register` | 🌐 | 🌐 | 🌐 |
| Log in | `POST /v1/auth/login` | 🌐 | 🌐 | 🌐 |
| Request password reset | `POST /v1/auth/password-reset/request` | 🌐 | 🌐 | 🌐 |
| Confirm password reset | `POST /v1/auth/password-reset/confirm` | 🌐 | 🌐 | 🌐 |
| Accept invite | `POST /v1/invites/{token}/accept` | 🌐 | 🌐 | 🌐 |
| Add client | `POST /v1/clients` | ❌ | ✅ | ❌ |
| List clients | `GET /v1/clients` | ❌ | ✅ | ❌ |
| Add dog | `POST /v1/dogs` | ❌ | 🔒 own client | 🔒 own |
| List dogs | `GET /v1/dogs` | ❌ | 🔒 own clients' | 🔒 own |
| View dog | `GET /v1/dogs/{dogId}` | ❌ | 🔒 own client | 🔒 own |
| Edit dog | `PATCH /v1/dogs/{dogId}` | ❌ | 🔒 own client | 🔒 own |
| Schedule walk | `POST /v1/walks` | ❌ | 🔒 own client | 🔒 own dog |
| List walks | `GET /v1/walks` | ❌ | 🔒 own clients' | 🔒 own |
| Decide on walk request | `PATCH /v1/walks/{walkId}/decision` | ❌ | 🔒 assigned | ❌ |
| Cancel walk | `POST /v1/walks/{walkId}/cancel` | ❌ | 🔒 assigned | 🔒 own |
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
  must equal the caller's Walker `id`. Cross-walker access returns
  `403 FORBIDDEN`.
- **For an `owner` caller** on a resource that references a Client
  (Dog, Walk, Invoice, WalkUpdate): the Client's `userId` must equal
  the caller's User `id`. Cross-owner access returns `403 FORBIDDEN`.
- **For Walk-specific operations** (decision, cancel, complete,
  updates): the Walk's `walkerId` (for walker callers) or the Walk's
  Dog's `ownerId` → Client's `userId` (for owner callers) must match.
- **For rate-card view by an `owner`**: the requested Walker must
  have invited the caller's Client (i.e. the caller is one of the
  walker's clients). Otherwise `403 FORBIDDEN`.

The same `FORBIDDEN` code is used for both *wrong role* and *not the
owner* failures, deliberately — the response does not reveal which
check failed.

## Error Responses

The auth-matrix references these error codes; each is defined in
`error-catalogue.md`:

- `AUTHENTICATION_REQUIRED` — missing or malformed bearer token
- `TOKEN_EXPIRED` — bearer token's `exp` is past
- `INVALID_CREDENTIALS` — login failed (email or password wrong)
- `FORBIDDEN` — caller's role or ownership trace doesn't permit the
  operation
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
- `WALKER_ALREADY_EXISTS` — second `role=walker` registration attempt
- `RESOURCE_NOT_FOUND` — GET / PATCH / POST on an id that doesn't
  exist
