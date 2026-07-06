# Agent instructions — DogWalking spec repository

This repository is the **authoritative specification** of the
DogWalking domain — requirements, domain model, and
API/event/data contracts. It contains no runnable implementation.

**Do not edit `docs/specifications/` directly.** Spec changes are
deliberate business decisions made through the
[domain-spec-suite](https://github.com/dataGriff/domain-spec-suite)'s
`domain-orchestrator` skill, which routes every change through the
right phase and its mechanical sign-off gates. Direct edits mark
phases stale and fail the audit.

**Implementing this domain?** Follow the canonical playbook at
[`docs/implementation-guide.md`](docs/implementation-guide.md) —
reading order, authority map, build workflow, verification loop.
Acceptance scenarios (`docs/specifications/acceptance-scenarios.md`)
are the acceptance test suite.

Useful commands (Taskfile is the single entry point):

```bash
task              # list all tasks
task audit        # full conformance audit (requires the suite as a sibling checkout)
task docs:serve   # browse the docs site locally
```
