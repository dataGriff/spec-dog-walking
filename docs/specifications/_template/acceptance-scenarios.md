# Acceptance Scenarios — [Domain]

> Given/When/Then scenarios at contract level. Every user story in
> `prd.md` has at least one scenario here. Scenarios are written at
> the HTTP-request level — they reference operation IDs, paths,
> status codes, and response shapes from `contracts/openapi.yaml`
> directly, so they can drive contract-level test suites in any
> implementation.

---

## US-001: [User story title]

### Scenario US-001-A: [Happy-path scenario name]

```gherkin
Given [precondition]
When I [action]
Then the response status is [code]
And the response body matches schema [SchemaName]
And [further assertions]
```

### Scenario US-001-B: [Edge case]

```gherkin
Given [precondition]
When I [action that should be rejected]
Then the response status is [code]
And the response body code equals "[ERROR_CODE]"
```

---

## US-002: [User story title]

### Scenario US-002-A: [Happy-path]

```gherkin
Given [precondition]
When I [action]
Then the response status is [code]
And [further assertions, including any domain event published]
```

---

## Cross-cutting

### Scenario CROSS-A: [Cross-cutting concern — e.g. expired token, refresh flow]

```gherkin
Given [precondition]
When I [action]
Then the response status is [code]
And [further assertions]
```
