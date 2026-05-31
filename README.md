# DogWalking

A **design-and-contracts-only** repository for the DogWalking domain.
Holds long-lived business requirements, rules, and API/event/data
contracts. No runnable implementation lives here — implementations
consume these specs from their own repositories.

> **Full documentation:** [`docs/index.md`](docs/index.md) (rendered via
> [MkDocs Material](https://squidfunk.github.io/mkdocs-material/)).

---

## Quick Start

```bash
mise trust          # one-time per clone — trusts this repo's .mise.toml
mise install        # installs Python 3.11, Node 20, Spectral,
                    # datacontract-cli, mkdocs-material via pipx
task setup          # installs pyyaml and wires git hooks
task                # list every available task
task domain:check   # lint contracts + regenerate the domain overview
task docs:serve     # browse the docs site locally
```

---

## What's in the Box

| Area | Location |
|------|----------|
| Product + domain requirements | `docs/specifications/*.md` |
| API / event / data contracts | `docs/specifications/contracts/*.yaml` |
| Blank spec templates | `docs/specifications/_template/` |
| Contract linting + docs tasks | `Taskfile.yml` |
| Published docs config | `mkdocs.yml`, `docs/`, `.github/workflows/docs.yml` |
| PR-time conformance audit | `.github/workflows/audit.yml` |

---

## How this repo was created

This repository was bootstrapped by the
[`domain-spec-suite`](https://github.com/dataGriff/domain-spec-suite),
which drives a user through an eight-phase walk (Bootstrap → Discovery
→ Modeling → Access Control → Flows → NFRs → Contracts → Audit) and
produces a complete, internally-consistent spec set. The suite's
audit phase is the source of truth for whether a spec set is
"complete".

To continue or update this spec set, invoke the
`domain-orchestrator` skill from the suite — it reads
`docs/specifications/_progress.yaml` and routes you to the right
phase.
