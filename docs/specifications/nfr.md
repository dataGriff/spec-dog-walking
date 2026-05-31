# Non-Functional Requirements — Dog Walking

> Quantified thresholds the Dog Walking domain must meet. Every NFR
> carries a measurable target (number, percentage, or time unit) OR
> a behavioural guarantee with an explicit n-a justification logged
> against the soft-gate engagement loop. Aspirational language
> ("fast", "scalable", "robust") is not permitted here — if a
> threshold cannot yet be set, it belongs in `_ambiguities.md` as a
> deferral, not in this file.

---

## Performance

### NFR-PERF-001: Read latency

`GET /v1/walks`, `GET /v1/walks/{walkId}/updates`, `GET /v1/invoices`,
`GET /v1/dogs`, `GET /v1/rate-card` complete with **p95 ≤ 200 ms**
and **p99 ≤ 400 ms**, measured server-side from request received to
response flushed, under a steady-state load of 5 requests per second
against a populated catalogue of 50 clients, 100 dogs, 1 000 walks,
and 100 invoices.

### NFR-PERF-002: Write latency

`POST /v1/walks`, `PATCH /v1/walks/{walkId}/decision`,
`POST /v1/walks/{walkId}/complete`, `POST /v1/walks/{walkId}/cancel`,
`POST /v1/invoices`, `POST /v1/invoices/{invoiceId}/mark-paid`,
`POST /v1/dogs`, `PATCH /v1/dogs/{dogId}` complete with
**p95 ≤ 300 ms** and **p99 ≤ 600 ms** under the same load profile
as NFR-PERF-001. The budget includes synchronous event publication.

### NFR-PERF-003: Auth latency

`POST /v1/auth/register`, `POST /v1/auth/login`,
`POST /v1/invites/{token}/accept`, and
`POST /v1/auth/password-reset/confirm` complete with
**p95 ≤ 500 ms**. The password-hashing cost mandated by NFR-SEC-002
is the dominant contributor; the budget accommodates a hash that
consumes ≥ 250 ms of CPU per request.

### NFR-PERF-004: Photo upload latency

`POST /v1/walks/{walkId}/updates` (multipart with photos) completes
with **p95 ≤ 2 000 ms** for an update with 3 photos of average
1.5 MB each. The 2-second budget is set against a typical mobile
network (LTE upload, ~5 Mbps).

### NFR-PERF-005: Photo retrieval latency

`GET /v1/walk-updates/{updateId}/photos/{photoId}` returns the first
byte with **p95 ≤ 250 ms** and completes streaming with
**p95 ≤ 1 500 ms** for a 1.5 MB photo.

### NFR-PERF-006: List pagination ceiling

`GET /v1/walks`, `GET /v1/invoices`, `GET /v1/dogs` return at most
**50 items per page** (enforced by `PageSize.maximum: 50` in
`contracts/openapi.yaml`). A request with `pageSize` above 50 is
rejected with `VALIDATION_ERROR`.

---

## Availability

### NFR-AVAIL-001: API uptime

The HTTP API is available **≥ 99.5 %** of the time, measured monthly
(no more than 220 minutes of unavailability per 30-day window).
99.5 % is the realistic target for a single-walker solo product;
99.9 % belongs to multi-walker SaaS deployments.

### NFR-AVAIL-002: Event delivery

Domain events are delivered to the broker **≥ 99.5 %** of the time
(matches `datacontract.yaml` `slaProperties.availability`). Event
publication is best-effort within the API request — failed
publication does not block the API response, but is logged and
retried via an out-of-band consumer (out of scope for this spec).

---

## Throughput

### NFR-THRU-001: Steady-state request rate

The API sustains **5 requests per second** of mixed traffic (~70 %
reads, ~30 % writes) without degradation in the latency targets of
NFR-PERF-001 and NFR-PERF-002. This is set against the realistic
single-walker workload: one walker, ~20 active clients, ~50 active
dogs, ~30 walks per day.

### NFR-THRU-002: Peak burst

The API absorbs **bursts of up to 20 requests per second for up to
30 seconds** (e.g. when an owner opens the app first thing in the
morning and the schedule view fans out into a flurry of GET calls)
without returning `5xx` errors. Latency may temporarily exceed
NFR-PERF-001 budgets during bursts but must recover within 60
seconds.

---

## Security

### NFR-SEC-001: Token lifetimes

Access tokens have a lifetime of **15 minutes**; refresh tokens
have a lifetime of **30 days**. Both lifetimes are recorded as
claims in the JWT.

### NFR-SEC-002: Password-hash cost

Passwords are stored using an adaptive password-hashing algorithm
calibrated such that a single verification consumes **≥ 250 ms of
CPU on a modern server-class processor**. The choice of algorithm
(Argon2id, bcrypt, scrypt) is an implementation decision; the cost
target is fixed here.

### NFR-SEC-003: Bearer token transport

The API is served only over **TLS 1.2 or later**. Plaintext HTTP
requests are rejected at the edge (308 Permanent Redirect to HTTPS
is acceptable; opaque rejection is not).

### NFR-SEC-004: Rate limiting on auth endpoints

The four auth endpoints (`register`, `login`, `password-reset/
request`, `password-reset/confirm`) are rate-limited per source IP
at **5 requests per minute**, returning `429 Too Many Requests` on
the 6th request within the window. Limits per email (rather than IP)
are out of scope for v1.

---

## Observability

### NFR-OBS-001: Request logging

Every API request is logged with the operationId, the authenticated
user id (or `anonymous`), the response status code, and the
end-to-end latency in milliseconds. PII fields (email, name) are
not logged.

### NFR-OBS-002: Event publish observability

Every successful event publish records the channel, the CloudEvents
`id`, the `time`, and the publish latency in milliseconds. Failed
publishes record the same fields plus the broker error code.

### NFR-OBS-003: Photo storage observability

Every photo upload and retrieval records the operationId, the
photoId, the contentType, the sizeBytes, and the latency. Failed
uploads (size or MIME violation) record the failure reason.

---

## Data

### NFR-DATA-001: Walk-update retention

Walk updates (notes and photos) are retained for **at least 24
months** from the walk's `completedAt`. Earlier deletion is
out-of-scope behaviour (clients may eventually request deletion;
that lives in a future GDPR-handling phase).

### NFR-DATA-002: Invoice retention

Invoices are retained for **at least 84 months** (7 years) from
the `issued` timestamp — the conventional accounting record-keeping
period for small businesses in the UK / EU / US contexts.

### NFR-DATA-003: Photo storage size cap

A single walker's total stored photo bytes are capped at **10 GB**
across all their clients. Approaching the cap (≥ 9 GB) triggers an
observability log; exceeding it rejects new photo uploads with
`VALIDATION_ERROR` and a `details[]` entry naming the cap.

---

## Compatibility

### NFR-COMPAT-001: OpenAPI version stability

Within a major version of the OpenAPI contract (`info.version` major
component), no field is removed and no enum value is removed.
Additions are permitted. Major-version bumps are reserved for
breaking changes.

### NFR-COMPAT-002: AsyncAPI / data-contract alignment

Every event channel in `contracts/asyncapi.yaml` has a corresponding
record in `contracts/datacontract.yaml`, and field names match
exactly between the two. Validated at the contracts phase by
`EVENT-IN-DATACONTRACT`.
