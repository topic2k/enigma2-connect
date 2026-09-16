[Deutsch](AGENTS.md) | [English](AGENTS.en.md)

# Project instructions

## Project

Enigma2 Connect is a Home Assistant custom integration for Enigma2 receivers
using OpenWebif. Target: Home Assistant 2026.9 or later, Python 3.14.2 or later.
Project code is licensed under Apache-2.0. Keep unrelated existing changes intact.

## Changelog and release documentation

These versioning, changelog, release and branching rules follow BT-RC.
Maintain these instructions, [RELEASING.en.md](RELEASING.en.md) and
[CHANGELOG.en.md](CHANGELOG.en.md) together with their German counterparts.
Each pair links to the other language. Both changelogs start with a table of
contents, list the newest version first and record every relevant change.
Continue the current target version's entry; preserve published history.
Changelogs contain only version history; do not duplicate it in the README.
The README describes current behavior and links to the changelog and release guide.
Detailed technical documentation and verification reports belong in `docs/`.
Distinguish simulated tests from actual receiver and Home Assistant checks.

Keep the README a short, easy-to-understand introduction from the user's
perspective with only essential information. Detailed usage instructions belong
in [USER_GUIDE.en.md](docs/USER_GUIDE.en.md); important developer information belongs
in [DEVELOPMENT.en.md](docs/DEVELOPMENT.en.md). The shared `README.md` contains
German first, followed by English, with jump links to both sections. Keep separate
German and English files for the user and developer guides and link each pair
to its counterpart.

The user guide explains tasks through simple steps and interface labels. Keep
action descriptions and YAML usage examples in the user guide under “Messages
and automations”. Keep API implementation details and technical edge cases in the
developer guide.
Keep `docs/` small: guides, a current verification summary and important license
records. When appropriate, preserve old analyses, reports and rejected designs
in a complete, verifiable `.local-archive/`; `.gitignore` keeps this folder local.
Move required information into active documentation first and update links.
Active branding sources and the font license belong in `assets/branding/`.

## Version locations

The integration version is in `custom_components/enigma2_connect/manifest.json`.
Keep `pyproject.toml` and the local `enigma2-connect` package in `uv.lock`
synchronized as well. There is no separate `INTEGRATION_VERSION` constant here.
The manifest, project metadata and both changelogs use `X.Y.Z-dev.N`;
`uv.lock` uses the equivalent normalized Python spelling `X.Y.Z.devN`.
Stable versions use `X.Y.Z` everywhere. Recheck lockfile consistency after changes.
Until a first stable release exists, use the existing version on `main` as the
baseline without presenting it as a published release. The initial `0.1.0` on
`main` plus unpublished new features leads to `0.2.0-dev.1` when adopting these
rules; the remote comparison before a PR remains mandatory.

## Branches, approval and releases

- Always create new worktrees for this project under `V:\enigma2-connect-worktrees`.
- Create a separate, descriptively named branch from current `develop` for every
  task. Use the existing working directory for small changes; also create a
  separate worktree for larger tasks.
- Commit completed changes on the working branch after appropriate checks,
  then merge them into `develop` and push `develop` without further approval.
  `develop` collects completed changes; do not implement directly on `develop`
  or `main`.
- Prepare and open a pull request from `develop` into `main` only after explicit
  user approval. Merge changes into `main` exclusively through that PR;
  merging also requires user approval.
- Create a new release only when explicitly instructed by the user.
  Approval of changes or a pull request does not authorize a release.
- The versioning rules below do not authorize automatic publication.

## Integration quality before merging into main

- Before merging into `main`, all required CI checks must pass for the current
  PR state and all integration quality requirements must remain satisfied.
  Changes must not lower the achieved quality status
  compared with the previous state and current `main`.
- Review the [quality checklist](custom_components/enigma2_connect/quality_scale.yaml)
  for the impact of the change. Additionally check affected requirements that CI
  does not cover. Do not lower fulfilled
  criteria, coverage thresholds or check strictness, or bypass them through
  unjustified exemptions.
- Keep evidence and remaining practical checks current in the
  [verification summary](docs/VALIDATION.en.md) and its German counterpart.
  Missing evidence does not count as a passed check. A regression or missing
  required evidence blocks merging; resolve it and check again first.
- Run targeted local checks appropriate to the change. Checks already supported
  by current CI results do not need a complete local rerun. A PR may be opened
  to run CI; passing CI alone does not prove all quality criteria are met in substance.
- If the source branch or `main` changes while a PR is open, ensure current CI
  results cover the resulting PR state and renew the quality comparison for
  affected requirements before merging.

## Versioning

- When making changes on `develop` or a working branch, automatically increase
  the version without a separate request, based on the entire unpublished scope
  since the last stable version: patch for fixes, internal changes and
  documentation-only changes, minor for backward-compatible new features,
  major for incompatible changes.
- Development builds use `X.Y.Z-dev.N`, starting with `dev.1`, for example
  `1.1.0-dev.1`. Increment the counter for further completed changes to the same
  target version; restart at `dev.1` when the target version increases.
  Do not assign a new version for every individual file edit.
- `version` in `manifest.json`, `version` in `pyproject.toml` and the newest entry in
  both changelogs must match, including the development suffix. Explicitly label
  the changelog entry as an unpublished development version and update it for
  further changes to the same target version.
- Immediately before each pull request into `main`, fetch the current remote
  state of `main`, tags and published releases. Recalculate the next appropriate
  version from the latest stable release and the entire proposed scope of changes.
  Account for intervening version increases from other branches or commits;
  do not reuse a published version or one already assigned on `main`, and do not
  decrease the version.
- On the working branch, remove the entire `-dev.N` suffix and synchronize the
  manifest, `version` in `pyproject.toml`, both changelogs and their tables of contents.
  Keep the entry labelled unpublished until publication, but no longer label it
  as a development version. Then run affected local checks; current successful
  CI is required before merging. This preparation is incomplete without an
  up-to-date comparison against the remote state.
- If `main` or the release baseline changes while a pull request is open, repeat
  the version comparison before merging and make any adjustments on the source
  branch. Merge only after user approval. A version without a development suffix
  or a merge does not authorize automatic tags or releases; an explicit release
  instruction is still required.

## Development rules

Before changes:

1. Analyze the existing code.
2. Understand the existing functionality.
3. Write a short implementation plan.

After changes:

1. Run tests appropriate to the change; do not repeat the full CI suite locally
   without a reason.
2. Check syntax when changing Python code.
3. Check affected Home Assistant compatibility as far as locally possible;
   verify current CI results before merging.
4. Update affected documentation and changelogs in both languages.
5. Do not create ZIP files unless explicitly requested.
