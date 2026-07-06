# Acceptance Scenarios — Dog Walking

> Given/When/Then scenarios at contract level. Every user story in
> `prd.md` has at least one scenario here. Scenarios are written at
> the HTTP-request level — they reference operation IDs, paths,
> status codes, and response shapes from `contracts/openapi.yaml`
> (Phase 6) directly, so they can drive contract-level test suites
> in any implementation.
>
> **Conventions** (per the suite's scenario-authoring rules):
> every request literal is legal against the contracts (enum values,
> field lengths); response assertions use the schema's own property
> paths (bare entities — `status`, not `walk.status`); every `POST`
> request carries a unique `Idempotency-Key` header as the contract
> requires — stated explicitly only in the scenarios that test the
> idempotency semantics themselves (see Cross-cutting: Idempotency).

---

## US-000: Register as a walker

### Scenario US-000-A: Walker self-registers

```gherkin
Given no walker is registered on this instance
And no user exists with email "alison@example.com"
When I POST /v1/auth/register with
  | email       | alison@example.com |
  | password    | walks4dogs         |
  | displayName | Alison             |
Then the response status is 201
And the response body contains a non-empty accessToken
And the response body contains a non-empty refreshToken
And an event with type "dogwalking.user.registered" is published
And an event with type "dogwalking.walker.registered" is published
```

### Scenario US-000-B: Second walker registration rejected

```gherkin
Given a walker is already registered on this instance
When I POST /v1/auth/register with email "second@example.com", password "walks4dogs", displayName "Second"
Then the response status is 409
And the response body code equals "WALKER_ALREADY_EXISTS"
```

### Scenario US-000-C: Duplicate email rejected

```gherkin
Given no walker is registered on this instance
And a user already exists with email "alison@example.com"
When I POST /v1/auth/register with email "alison@example.com" and otherwise valid fields
Then the response status is 409
And the response body code equals "EMAIL_ALREADY_REGISTERED"
```

### Scenario US-000-D: Short password rejected

```gherkin
Given no walker is registered on this instance
When I POST /v1/auth/register with password "short7!" and otherwise valid fields
Then the response status is 400
And the response body code equals "VALIDATION_ERROR"
```

---

## US-001: Add a new client

### Scenario US-001-A: Walker invites a new client

```gherkin
Given a walker is logged in
And no user exists with email "clancy@example.com"
When I POST /v1/clients with
  | name  | Clancy            |
  | email | clancy@example.com |
Then the response status is 201
And the response body contains an invite id
And the response body status equals "pending"
And the response body expiresAt is 24 hours from now
And the response body contains no clientId — the Client record is created at acceptance
And an event with type "dogwalking.invite.created" is published
```

### Scenario US-001-B: Duplicate email rejected

```gherkin
Given a walker is logged in
And a user already exists with email "clancy@example.com"
When I POST /v1/clients with email "clancy@example.com"
Then the response status is 409
And the response body code equals "EMAIL_ALREADY_REGISTERED"
```

### Scenario US-001-C: Owner cannot add clients

```gherkin
Given an owner is logged in
When I POST /v1/clients with valid fields
Then the response status is 403
And the response body code equals "FORBIDDEN"
```

### Scenario US-001-D: Walker lists their clients

```gherkin
Given a walker is logged in
And 2 clients exist who accepted this walker's invites
When I GET /v1/clients
Then the response status is 200
And the response body data has length 2
```

---

## US-002: Accept invite and set password

### Scenario US-002-A: Valid invite accepted

```gherkin
Given an invite exists with token "INV123" in status "pending"
And the invite is less than 24 hours old
When I POST /v1/invites/INV123/accept with password "hunter2hunter"
Then the response status is 200
And the response body contains an accessToken and a refreshToken
And an event with type "dogwalking.invite.accepted" is published
And an event with type "dogwalking.user.registered" is published
And an event with type "dogwalking.client.registered" is published
And the invite.accepted and client.registered payloads both carry the inviteId
```

### Scenario US-002-B: Expired invite rejected

```gherkin
Given an invite exists with token "INV123" created more than 24 hours ago
When I POST /v1/invites/INV123/accept with a valid password
Then the response status is 410
And the response body code equals "INVITE_EXPIRED"
And an event with type "dogwalking.invite.expired" is published
```

### Scenario US-002-C: Already-used invite rejected

```gherkin
Given an invite exists with token "INV123" in status "accepted"
When I POST /v1/invites/INV123/accept with a valid password
Then the response status is 410
And the response body code equals "INVITE_ALREADY_USED"
```

### Scenario US-002-D: Never-existed invite token rejected

```gherkin
Given no invite has ever been issued with token "GHOST99"
When I POST /v1/invites/GHOST99/accept with a valid password
Then the response status is 404
And the response body code equals "RESOURCE_NOT_FOUND"
```

---

## US-003: Log in

### Scenario US-003-A: Successful login

```gherkin
Given a registered user with email "alison@example.com" and password "walks4dogs"
When I POST /v1/auth/login with
  | email    | alison@example.com |
  | password | walks4dogs         |
Then the response status is 200
And the response body contains a non-empty accessToken
And the response body contains a non-empty refreshToken
```

### Scenario US-003-B: Wrong password rejected

```gherkin
Given a registered user with email "alison@example.com"
When I POST /v1/auth/login with email "alison@example.com" and password "wrong"
Then the response status is 401
And the response body code equals "INVALID_CREDENTIALS"
```

### Scenario US-003-C: Unknown email rejected indistinguishably

```gherkin
Given no user exists with email "ghost@example.com"
When I POST /v1/auth/login with email "ghost@example.com" and password "anything"
Then the response status is 401
And the response body code equals "INVALID_CREDENTIALS"
```

---

## US-004: Reset forgotten password

### Scenario US-004-A: Reset request always returns 204

```gherkin
When I POST /v1/auth/password-reset/request with email "anything@example.com"
Then the response status is 204
And the response body is empty
```

### Scenario US-004-B: Reset confirm succeeds and revokes refresh tokens observably

```gherkin
Given a registered user holding a refresh token "RT-OLD" from a previous login
And a password-reset token "RST123" in status "pending" issued less than 1 hour ago for that user
When I POST /v1/auth/password-reset/confirm with token "RST123" and newPassword "freshStart9"
Then the response status is 200
When I POST /v1/auth/refresh with refreshToken "RT-OLD"
Then the response status is 401
And the response body code equals "INVALID_REFRESH_TOKEN"
```

### Scenario US-004-C: Expired reset token rejected

```gherkin
Given a password-reset token "RST123" issued more than 1 hour ago
When I POST /v1/auth/password-reset/confirm with token "RST123" and a valid password
Then the response status is 410
And the response body code equals "RESET_TOKEN_EXPIRED"
```

### Scenario US-004-D: Already-used reset token rejected

```gherkin
Given a password-reset token "RST123" in status "used"
When I POST /v1/auth/password-reset/confirm with token "RST123" and a valid password
Then the response status is 410
And the response body code equals "RESET_TOKEN_ALREADY_USED"
```

### Scenario US-004-E: Never-existed reset token rejected

```gherkin
Given no password-reset token has ever been issued with value "GHOST99"
When I POST /v1/auth/password-reset/confirm with token "GHOST99" and a valid password
Then the response status is 404
And the response body code equals "RESOURCE_NOT_FOUND"
```

---

## US-021: Stay logged in without re-entering credentials

### Scenario US-021-A: Refresh token exchanged and rotated

```gherkin
Given a registered user holding a refresh token "RT1" from login
When I POST /v1/auth/refresh with refreshToken "RT1"
Then the response status is 200
And the response body contains a non-empty accessToken
And the response body contains a non-empty refreshToken different from "RT1"
When I POST /v1/auth/refresh with refreshToken "RT1" again
Then the response status is 401
And the response body code equals "INVALID_REFRESH_TOKEN"
```

### Scenario US-021-B: Unknown refresh token rejected indistinguishably

```gherkin
Given no refresh token "GHOST99" has ever been issued
When I POST /v1/auth/refresh with refreshToken "GHOST99"
Then the response status is 401
And the response body code equals "INVALID_REFRESH_TOKEN"
```

---

## US-022: Log out

### Scenario US-022-A: Logout revokes the refresh token

```gherkin
Given a registered user is logged in holding refresh token "RT1"
When I POST /v1/auth/logout with refreshToken "RT1"
Then the response status is 204
When I POST /v1/auth/refresh with refreshToken "RT1"
Then the response status is 401
And the response body code equals "INVALID_REFRESH_TOKEN"
```

---

## US-005: Add a dog

### Scenario US-005-A: Owner adds their own dog

```gherkin
Given an owner is logged in
When I POST /v1/dogs with
  | name       | Bramble       |
  | breed      | border-collie |
  | medication | none          |
Then the response status is 201
And the response body ownerId equals my client id
And an event with type "dogwalking.dog.added" is published
```

### Scenario US-005-B: Walker adds a dog for one of their clients

```gherkin
Given a walker is logged in
And a client "C1" exists who was invited by this walker
When I POST /v1/dogs with name "Bramble" and ownerId "C1"
Then the response status is 201
And the response body ownerId equals "C1"
```

### Scenario US-005-C: Walker cannot add a dog for a non-client

```gherkin
Given a walker is logged in
And a client "C2" exists who was invited by a different walker
When I POST /v1/dogs with name "Bramble" and ownerId "C2"
Then the response status is 404
And the response body code equals "RESOURCE_NOT_FOUND"
```

### Scenario US-005-D: Missing required field rejected

```gherkin
Given an owner is logged in
When I POST /v1/dogs with no "name" field
Then the response status is 400
And the response body code equals "VALIDATION_ERROR"
```

### Scenario US-005-E: Owner lists their dogs

```gherkin
Given an owner is logged in
And I have 2 dogs and a different owner has 3 dogs
When I GET /v1/dogs
Then the response status is 200
And the response body data has length 2
```

---

## US-006: Update dog details

### Scenario US-006-A: Owner edits their own dog

```gherkin
Given an owner is logged in
And a dog "D1" exists owned by me
When I PATCH /v1/dogs/D1 with medication "twice daily, with food"
Then the response status is 200
And the response body medication equals "twice daily, with food"
And an event with type "dogwalking.dog.updated" is published
```

### Scenario US-006-B: Cross-owner edit indistinguishable from not-found

```gherkin
Given an owner is logged in
And a dog "D2" exists owned by a different owner
When I PATCH /v1/dogs/D2 with any field
Then the response status is 404
And the response body code equals "RESOURCE_NOT_FOUND"
```

---

## US-020: View a single dog

### Scenario US-020-A: Owner views their own dog

```gherkin
Given an owner is logged in
And a dog "D1" exists owned by me
When I GET /v1/dogs/D1
Then the response status is 200
And the response body id equals "D1"
And the response body ownerId equals my client id
```

### Scenario US-020-B: Cross-owner view indistinguishable from not-found

```gherkin
Given an owner is logged in
And a dog "D2" exists owned by a different owner
When I GET /v1/dogs/D2
Then the response status is 404
And the response body code equals "RESOURCE_NOT_FOUND"
```

### Scenario US-020-C: Unknown dog id rejected

```gherkin
Given an owner is logged in
When I GET /v1/dogs/00000000-0000-0000-0000-000000000000
Then the response status is 404
And the response body code equals "RESOURCE_NOT_FOUND"
```

---

## US-007: Schedule a walk

### Scenario US-007-A: Owner requests a walk

```gherkin
Given an owner is logged in
And a dog "D1" exists owned by me
And the walker's rate card has an entry for walkType "solo", durationMinutes 30
When I POST /v1/walks with
  | dogId           | D1                  |
  | startAt         | (any future ISO 8601)|
  | durationMinutes | 30                  |
  | walkType        | solo                |
Then the response status is 201
And the response body status equals "requested"
And the response body priceCents is null
And an event with type "dogwalking.walk.requested" is published
```

### Scenario US-007-B: Walker schedules a walk directly and the price is recorded

```gherkin
Given a walker is logged in
And a dog "D1" exists owned by one of my clients
And my rate card prices walkType "solo", durationMinutes 30 at priceCents 1500
When I POST /v1/walks with dogId "D1", startAt in the future, durationMinutes 30, walkType "solo"
Then the response status is 201
And the response body status equals "scheduled"
And the response body priceCents equals 1500
And an event with type "dogwalking.walk.scheduled" is published
```

### Scenario US-007-C: Walk-type not on rate card rejected

```gherkin
Given an owner is logged in
And the walker's rate card has no entry for walkType "trail-run", durationMinutes 60
When I POST /v1/walks with walkType "trail-run", durationMinutes 60, and otherwise valid fields
Then the response status is 400
And the response body code equals "INVALID_WALK_TYPE"
```

### Scenario US-007-D: Past startAt rejected

```gherkin
Given an owner is logged in
And a dog "D1" exists owned by me
When I POST /v1/walks with dogId "D1", startAt set to yesterday, and otherwise valid fields
Then the response status is 400
And the response body code equals "VALIDATION_ERROR"
```

---

## US-008: Decide on a walk request

### Scenario US-008-A: Walker schedules a requested walk and the price is recorded

```gherkin
Given a walker is logged in
And my rate card prices walkType "solo", durationMinutes 30 at priceCents 1500
And a walk "W1" exists in status "requested" for one of my clients with walkType "solo", durationMinutes 30
When I PATCH /v1/walks/W1/decision with decision "scheduled"
Then the response status is 200
And the response body status equals "scheduled"
And the response body priceCents equals 1500
And an event with type "dogwalking.walk.scheduled" is published
```

### Scenario US-008-B: Walker declines a requested walk

```gherkin
Given a walker is logged in
And a walk "W1" exists in status "requested" for one of my clients
When I PATCH /v1/walks/W1/decision with decision "declined" and reason "already booked"
Then the response status is 200
And the response body status equals "declined"
And an event with type "dogwalking.walk.declined" is published
```

### Scenario US-008-C: Decision on non-requested walk rejected

```gherkin
Given a walker is logged in
And a walk "W1" exists in status "scheduled" for one of my clients
When I PATCH /v1/walks/W1/decision with decision "scheduled"
Then the response status is 409
And the response body code equals "WALK_NOT_PENDING"
```

---

## US-009: Cancel a walk

### Scenario US-009-A: Owner cancels their own walk

```gherkin
Given an owner is logged in
And a walk "W1" exists in status "scheduled" for my dog
When I POST /v1/walks/W1/cancel
Then the response status is 200
And the response body status equals "cancelled"
And an event with type "dogwalking.walk.cancelled" is published
```

### Scenario US-009-B: Cancel on completed walk rejected

```gherkin
Given a walker is logged in
And a walk "W1" exists in status "completed" for one of my clients
When I POST /v1/walks/W1/cancel
Then the response status is 409
And the response body code equals "WALK_NOT_CANCELLABLE"
```

### Scenario US-009-C: Cross-owner cancel indistinguishable from not-found

```gherkin
Given an owner is logged in
And a walk "W2" exists in status "scheduled" for a dog owned by a different owner
When I POST /v1/walks/W2/cancel
Then the response status is 404
And the response body code equals "RESOURCE_NOT_FOUND"
```

### Scenario US-009-D: Walker cancels a scheduled walk

```gherkin
Given a walker is logged in
And a walk "W1" exists in status "scheduled" assigned to me
When I POST /v1/walks/W1/cancel
Then the response status is 200
And the response body status equals "cancelled"
And the response body cancelledByRole equals "walker"
And an event with type "dogwalking.walk.cancelled" is published
```

### Scenario US-009-E: Walker cannot cancel a requested walk

```gherkin
Given a walker is logged in
And a walk "W1" exists in status "requested" for one of my clients
When I POST /v1/walks/W1/cancel
Then the response status is 403
And the response body code equals "FORBIDDEN"
```

---

## US-010: List walks

### Scenario US-010-A: Owner lists their own walks

```gherkin
Given an owner is logged in
And there are 3 walks for my dogs across statuses scheduled, completed, cancelled
When I GET /v1/walks
Then the response status is 200
And the response body contains exactly those 3 walks
```

### Scenario US-010-B: Owner does not see other owners' walks

```gherkin
Given an owner is logged in
And 5 walks exist for other owners' dogs
When I GET /v1/walks
Then the response body contains 0 walks
```

### Scenario US-010-C: Walk list is paginated

```gherkin
Given a walker is logged in
And 5 walks exist for my clients' dogs
When I GET /v1/walks?page=1&pageSize=2
Then the response status is 200
And the response body data has length 2
And the response body pagination.totalItems equals 5
When I GET /v1/walks?pageSize=51
Then the response status is 400
And the response body code equals "VALIDATION_ERROR"
```

---

## US-011: Complete a walk

### Scenario US-011-A: Walker completes a scheduled walk

```gherkin
Given a walker is logged in
And a walk "W1" exists in status "scheduled" and assigned to me
When I POST /v1/walks/W1/complete
Then the response status is 200
And the response body status equals "completed"
And the response body completedAt is set
And an event with type "dogwalking.walk.completed" is published
```

### Scenario US-011-B: Complete on non-scheduled walk rejected

```gherkin
Given a walker is logged in
And a walk "W1" exists in status "requested" for one of my clients
When I POST /v1/walks/W1/complete
Then the response status is 409
And the response body code equals "WALK_NOT_SCHEDULED"
```

### Scenario US-011-C: Owner cannot complete their own walk

```gherkin
Given an owner is logged in
And a walk "W1" exists in status "scheduled" for my dog
When I POST /v1/walks/W1/complete
Then the response status is 403
And the response body code equals "FORBIDDEN"
```

---

## US-012: Post a walk update

### Scenario US-012-A: Notes-only update

```gherkin
Given a walker is logged in
And a walk "W1" exists in status "scheduled" assigned to me
When I POST /v1/walks/W1/updates as multipart with notes "Great walk, no issues"
Then the response status is 201
And the response body notes equals "Great walk, no issues"
And the response body photos is an empty array
And an event with type "dogwalking.walkupdate.posted" is published
```

### Scenario US-012-B: Photos-only update

```gherkin
Given a walker is logged in
And a walk "W1" exists in status "scheduled" assigned to me
When I POST /v1/walks/W1/updates as multipart with 2 valid JPEG photos
Then the response status is 201
And the response body photos has length 2
```

### Scenario US-012-C: Empty update rejected

```gherkin
Given a walker is logged in
And a walk "W1" exists in status "scheduled" assigned to me
When I POST /v1/walks/W1/updates as multipart with no notes and no photos
Then the response status is 400
And the response body code equals "VALIDATION_ERROR"
```

### Scenario US-012-D: Oversize photo rejected

```gherkin
Given a walker is logged in
And a walk "W1" exists in status "scheduled" assigned to me
When I POST /v1/walks/W1/updates with a single 15 MB JPEG photo
Then the response status is 400
And the response body code equals "INVALID_PHOTO"
```

### Scenario US-012-E: Update on cancelled walk rejected

```gherkin
Given a walker is logged in
And a walk "W1" exists in status "cancelled" for one of my clients
When I POST /v1/walks/W1/updates with valid notes
Then the response status is 409
And the response body code equals "WALK_UPDATE_NOT_ALLOWED"
```

### Scenario US-012-F: Post-hoc update on a completed walk allowed

```gherkin
Given a walker is logged in
And a walk "W1" exists in status "completed" assigned to me
When I POST /v1/walks/W1/updates as multipart with notes "Forgot to mention: Bramble found a stick"
Then the response status is 201
And an event with type "dogwalking.walkupdate.posted" is published
```

### Scenario US-012-G: Too many photos rejected

```gherkin
Given a walker is logged in
And a walk "W1" exists in status "scheduled" assigned to me
When I POST /v1/walks/W1/updates as multipart with 6 valid JPEG photos
Then the response status is 400
And the response body code equals "INVALID_PHOTO"
```

### Scenario US-012-H: Wrong MIME type rejected

```gherkin
Given a walker is logged in
And a walk "W1" exists in status "scheduled" assigned to me
When I POST /v1/walks/W1/updates as multipart with one photo part of Content-Type image/gif
Then the response status is 400
And the response body code equals "INVALID_PHOTO"
```

---

## US-013: View walk updates

### Scenario US-013-A: Owner views updates for their own walk

```gherkin
Given an owner is logged in
And a walk "W1" exists for my dog with 2 posted updates
When I GET /v1/walks/W1/updates
Then the response status is 200
And the response body contains 2 updates in posted-at order
```

### Scenario US-013-B: Photo bytes returned by auth-protected endpoint

```gherkin
Given an owner is logged in
And an update on my walk has photoId "P1"
When I GET /v1/walk-updates/{updateId}/photos/P1
Then the response status is 200
And the response Content-Type is one of image/jpeg, image/png, image/heic
```

### Scenario US-013-C: Cross-owner photo access indistinguishable from not-found

```gherkin
Given an owner is logged in
And a photo "P1" belongs to a walk for a different owner
When I GET /v1/walk-updates/{updateId}/photos/P1
Then the response status is 404
And the response body code equals "RESOURCE_NOT_FOUND"
```

---

## US-014: Generate an invoice

### Scenario US-014-A: Walker generates an invoice for a billing period

```gherkin
Given a walker is logged in
And client "C1" has 3 completed walks in March 2026
When I POST /v1/invoices with clientId "C1", periodStart "2026-03-01", periodEnd "2026-03-31"
Then the response status is 201
And the response body lineItems has length 3
And the response body status equals "issued"
And the response body totalCents equals the sum of the 3 line-item priceCents
And an event with type "dogwalking.invoice.issued" is published
```

### Scenario US-014-B: No billable walks rejected

```gherkin
Given a walker is logged in
And client "C1" has 0 completed walks in April 2026
When I POST /v1/invoices with clientId "C1", periodStart "2026-04-01", periodEnd "2026-04-30"
Then the response status is 400
And the response body code equals "NO_BILLABLE_WALKS"
```

### Scenario US-014-C: Cross-walker client indistinguishable from not-found

```gherkin
Given a walker is logged in
And client "C2" was invited by a different walker
When I POST /v1/invoices with clientId "C2" and any valid period
Then the response status is 404
And the response body code equals "RESOURCE_NOT_FOUND"
```

### Scenario US-014-D: Rate-card change after scheduling does not reprice the invoice

```gherkin
Given a walker is logged in
And a walk "W1" was scheduled while walkType "solo", durationMinutes 30 was priced at priceCents 1500
And the rate card was later updated to price that entry at priceCents 2000
And walk "W1" is completed within March 2026
When I POST /v1/invoices with the walk's clientId, periodStart "2026-03-01", periodEnd "2026-03-31"
Then the response status is 201
And the line item for walk "W1" has priceCents 1500
```

---

## US-015: List invoices

### Scenario US-015-A: Walker lists all their issued invoices

```gherkin
Given a walker is logged in
And the walker has 4 invoices: 3 issued, 1 paid
When I GET /v1/invoices
Then the response status is 200
And the response body contains 4 invoices
```

### Scenario US-015-B: Owner lists only invoices addressed to them

```gherkin
Given an owner is logged in
And 3 invoices exist addressed to me
And 5 invoices exist addressed to other owners
When I GET /v1/invoices
Then the response body contains 3 invoices
```

### Scenario US-015-C: Invoices filtered by issue-date range

```gherkin
Given a walker is logged in
And the walker has 2 invoices issued in March 2026 and 1 issued in April 2026
When I GET /v1/invoices?from=2026-03-01&to=2026-03-31
Then the response status is 200
And the response body data has length 2
```

---

## US-016: Record an invoice as paid

### Scenario US-016-A: Walker marks an issued invoice paid

```gherkin
Given a walker is logged in
And invoice "I1" exists in status "issued" issued by me
When I POST /v1/invoices/I1/mark-paid with paidAt "2026-04-05T10:00:00Z" and paidVia "bank transfer"
Then the response status is 200
And the response body status equals "paid"
And the response body paidVia equals "bank transfer"
And an event with type "dogwalking.invoice.paid" is published
```

### Scenario US-016-B: Owner cannot mark their own invoice paid

```gherkin
Given an owner is logged in
And invoice "I1" exists addressed to me in status "issued"
When I POST /v1/invoices/I1/mark-paid with valid fields
Then the response status is 403
And the response body code equals "FORBIDDEN"
```

### Scenario US-016-C: Mark-paid on already-paid invoice rejected

```gherkin
Given a walker is logged in
And invoice "I1" exists in status "paid" issued by me
When I POST /v1/invoices/I1/mark-paid with valid fields
Then the response status is 409
And the response body code equals "INVOICE_NOT_ISSUED"
```

---

## US-017: Set my rate card

### Scenario US-017-A: Walker sets a valid rate card

```gherkin
Given a walker is logged in
And no rate card exists yet for this walker
When I PUT /v1/rate-card with
  | currency | GBP |
  | entries  | [{walkType: "solo", durationMinutes: 30, priceCents: 1500}, {walkType: "solo", durationMinutes: 60, priceCents: 2500}] |
Then the response status is 200
And the response body currency equals "GBP"
And the response body entries has length 2
And an event with type "dogwalking.ratecard.updated" is published
```

### Scenario US-017-B: Duplicate (walkType, durationMinutes) rejected

```gherkin
Given a walker is logged in
When I PUT /v1/rate-card with two entries both walkType "solo" durationMinutes 30
Then the response status is 400
And the response body code equals "VALIDATION_ERROR"
```

### Scenario US-017-C: Non-positive priceCents rejected

```gherkin
Given a walker is logged in
When I PUT /v1/rate-card with one entry priceCents 0
Then the response status is 400
And the response body code equals "VALIDATION_ERROR"
```

### Scenario US-017-D: Currency change rejected

```gherkin
Given a walker is logged in
And the walker's rate card was created with currency "GBP"
When I PUT /v1/rate-card with currency "EUR" and valid entries
Then the response status is 409
And the response body code equals "CURRENCY_IMMUTABLE"
```

---

## US-018: View the rate card

### Scenario US-018-A: Walker views their own rate card

```gherkin
Given a walker is logged in
And the walker's rate card has 3 entries
When I GET /v1/rate-card
Then the response status is 200
And the response body entries has length 3
```

### Scenario US-018-B: Owner views their walker's rate card

```gherkin
Given an owner is logged in
And the walker who invited me has a rate card with 3 entries
When I GET /v1/rate-card
Then the response status is 200
And the response body entries has length 3
```

### Scenario US-018-C: Rate card before first PUT is not found

```gherkin
Given a walker is logged in
And no rate card has ever been set on this instance
When I GET /v1/rate-card
Then the response status is 404
And the response body code equals "RESOURCE_NOT_FOUND"
```

---

## US-019: Add a tip when marking an invoice paid

### Scenario US-019-A: Mark paid with a tip

```gherkin
Given a walker is logged in
And invoice "I1" exists in status "issued" issued by me with totalCents 4500
When I POST /v1/invoices/I1/mark-paid with
  | paidAt   | 2026-04-05T10:00:00Z |
  | paidVia  | bank transfer        |
  | tipCents | 500                  |
Then the response status is 200
And the response body status equals "paid"
And the response body tipCents equals 500
And an event with type "dogwalking.invoice.paid" is published
And the event payload data.tipCents equals 500
```

### Scenario US-019-B: Mark paid without a tip defaults to 0

```gherkin
Given a walker is logged in
And invoice "I1" exists in status "issued" issued by me
When I POST /v1/invoices/I1/mark-paid with paidAt, paidVia, and no tipCents
Then the response status is 200
And the response body tipCents equals 0
```

### Scenario US-019-C: Negative tip rejected

```gherkin
Given a walker is logged in
And invoice "I1" exists in status "issued" issued by me
When I POST /v1/invoices/I1/mark-paid with tipCents -100 and otherwise valid fields
Then the response status is 400
And the response body code equals "VALIDATION_ERROR"
```

---

## Cross-cutting: Authentication failures

### Scenario AUTH-A: Missing bearer token rejected

```gherkin
Given no Authorization header is supplied
When I GET /v1/walks
Then the response status is 401
And the response body code equals "AUTHENTICATION_REQUIRED"
```

### Scenario AUTH-B: Tampered token rejected

```gherkin
Given an Authorization header whose bearer token signature does not verify
When I GET /v1/walks
Then the response status is 401
And the response body code equals "AUTHENTICATION_REQUIRED"
```

### Scenario AUTH-C: Expired access token rejected distinguishably

```gherkin
Given an Authorization header whose bearer token is validly signed but expired
When I GET /v1/walks
Then the response status is 401
And the response body code equals "TOKEN_EXPIRED"
```

---

## Cross-cutting: Rate limiting

### Scenario RATE-A: Sixth login attempt within a minute rejected

```gherkin
Given 5 POST /v1/auth/login requests were made from my IP within the last minute
When I POST /v1/auth/login with any credentials
Then the response status is 429
And the response body code equals "RATE_LIMITED"
And the response carries a Retry-After header
```

### Scenario RATE-B: Invite-token guessing rejected

```gherkin
Given 5 POST /v1/invites/{token}/accept requests were made from my IP within the last minute
When I POST /v1/invites/GUESS06/accept with a valid password
Then the response status is 429
And the response body code equals "RATE_LIMITED"
```

---

## Cross-cutting: Idempotency

### Scenario IDEM-A: Replaying a POST with the same key returns the original response

```gherkin
Given an owner is logged in
And a dog "D1" exists owned by me
When I POST /v1/walks with valid fields and Idempotency-Key "11111111-1111-1111-1111-111111111111"
Then the response status is 201
When I repeat the identical POST /v1/walks with Idempotency-Key "11111111-1111-1111-1111-111111111111"
Then the response status is 201
And the response body id equals the id from the first response
And only one event with type "dogwalking.walk.requested" is published
```

### Scenario IDEM-B: Reusing a key with a different body rejected

```gherkin
Given an owner is logged in
And a POST /v1/walks succeeded with Idempotency-Key "22222222-2222-2222-2222-222222222222"
When I POST /v1/walks with a different startAt and the same Idempotency-Key "22222222-2222-2222-2222-222222222222"
Then the response status is 409
And the response body code equals "IDEMPOTENCY_KEY_CONFLICT"
```

### Scenario IDEM-C: Missing Idempotency-Key rejected

```gherkin
Given an owner is logged in
When I POST /v1/walks with valid fields and no Idempotency-Key header
Then the response status is 400
And the response body code equals "VALIDATION_ERROR"
```
