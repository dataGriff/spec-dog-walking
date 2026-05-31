# Error Catalogue — [Domain]

> Canonical error codes returned by the [Domain] API. Every error
> code referenced in `contracts/openapi.yaml` responses or in
> `auth-matrix.md` appears here with its HTTP status, meaning, and
> the conditions that trigger it. Code implementations must use these
> codes exactly.

---

## Authentication errors (401)

### `AUTHENTICATION_REQUIRED`

**HTTP status:** 401 Unauthorized

**Meaning:** The request reached a protected route but did not
include a valid bearer token in the `Authorization` header.

**Triggered by:**
- [List each trigger condition.]

**Response shape:** `Error` (`code`, `message`).

---

## Authorization errors (403)

### `FORBIDDEN`

**HTTP status:** 403 Forbidden

**Meaning:** The caller is authenticated but lacks permission for
this operation (either role-based or ownership-based).

**Triggered by:**
- [List each trigger condition.]

**Response shape:** `Error` (`code`, `message`).

---

## Not-found errors (404)

### `[RESOURCE1]_NOT_FOUND`

**HTTP status:** 404 Not Found

**Meaning:** The [Resource1] referenced by the path parameter does
not exist.

**Triggered by:**
- [Operation listing — e.g. GET /v1/[resource1]s/{id}, PATCH,
  DELETE]

**Response shape:** `Error` (`code`, `message`).

---

## Validation errors (400)

### `VALIDATION_FAILED`

**HTTP status:** 400 Bad Request

**Meaning:** The request body or query parameters failed schema
validation against the OpenAPI contract.

**Triggered by:**
- Any field violating its declared constraints in
  `contracts/openapi.yaml`.

**Response shape:** `ValidationError` (`code`, `message`,
`details[]`). Each entry in `details` names the offending `field`
and a one-line `issue` description.

---

## Error code → HTTP status reference

| Code | HTTP | Used by operations |
|------|------|-------------------|
| `AUTHENTICATION_REQUIRED` | 401 | All authenticated operations |
| `FORBIDDEN` | 403 | All write operations |
| `[RESOURCE1]_NOT_FOUND` | 404 | GET/PATCH/DELETE on /v1/[resource1]s/{id} |
| `VALIDATION_FAILED` | 400 | All operations with a request body |

---

## Authoring rules

1. **Codes are SCREAMING_SNAKE_CASE.** Stable across versions.
2. **Codes are domain-meaningful, not HTTP-restating.**
   `[RESOURCE1]_NOT_FOUND`, not `NOT_FOUND_404`.
3. **One trigger per code where possible.** Deliberate ambiguity
   (e.g. indistinguishable wrong-email vs wrong-password) must be
   called out explicitly in the code's description.
4. **Messages are human-readable, not localised.** Localisation is
   downstream of v1.
