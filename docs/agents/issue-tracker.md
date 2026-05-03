# Issue tracker: GitHub

Issues and PRDs for this repo live as GitHub issues in `enclave-free/enclave.free-prototype`. Use the `gh` CLI for all operations.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --comments`, filtering comments by `jq` and also fetching labels.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

Infer the repo from `git remote -v`. The default repo for this prototype is `enclave-free/enclave.free-prototype`; use `gh repo set-default enclave-free/enclave.free-prototype` if the CLI cannot infer it.

## When a skill says "publish to the issue tracker"

Create a GitHub issue in `enclave-free/enclave.free-prototype`.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.
