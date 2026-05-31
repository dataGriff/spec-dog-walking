# Non-Functional Requirements — [Domain]

> Quantified thresholds the [Domain] domain must meet. Every NFR
> carries a measurable target (number, percentage, or time unit).
> Aspirational language ("fast", "scalable", "robust") is not
> permitted here — if a threshold cannot yet be set, it belongs in
> `_ambiguities.md` as a deferral, not in this file.

---

## Performance

### NFR-PERF-001: Read latency

[Operation set] complete with **p95 ≤ [number] ms** and **p99 ≤
[number] ms**, measured server-side from request received to response
flushed, under a steady-state load of [N requests per second] against
a populated dataset of [N records].

### NFR-PERF-002: Write latency

[Operation set] complete with **p95 ≤ [number] ms** and **p99 ≤
[number] ms** under the same load profile as NFR-PERF-001. The budget
includes synchronous event publication.

---

## Availability

### NFR-AVAIL-001: API uptime

The HTTP API is available **≥ [percentage] %** of the time, measured
monthly.

### NFR-AVAIL-002: Event delivery

Domain events are delivered to the broker **≥ [percentage] %** of the
time. Event publication is best-effort within the API request —
failed publication does not block the API response.

---

## Throughput

### NFR-THRU-001: Steady-state request rate

[Define throughput target, e.g. ≥ N requests per second sustained for
M minutes, under [read/write mix]%, without exceeding latency budgets.]

---

## Security

### NFR-SEC-001: Token lifetime

Access tokens expire **[number] s** after issue. Refresh tokens
expire **[number] s** after issue.

### NFR-SEC-002: Password hashing

Passwords are stored using an **adaptive password-hashing algorithm**
configured so that a single hash takes **≥ [number] ms** of CPU time
on commodity hardware. Plaintext passwords are never logged and never
returned in API responses.

### NFR-SEC-003: Transport encryption

All non-local traffic is served over **TLS [version] or higher**.

### NFR-SEC-004: Authentication coverage

**100 %** of routes outside [explicit allowlist] require a valid
bearer token. Routes without a declared `security` block in
`contracts/openapi.yaml` are a build-time audit failure.

---

## Data retention

### NFR-DATA-001: Event retention

Domain events are retained on the broker for **[number] days** (must
match `contracts/datacontract.yaml` `slaProperties.retention`).

### NFR-DATA-002: Domain data durability

[Either state durability guarantees with a measurable RPO/RTO, or
explicitly declare durability is not required for this reference
spec set. Use implementation-free language — describe the property,
not the mechanism.]

---

## Observability

### NFR-OBS-001: Request log coverage

**100 %** of incoming HTTP requests emit a structured log line
recording method, path, status code, latency in milliseconds, and
the authenticated `user.id` if present. No request bodies are
logged.

### NFR-OBS-002: Error sampling

**100 %** of `5xx` responses and **≥ [percentage] %** of `4xx`
responses produce a structured error log recording the error `code`,
the operation `operationId`, and the `user.id` if present.

### NFR-OBS-003: Event publish observability

Every successful event publish records the channel, the CloudEvents
`id`, and the publish latency in milliseconds. Failed publishes
record the same fields plus the broker error.

---

## Compatibility

### NFR-COMPAT-001: OpenAPI version stability

Within a major version of the OpenAPI contract (`info.version` major
component), no field is removed and no enum value is removed.
Additions are permitted. Major-version bumps are reserved for
breaking changes.

### NFR-COMPAT-002: AsyncAPI / data contract alignment

Field names, types, and required/optional status in
`contracts/asyncapi.yaml` event payloads match
`contracts/datacontract.yaml` exactly. Drift is a hard audit failure.
