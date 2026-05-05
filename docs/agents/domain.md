# Domain Docs

How the engineering skills should consume the Enclave Free workspace's domain documentation when exploring this repository.

## Layout

Use a multi-context layout rooted one level up from this repo:

```text
/Users/plebdev/Desktop/code/enclave-free/
├── CONTEXT-MAP.md
├── docs/adr/
├── enclave.free/
│   ├── CONTEXT.md
│   └── docs/adr/
├── sage/
│   ├── CONTEXT.md
│   └── docs/adr/
└── enclave.free-prototype/
    ├── CONTEXT.md
    ├── docs/adr/
    └── docs/agents/
```

This workspace is not an official monorepo, but the product context spans the original Enclave Free repo, the Sage agent repo, and this Enclave Free prototype repo. Treat those sibling repos as separate contexts inside one working domain.

## Before exploring, read these

- `../CONTEXT-MAP.md`, if it exists. Use it to decide which context files are relevant to the task.
- `../docs/adr/`, if it exists. Read workspace-level ADRs that touch the area you're about to work in.
- `../enclave.free/CONTEXT.md`, if the task touches the original Enclave Free product or behavior.
- `../sage/CONTEXT.md`, if the task touches the Sage agent, runtime, or forked agent behavior.
- `./CONTEXT.md`, if the task touches this prototype repo.
- `docs/adr/` inside each relevant sibling repo, if present, for context-scoped decisions.

If any of these files or directories do not exist, proceed silently. Do not flag their absence and do not suggest creating them upfront. The producer skill (`/grill-with-docs`) creates them lazily when terms or decisions get resolved.

## Use the glossary's vocabulary

When your output names a domain concept in an issue title, refactor proposal, hypothesis, or test name, use the term as defined in the relevant `CONTEXT.md`. Do not drift to synonyms the glossary explicitly avoids.

If the concept you need is not in a glossary yet, that is a signal: either you are inventing language the project does not use, or there is a real gap to note for `/grill-with-docs`.

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> Contradicts ADR-0007 (example decision) but worth reopening because...
