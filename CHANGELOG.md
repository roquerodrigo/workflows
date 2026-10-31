# Changelog

## [2.2.0](https://github.com/roquerodrigo/workflows/compare/v2.1.0...v2.2.0) (2026-10-31)

### New features

- Rewritten release pull requests and published releases now end with a fixed sponsorship section in the language of the notes, kept out of CHANGELOG.md. ([#49](https://github.com/roquerodrigo/workflows/pull/49))

### Bug fixes

- Rewritten release pull requests no longer show the release-please banner above and below the notes; only the required delimiters remain. ([#48](https://github.com/roquerodrigo/workflows/pull/48))

## [2.1.0](https://github.com/roquerodrigo/workflows/compare/v2.0.0...v2.1.0) (2026-10-31)

### New features

- The release-please workflow accepts an optional anthropic-api-key secret that rewrites the release pull request notes and matching CHANGELOG.md section for users. ([#45](https://github.com/roquerodrigo/workflows/pull/45))
- Rewritten notes are written in pt-BR when hacs.json declares Brazil as the country, and in English otherwise. ([#45](https://github.com/roquerodrigo/workflows/pull/45))
- If rewriting fails, the release keeps the original release-please notes and the release and publishing proceed normally. ([#45](https://github.com/roquerodrigo/workflows/pull/45))

## [2.0.0](https://github.com/roquerodrigo/workflows/compare/v1.0.0...v2.0.0) (2026-10-31)


### ⚠ BREAKING CHANGES

* sync-uv-lock.yml is removed. Callers must declare uv.lock under extra-files in release-please-config.json instead.

### Features

* **policy:** match Home Assistant repositories by pattern ([98e0a73](https://github.com/roquerodrigo/workflows/commit/98e0a732d3b6ce1a2339cba76af781d724afd7a8))


### Bug Fixes

* **deps:** bump pypa/gh-action-pypi-publish to v1.14.3 ([3b33006](https://github.com/roquerodrigo/workflows/commit/3b33006796b33bdf38144f1e975c43b9aff861ae))


### Build System

* remove the sync-uv-lock workflow ([2c076d4](https://github.com/roquerodrigo/workflows/commit/2c076d4d5da1351c13f3cd0c0986d2b457ba4c1a))


### Miscellaneous Chores

* **release:** keep only user-facing changes in the changelog ([0bf4e04](https://github.com/roquerodrigo/workflows/commit/0bf4e0405215a131ca74fa2fc9a9316cf1139582))

## 1.0.0 (2026-09-19)


### Features

* **auto-assign:** assign the author alongside the maintainer ([7dac6c4](https://github.com/roquerodrigo/workflows/commit/7dac6c4c0e312eb1731c1e0e6e642aa683b1b2a5))
* **hacs:** attach the card bundle to plugin releases ([ed698a8](https://github.com/roquerodrigo/workflows/commit/ed698a840ab211138f4dc0084c8d4b3a23a2186a))
* **hacs:** attach the install zip to integration releases ([13ce050](https://github.com/roquerodrigo/workflows/commit/13ce050602f4242a453ee7a556cea1812fe0f4ff))
* **policy:** reconcile repository settings alongside branch protection ([abb5de9](https://github.com/roquerodrigo/workflows/commit/abb5de9b1774c78495a58c4290ab28f11f2bc926))
* **protection:** reconcile branch protection across the account ([5798601](https://github.com/roquerodrigo/workflows/commit/579860135732a715a3bbddef119ff20066a24dfc))
* reusable workflows and composite actions ([4cfb11c](https://github.com/roquerodrigo/workflows/commit/4cfb11ce54057395c1319e28e1d09612a4535260))


### Bug Fixes

* grant contents read to the jobs that check out ([257af40](https://github.com/roquerodrigo/workflows/commit/257af40bcf5be757bf96e4a3c6d1cf4b47264a00))
* **hacs:** package the tracked tree with git archive ([d78b3ca](https://github.com/roquerodrigo/workflows/commit/d78b3ca8a86e1e0d703169175a7b35848db31909))


### Dependencies

* **deps:** bump astral-sh/setup-uv in /actions/setup-python ([17bc514](https://github.com/roquerodrigo/workflows/commit/17bc514947491231b112317a78ac726681925e64))
* **deps:** bump astral-sh/setup-uv in /actions/setup-python ([ee1a979](https://github.com/roquerodrigo/workflows/commit/ee1a97945de48b652c180095200b5ecf104487f5))
* **deps:** bump astral-sh/setup-uv in the actions group ([88f95f7](https://github.com/roquerodrigo/workflows/commit/88f95f7ba64ece986e4402e7d3a35f78e3d1b4df))
* **deps:** bump the actions group with 2 updates ([ccbcf73](https://github.com/roquerodrigo/workflows/commit/ccbcf73b2c325587cbdb660be0ca2c2318ef00c6))
* **deps:** bump the actions group with 3 updates ([c8f4cdb](https://github.com/roquerodrigo/workflows/commit/c8f4cdbb114d339ae54e35cd460ada75403d0271))
* **deps:** bump the actions group with 3 updates ([3f00a7f](https://github.com/roquerodrigo/workflows/commit/3f00a7fc0d9d1971a077ece08b4d7b0b290a1625))


### Documentation

* add CLAUDE.md ([33c4969](https://github.com/roquerodrigo/workflows/commit/33c4969e8147052909a01eacd75ea894f1cdfe42))
* add GitHub Sponsors button and support section ([8f61edb](https://github.com/roquerodrigo/workflows/commit/8f61edbe52ebccfec2ada40554522fa20c33c014))
* describe the repository policy job in CLAUDE.md ([dc7d909](https://github.com/roquerodrigo/workflows/commit/dc7d909150d5eefffe171526c03906f57be364e1))


### Continuous Integration

* cut releases with release-please ([9473d3c](https://github.com/roquerodrigo/workflows/commit/9473d3cefaafbf65a3babcb2bc748259d96e91e1))
* match the codeql-action version comment to the pinned commit ([3a0926a](https://github.com/roquerodrigo/workflows/commit/3a0926a4f2aa092d06a4bc9e9dd692f2d81b57f9))
* suppress the zizmor self-repository finding on the auto-assign caller ([97188c1](https://github.com/roquerodrigo/workflows/commit/97188c162f3c11890de5bf131f5bb2daf586a11b))


### Miscellaneous Chores

* label Dependabot commits deps ([dbeb972](https://github.com/roquerodrigo/workflows/commit/dbeb9725f89fd9d0ca3b6b9a3f698fe1c9caeb4c))
