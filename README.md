# workflows

[![Sponsor](https://img.shields.io/badge/Sponsor-%E2%9D%A4-db61a2?logo=githubsponsors&logoColor=white&style=for-the-badge)](https://github.com/sponsors/roquerodrigo)

Reusable GitHub Actions workflows and composite actions shared across Home
Assistant integrations, Python SDKs, npm packages and Lovelace cards.

Every consumer keeps a thin caller that wires these together. A fix lands once
here and reaches every repository on its next run.

## Layout

```
actions/                          composite actions — the shared steps
├── setup-python/                 uv, interpreter, dependency groups, cache
├── setup-node/                   Node, npm cache, npm ci
├── release-notes/                write the notes of the next release
└── release-please/               run release-please with those notes in place

.github/workflows/                reusable workflows — one concern each
├── python-lint.yml               Ruff, Mypy
├── python-test.yml               Pytest
├── node-lint.yml                 ESLint
├── node-build.yml                npm run build
├── node-test.yml                 npm test
├── codeql.yml                    CodeQL, any language
├── home-assistant-validate.yml   hassfest, HACS, manifest/pyproject drift
├── release-please.yml            release pull request and tagging
├── publish-pypi.yml              build and upload to PyPI
├── publish-hacs-zip.yml          attach the HACS install zip to the release
├── publish-hacs-plugin.yml       attach the HACS card bundle to the release
├── publish-npm.yml               build and publish to npm
├── auto-assign.yml               assign the maintainer and the author, optionally request a review
├── update-pr-branch.yml          rebase the pull request onto its base
└── self-*.yml                    this repository's own callers: CI, release, auto-assign, notes preview
```

Workflows are named after the ecosystem they serve, not the consumer that calls
them: linting a Python SDK and linting an integration are the same job, so they
share `python-lint.yml`. Only genuinely domain-specific behaviour —
`home-assistant-validate.yml` — carries a domain name.

## Versioning

Releases are cut by release-please from the conventional commits on `main`, and
each one is a `vX.Y.Z` tag with its notes in `CHANGELOG.md`. A change to an
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

CI is `python-lint.yml` plus `python-test.yml`. Release composes two
workflows, so each stage stays independently readable:

```yaml
jobs:
  release:
    uses: roquerodrigo/workflows/.github/workflows/release-please.yml@main
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

### Release notes

`release-please.yml` can write the notes of the release for the people who use the
project, instead of listing commits. Pass one more secret:

```yaml
    secrets:
      release-token: ${{ secrets.RELEASE_PLEASE_PAT }}
      anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
```

release-please still decides the version, the tag and the files. Before it touches
the release pull request, a job takes the commits the project shows in its changelog
(`changelog-sections`) and asks the Claude API for the text. release-please then runs
with that text as its notes, so the pull request, `CHANGELOG.md` and the release all
carry it from the first write. It publishes the release from the pull request body,
so reviewing the pull request is reviewing the text.

- The notes are in pt-BR when `hacs.json` declares `"country": ["BR"]`, and in
  English otherwise, unless the project declares a language (below). Section titles
  are fixed for each language, unless the project names its own.
- The release ends with a section that invites sponsorship, in the language of the
  release. It is fixed text, and it stays out of the changelogs, where it would
  repeat for every version.
- A hidden comment in the pull request records what the notes were written from: the
  commits shown and the configuration. While those stay the same, a push neither
  calls the model nor touches the pull request. A new commit in `changelog-sections`
  writes the notes again, since the entries may merge.
- A failure to write the notes leaves the release pull request as it is and fails the
  run, and the next push tries again. The default text is never used as a fallback.
  A release already merged is still tagged and published.
- The model runs with no tools and no GitHub token, and its text is rejected if it
  carries a link, an image or a mention, or omits a breaking commit.
- A first release has no previous tag to compare with, tags that carry a component
  are not supported, and neither is a repository with several packages. These keep
  the text release-please writes.

A project shapes its notes with an optional `.github/release-notes.toml`, read from
the commit being released. Without the file nothing changes, and every field can be
left out:

```toml
# The language of the notes, "en" or "pt-BR". Without it, hacs.json decides. Replaced
# by [[changelogs]] in a project with more than one language, below.
language = "pt-BR"

# Replaces the guidance on what to write and how. The rules on markup, breaking
# commits and instructions found in the data still apply. `summary` is the text
# above the sections, so the prompt decides what goes there.
prompt = """
You write the patch notes of a game for the people who play it.
"""

# Read first and in full. The limits on the size of a patch only cut other files,
# so a commit full of generated files never hides the ones that matter.
priority_paths = ["src/data/", "docs/changes.md"]

# One title per section, in the order they appear. The prompt says what goes in each.
[sections]
balance = "Balance"
fixes = "Bug fixes"
```

A `breaking` section is always there, first, with the title of the language unless
the file names it. A file that cannot be used counts as a failure to write the notes.

To keep the notes in another file, or in several languages, list the changelogs. The
first one is the language of the pull request and the release, and `[sections]` moves
inside each entry:

```toml
[[changelogs]]
language = "pt-BR"
# Optional here, and only here. Without it, `changelog-path` of release-please decides.
path = "CHANGELOG.md"

[[changelogs]]
language = "en"
path = "docs/CHANGELOG.en.md"

# A language other than "en" and "pt-BR" declares the texts it has no default for.
[[changelogs]]
language = "es"
path = "docs/CHANGELOG.es.md"
no_user_facing_changes = "Solo mantenimiento interno, sin cambios para quienes usan el proyecto."
support = "### Apoyo\n\nConsidera [apoyar el trabajo]({url}).\n"

[changelogs.sections]
breaking = "Cambios incompatibles"
added = "Novedades"
changed = "Mejoras"
fixed = "Correcciones"
```

A changelog can also keep each release in a file of its own, with `release_path`. It
needs `{version}`, the version without the `v`, and the file holds the same text as
the entry in the changelog. It works next to `path`, and a language other than the
first can use it instead of `path`. The first language always keeps `changelog-path`
too, unless release-please is told to `skip-changelog`:

```toml
[[changelogs]]
language = "en"
release_path = "docs/releases/en/{version}.md"
```

All the languages come from one call to the model, entry by entry, so they cannot
list different changes. Every changelog needs the same sections.

`self-release-notes-preview.yml` prints the notes of two past releases on any pull
request that touches the action, to judge a prompt change by its output.

### uv.lock

release-please ships no updater for `uv.lock`, so a project locked with uv —
SDK or integration — declares the lock under `extra-files` in
`release-please-config.json`, next to `pyproject.toml`:

```json
{
  "type": "toml",
  "path": "uv.lock",
  "jsonpath": "$.package[?(@.name.value==\"<package-name>\")].version"
}
```

The filter compares `@.name.value`, not `@.name`: release-please's TOML parser
wraps every scalar in a `{ start, end, value }` node, and `@.name` alone never
matches — release-please only logs `No entries modified` and leaves the lock on
the previous version.

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

## Support

This collection is built and maintained on personal time. If it is useful to you, consider [sponsoring the work](https://github.com/sponsors/roquerodrigo) — it keeps the development, the testing and the releases coming.
