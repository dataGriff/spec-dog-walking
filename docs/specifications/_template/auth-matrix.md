# Auth Matrix

> **Template placeholder.** Do not edit in place. The suite's
> access-control skill copies this into
> `docs/specifications/auth-matrix.md` when Phase 3 starts (or run
> `task domain:init` to copy every template at once).

---

## Roles

<!-- Define all roles in your system. -->

| Role | Description |
|------|-------------|
| `admin` | TODO |
| `[role1]` | TODO |
| `[role2]` | TODO |

## Authentication

<!-- Describe the authentication mechanism. -->

All protected routes require a `Bearer` JWT token in the `Authorization` header.  
Unauthenticated requests to protected routes return `401 Unauthorized`.

Tokens are issued via `POST /v1/auth/login` and refreshed via `POST /v1/auth/refresh`.

## Auth Matrix

<!-- For each resource and operation, list which roles are allowed. -->
<!-- Use: ✅ allowed | ❌ forbidden | 🌐 public (no auth) -->

### Authentication

| Operation | Endpoint | Public | [role1] | [role2] | admin |
|-----------|----------|--------|---------|---------|-------|
| Register | `POST /v1/auth/register` | 🌐 | 🌐 | 🌐 | 🌐 |
| Login | `POST /v1/auth/login` | 🌐 | 🌐 | 🌐 | 🌐 |
| Refresh token | `POST /v1/auth/refresh` | 🌐 | 🌐 | 🌐 | 🌐 |
| Logout | `POST /v1/auth/logout` | ❌ | ✅ | ✅ | ✅ |

### [Resource1]

| Operation | Endpoint | Public | [role1] | [role2] | admin |
|-----------|----------|--------|---------|---------|-------|
| List | `GET /v1/[resource1]` | ❌ | ✅ | ❌ | ✅ |
| Get | `GET /v1/[resource1]/{id}` | ❌ | ✅ own | ❌ | ✅ |
| Create | `POST /v1/[resource1]` | ❌ | ✅ | ❌ | ✅ |
| Update | `PATCH /v1/[resource1]/{id}` | ❌ | ✅ own | ❌ | ✅ |
| Delete | `DELETE /v1/[resource1]/{id}` | ❌ | ✅ own | ❌ | ✅ |

### [Resource2]

| Operation | Endpoint | Public | [role1] | [role2] | admin |
|-----------|----------|--------|---------|---------|-------|
| List | `GET /v1/[resource2]` | ❌ | ❌ | ✅ | ✅ |
| Get | `GET /v1/[resource2]/{id}` | ❌ | ✅ | ✅ own | ✅ |
| Create | `POST /v1/[resource2]` | ❌ | ✅ | ❌ | ✅ |
| Update | `PATCH /v1/[resource2]/{id}` | ❌ | ❌ | ✅ own | ✅ |
| Delete | `DELETE /v1/[resource2]/{id}` | ❌ | ❌ | ✅ own | ✅ |

## Ownership Rules

<!-- Define what "own" means for each resource that has ownership-scoped access. -->

- **[Resource1]**: A `[role1]` may only access their own [resource1]. The `[role1Id]` field on the resource must match `req.user.sub`.
- **[Resource2]**: A `[role2]` may only access [resource2] records where `[role2Id]` matches `req.user.sub`.

## Error Responses

| Scenario | HTTP Status | Error Code |
|----------|-------------|------------|
| No token provided | `401` | `AUTHENTICATION_REQUIRED` |
| Token expired | `401` | `TOKEN_EXPIRED` |
| Valid token, wrong role | `403` | `FORBIDDEN` |
| Valid token, not owner | `403` | `FORBIDDEN` |
