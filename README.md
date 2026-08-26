# workflows

Reusable GitHub Actions workflows and composite actions shared across Home
Assistant integrations, Python SDKs, npm packages and Lovelace cards.

Every consumer keeps a thin caller that wires these together. A fix lands once
here and reaches every repository on its next run.

## Layout

```
actions/                          composite actions — the shared setup steps
├── setup-python/                 uv, interpreter, dependency groups, cache
└── setup-node/                   Node, npm cache, npm ci

.github/workflows/                reusable workflows — one concern each
├── python-lint.yml               Ruff, Mypy
├── python-test.yml               Pytest
├── node-lint.yml                 ESLint
├── node-build.yml                npm run build
├── node-test.yml                 npm test
├── codeql.yml                    CodeQL, any language
├── home-assistant-validate.yml   hassfest, HACS, manifest/pyproject drift
├── release-please.yml            release pull request and tagging
├── sync-uv-lock.yml              uv.lock refresh on the release branch
├── publish-pypi.yml              build and upload to PyPI
├── publish-hacs-zip.yml          attach the HACS install zip to the release
├── publish-hacs-plugin.yml       attach the HACS card bundle to the release
├── publish-npm.yml               build and publish to npm
├── auto-assign.yml               assign the maintainer and the author
├── update-pr-branch.yml          rebase the pull request onto its base
└── repository-policy.yml         reconcile settings and protection account-wide

scripts/
└── reconcile-repository-policy.py

repository-policy.json            desired settings and branch protection
```

`repository-policy.yml` is the one workflow here that is not called by anyone:
it runs on a schedule in this repository and administers the others. It covers
two things that never drift but do go missing — the merge settings (rebase only,
auto-merge, branch deletion, secret scanning and its push protection) and branch
protection itself. A repository created after a convention was agreed never
receives it, so the reconcile also lists every public repository absent from
`repository-policy.json`, which is what makes a new one visible. Forks and
scratch repositories are meant to be absent and are never touched.

The schedule applies; a manual run reports unless `apply` is ticked. It needs
`BRANCH_PROTECTION_PAT`, a token with `repo` scope, because the default
`GITHUB_TOKEN` cannot reach outside this repository.

Workflows are named after the ecosystem they serve, not the consumer that calls
them: linting a Python SDK and linting an integration are the same job, so they
share `python-lint.yml`. Only genuinely domain-specific behaviour —
`home-assistant-validate.yml` — carries a domain name.

## Versioning

There are no tags. Callers reference `@main` and pick up every change on their
next run.

That trades a pinning ritual for a stronger contract on this side: the workflows
here are linted with `actionlint` and audited with `zizmor` on every pull
request, `main` is protected, and Dependabot keeps the pinned action digests
current. A breaking change is a breaking change everywhere at once, so it does
not get merged.

## Caller patterns

### Home Assistant integration

`.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

permissions: {}

jobs:
  lint:
    uses: roquerodrigo/workflows/.github/workflows/python-lint.yml@main

  tests:
    needs: lint
    uses: roquerodrigo/workflows/.github/workflows/python-test.yml@main

  validate:
    needs: lint
    uses: roquerodrigo/workflows/.github/workflows/home-assistant-validate.yml@main

  update-pr-branch:
    if: github.event_name == 'pull_request'
    needs: [lint, tests, validate]
    uses: roquerodrigo/workflows/.github/workflows/update-pr-branch.yml@main
```

`.github/workflows/release.yml`

```yaml
name: Release

on:
  workflow_run:
    workflows: [CI]
    types: [completed]
    branches: [main]

permissions: {}

jobs:
  release:
    if: >-
      github.event.workflow_run.event == 'push' &&
      github.event.workflow_run.conclusion == 'success'
    uses: roquerodrigo/workflows/.github/workflows/release-please.yml@main
    secrets:
      release-token: ${{ secrets.RELEASE_PLEASE_PAT }}

  publish:
    needs: release
    if: needs.release.outputs.release-created == 'true'
    uses: roquerodrigo/workflows/.github/workflows/publish-hacs-zip.yml@main
    with:
      domain: <domain>
      ref: ${{ needs.release.outputs.tag-name }}
```

The `workflow_run.event == 'push'` half of that condition is what stops a pull
request with green CI from cutting a release.

`publish-hacs-zip.yml` packages `custom_components/<domain>/` and attaches it to
the tag. It only pays off alongside `hacs.json`:

```json
{ "zip_release": true, "filename": "<domain>.zip" }
```

Without both halves HACS keeps installing file by file, and the release's
`download_count` — the only per-repository usage figure there is — stays at
zero. The analytics Home Assistant publishes are keyed by domain, so a fork and
the project it forked from report as one.

A private integration cannot run HACS validation, which reads the repository
through the public API — pass `hacs: false`. A Lovelace card has no manifest and
no Python package — pass `hassfest: false`, `version-check: false` and
`hacs-category: plugin`.

A card also releases its asset differently. There is no directory to package, so
it composes `publish-hacs-plugin.yml` instead, naming the bundle that
`hacs.json` already points at:

```yaml
  publish:
    needs: release
    if: needs.release.outputs.release-created == 'true'
    uses: roquerodrigo/workflows/.github/workflows/publish-hacs-plugin.yml@main
    with:
      filename: <card>.js
      ref: ${{ needs.release.outputs.tag-name }}
```

### Python SDK

CI is `python-lint.yml` plus `python-test.yml`. Release composes three
workflows, so each stage stays independently readable:

```yaml
jobs:
  release:
    uses: roquerodrigo/workflows/.github/workflows/release-please.yml@main
    secrets:
      release-token: ${{ secrets.RELEASE_PLEASE_PAT }}

  sync-uv-lock:
    needs: release
    if: needs.release.outputs.release-pr != ''
    uses: roquerodrigo/workflows/.github/workflows/sync-uv-lock.yml@main
    with:
      release-pr: ${{ needs.release.outputs.release-pr }}
    secrets:
      release-token: ${{ secrets.RELEASE_PLEASE_PAT }}

  publish:
    needs: release
    if: needs.release.outputs.release-created == 'true'
    uses: roquerodrigo/workflows/.github/workflows/publish-pypi.yml@main
    with:
      package: the-package-name
      ref: ${{ needs.release.outputs.tag-name }}
    secrets:
      pypi-token: ${{ secrets.PYPI_API_TOKEN }}
```

### npm package

CI is `node-lint.yml`, `node-build.yml` and `node-test.yml`. Release is
`release-please.yml` followed by `publish-npm.yml`.

`publish-npm.yml` uses npm trusted publishing, so there is no token to store.
Each package needs the publisher registered once, under **Package settings >
Trusted publisher** on npmjs.com: GitHub Actions, the consuming repository, and
the caller's workflow filename. The OIDC claim names the entry workflow, not the
reusable one.

## Conventions

- Third-party actions are pinned by commit digest with the version in a trailing
  comment. First-party publishing actions (`googleapis`, `pypa`) are pinned the
  same way.
- `permissions: {}` at workflow scope; each job declares only the scopes it
  needs. GitHub refuses to start a run when a reusable workflow asks for more
  than its caller granted, so the caller stays the ceiling.
- Secrets are passed explicitly rather than with `secrets: inherit`, so the
  caller shows what each pipeline can reach.
- Every job carries `timeout-minutes`. Without it a wedged job holds a runner
  for six hours.
- Coverage thresholds and lint targets live in the consumer's own configuration
  (`pyproject.toml`, the test runner config), never as workflow inputs, so a
  local run and CI agree on what passing means.
