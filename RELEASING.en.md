[Deutsch](RELEASING.md) | [English](RELEASING.en.md)

# Publishing

New worktrees for this project always belong under `V:\enigma2-connect-worktrees`.

## Contents

- [Development and branches](#development-and-branches)
- [Version before the pull request](#version-before-the-pull-request)
- [Checks](#checks)
- [Publish a release](#publish-a-release)

For development setup and project structure, see the
[developer guide](docs/DEVELOPMENT.en.md).

## Development and branches

Follow the [project instructions](AGENTS.en.md), adopted from BT-RC.
Make changes on `develop` or a working branch, never directly on `main`.
Merge into `main` only through a pull request after explicit user approval.
Merge approval does not authorize a release.

Automatically increase the version based on the entire unpublished scope since
the latest stable release: patch for fixes, internal changes and documentation,
minor for backward-compatible new features, major for incompatible changes.
Development versions use `X.Y.Z-dev.N`, starting at `dev.1`. Further completed
changes to the same target increment the counter; a higher target version starts
again at `dev.1`. Do not increment for every individual file edit.

Keep these version locations synchronized:

- `custom_components/enigma2_connect/manifest.json`: `version`.
- `pyproject.toml`: `project.version`, using the same full version identifier.
- `uv.lock`: local package `enigma2-connect`, using the normalized Python spelling
  `X.Y.Z.devN` for development versions.
- Latest entry and table of contents in [CHANGELOG.md](CHANGELOG.md) and
  [CHANGELOG.en.md](CHANGELOG.en.md).

Both changelogs start with a table of contents and list the newest version first.
Update the target version's entry for every relevant change and explicitly label
it as an unreleased development version. Preserve published history; do not
duplicate version history in the README.

The local baseline `0.1.0` is already assigned on `main`. When adopting these
rules, additional existing features result in the target `0.2.0-dev.1`.
This does not claim publication; recheck the actual remote and release baseline
before preparing a PR.

## Version before the pull request

1. Immediately before every PR into `main`, fetch remote branches and tags, for
   example with `git fetch origin --prune --tags`, and check published GitHub
   releases. Local versions or tags alone are insufficient.
2. Recalculate the appropriate version from the latest stable release and the
   entire proposed scope. Until a first stable release exists, use the existing
   version on `main` as the baseline. Account for intervening version increases
   on other branches. Do not reuse a published version or one already assigned
   on `main`, and do not decrease the version.
3. On the source branch, remove the entire `-dev.N` suffix and synchronize all
   version locations, including the lockfile and both changelog tables of contents.
   Keep the entry labelled unreleased; remove only its development-version label.
   Rerun the checks.
4. Preparation is incomplete without a current remote comparison. If `main` or
   the release baseline changes while the PR is open, repeat the comparison
   before merging and adjust the source branch. Merge only after user approval.

A version without a development suffix and a merge do not authorize automatic
tags, release drafts or publication.

## Checks

Run in the project directory on Linux/WSL with Python 3.14.2 or later:

```sh
uv sync --locked --group dev
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest --cov=custom_components.enigma2_connect --cov-report=term-missing
uv run --locked python -m compileall -q custom_components tests
node --test tests/frontend.test.cjs
git diff --check
```

After a version change, run `uv lock --offline` and verify that only the expected
project metadata changes. Do not update dependencies incidentally.
Check version locations and both changelogs, including language links.
The workflows `.github/workflows/tests.yml` and `.github/workflows/validate.yml`
run tests, Ruff, Hassfest and HACS. All checks must pass for the actual commit
being released.

Verification scope, known limitations and hardware results are recorded in the
[verification summary](docs/VALIDATION.en.md). Also test new features in Home
Assistant with the affected receivers and both UI languages. Existing reports
cover their documented state; they do not automatically cover later changes.
Simulated tests are not hardware acceptance tests.

## Publish a release

An explicit release instruction from the user is required, including for release
drafts and release tags.

1. Check the version and intended commit on `main`. Prepare pending changes using
   [Version before the pull request](#version-before-the-pull-request).
2. As part of the requested publication, remove the unreleased label from both
   changelogs. Prepare this change on a working branch too, then merge through a
   PR after user approval. Repeat the version comparison; merely marking the
   existing entry as published does not require a new product version.
3. Verify successful CI and document the actual hardware testing scope for the
   release commit. The manifest, project metadata, lockfile and both changelogs
   must contain the same stable version `X.Y.Z`.
4. Create the annotated tag `vX.Y.Z` on the checked commit on `main` and push that
   tag. A tag alone is not a published GitHub release.
5. In `topic2k/enigma2-connect`, create a GitHub release for tag `vX.Y.Z`, titled
   `X.Y.Z`. Use the corresponding sections from both changelogs as its bilingual
   description and publish it as a regular release.

An authorized draft remains unpublished until checks pass. Update the target
commit and bilingual description after changes. Create ZIP files only when
explicitly requested. The integration is in `custom_components/enigma2_connect`;
the optional card under `www/` is installed separately, see the
[user guide](docs/USER_GUIDE.en.md#dashboard-remote).
Do not distribute local `.work/` or `.local-archive/` files. The license remains
Apache-2.0. The [developer guide](docs/DEVELOPMENT.en.md#files-and-local-archives) describes
HACS installation and package boundaries; inclusion in the HACS default catalog
is a separate step.
