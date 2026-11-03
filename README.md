# workflows

[![Sponsor](https://img.shields.io/badge/Sponsor-%E2%9D%A4-db61a2?logo=githubsponsors&logoColor=white&style=for-the-badge)](https://github.com/sponsors/roquerodrigo)

Reusable GitHub Actions workflows and composite actions shared across Home
Assistant integrations, Python SDKs, npm packages and Lovelace cards.

What is specific to Home Assistant, validating a repository for the Home Assistant
Marketplace and attaching its release asset, lives in
[Home Assistant Autopilot](https://github.com/marketplace/actions/home-assistant-autopilot).

Every consumer keeps a thin caller that wires these together. A fix lands once
here and reaches every repository on its next run.

## Layout

```
actions/                          composite actions — the shared steps
├── setup-python/                 uv, interpreter, dependency groups, cache
└── setup-node/                   Node, npm cache, npm ci

.github/workflows/                reusable workflows — one concern each
├── python-lint.yml               Ruff, Mypy
├── python-test.yml               Pytest
├── node-lint.yml                 ESLint
├── node-build.yml                npm run build
├── node-test.yml                 npm test
├── codeql.yml                    CodeQL, any language
├── publish-pypi.yml              build and upload to PyPI
├── publish-npm.yml               build and publish to npm
├── auto-assign.yml               assign the maintainer and the author, optionally request a review
├── update-pr-branch.yml          rebase the pull request onto its base
└── self-*.yml                    this repository's own callers: CI, release, auto-assign
```

Workflows are named after the ecosystem they serve, not the consumer that calls
them: linting a Python SDK and linting an integration are the same job, so they
share `python-lint.yml`.

## Versioning

Releases are cut by [Release Autopilot](https://github.com/marketplace/actions/release-autopilot)
from the conventional commits on `main`, and each one is a `vX.Y.Z` tag with its
notes in `CHANGELOG.md`. A change to an
input, a default, a secret name or an output that breaks a caller is a major
bump.

The repositories this collection was built for reference `@main` and pick up
every change on their next run. That trades a pinning ritual for a stronger
contract on this side: the workflows here are linted with `actionlint` and
audited with `zizmor` on every pull request, `main` is protected, and Dependabot
keeps the pinned action digests current.

Anyone else should pin a release, by tag or by the commit behind it:

```yaml
uses: roquerodrigo/workflows/.github/workflows/python-lint.yml@v1.0.0
```

A pinned workflow is not frozen all the way down. The Python and Node workflows
load the composite actions under `actions/` from `@main`, so the setup steps
keep tracking `main` whatever ref the caller pinned.

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
    name: Home Assistant Marketplace
    needs: lint
    runs-on: ubuntu-latest
    timeout-minutes: 20
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: roquerodrigo/home-assistant-autopilot@latest

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

concurrency:
  group: release
  cancel-in-progress: false

permissions: {}

jobs:
  release:
    if: >-
      github.event.workflow_run.event == 'push' &&
      github.event.workflow_run.conclusion == 'success'
    runs-on: ubuntu-latest
    timeout-minutes: 15
    permissions:
      contents: write
      pull-requests: write
    steps:
      - id: release
        uses: roquerodrigo/release-autopilot@latest
        with:
          token: ${{ secrets.RELEASE_TOKEN }}
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}

      - if: steps.release.outputs.released == 'true'
        uses: roquerodrigo/home-assistant-autopilot@latest
        with:
          command: publish
          tag: ${{ steps.release.outputs.tag }}
```

The release itself comes from [Release Autopilot](https://github.com/marketplace/actions/release-autopilot),
which keeps the release pull request, writes the notes and tags the version. The
`workflow_run.event == 'push'` half of the condition is what stops a pull request
with green CI from cutting a release. A Lovelace card uses the same two steps with
its own CI, since Home Assistant Autopilot reads what the repository is.

### Python SDK

CI is `python-lint.yml` plus `python-test.yml`. Release is the same `release` job
as an integration's, exposing the outputs of Release Autopilot and followed by
`publish-pypi.yml`:

```yaml
  release:
    # ...the job above, without the Home Assistant Autopilot step
    outputs:
      released: ${{ steps.release.outputs.released }}
      tag: ${{ steps.release.outputs.tag }}

  publish:
    needs: release
    if: needs.release.outputs.released == 'true'
    uses: roquerodrigo/workflows/.github/workflows/publish-pypi.yml@main
    with:
      package: the-package-name
      ref: ${{ needs.release.outputs.tag }}
    secrets:
      pypi-token: ${{ secrets.PYPI_API_TOKEN }}
```

### npm package

CI is `node-lint.yml`, `node-build.yml` and `node-test.yml`. Release is
the same `release` job followed by `publish-npm.yml`.

`publish-npm.yml` uses npm trusted publishing, so there is no token to store.
Each package needs the publisher registered once, under **Package settings >
Trusted publisher** on npmjs.com: GitHub Actions, the consuming repository, and
the caller's workflow filename. The OIDC claim names the entry workflow, not the
reusable one.

## Conventions

- Third-party actions are pinned by commit digest with the version in a trailing
  comment. First-party publishing actions (`pypa`) are pinned the same way.
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

## Support

This collection is built and maintained on personal time. If it is useful to you, consider [sponsoring the work](https://github.com/sponsors/roquerodrigo) — it keeps the development, the testing and the releases coming.
