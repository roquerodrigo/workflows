# workflows

Reusable GitHub Actions workflows (`.github/workflows/`) and composite actions
(`actions/`) shared by Home Assistant integrations, Python SDKs, npm packages and
Lovelace cards. `README.md` is the authoritative spec for the layout, caller
patterns and conventions — read it before changing a workflow's interface.

## The one constraint that governs every change

There are no version tags. Callers reference `@main`, so **a merge here is live in
every consumer on its next run**. A breaking change breaks everyone at once. Treat
input names, defaults, secret names and output names as a public contract: rename
or remove one only when you have checked the consumers, and prefer adding an
optional input over changing an existing one.

## Verifying a change

CI (`self-ci.yml`) is the only test surface — there is no package manager here.
Reproduce it locally before opening a PR:

- `actionlint`
- `uvx --from 'zizmor>=1,<2' zizmor --persona regular --min-severity low .`
  (needs `GH_TOKEN` set; audit policy lives in `zizmor.yml`)

## Conventions not obvious from a single file

- Third-party action `uses:` are pinned by commit digest with a trailing version
  comment; `roquerodrigo/*` are pinned by branch on purpose (see `zizmor.yml` —
  freezing them would defeat the shared-`@main` model). Dependabot bumps the
  digests.
- Workflow scope is `permissions: {}`; each job grants only what it needs. A
  reusable workflow may not request more than its caller granted, so callers keep
  their own `permissions: {}` ceiling.
- Secrets are passed explicitly, never `secrets: inherit`.
- Every job sets `timeout-minutes`.
- `home-assistant-validate.yml` jobs are opt-out (`hassfest`, `hacs`,
  `version-check` inputs) because private integrations and Lovelace cards can't run
  the full set — see the header comment there.

## Git

Public repo with branch protection: work on a feature branch, open a PR, let CI go
green. Merge with **rebase merge only** (squash and merge-commit are disabled).
