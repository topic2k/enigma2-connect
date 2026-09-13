[Deutsch](VALIDIERUNG.md) | [English](VALIDATION.en.md)

# Verification summary

Checked on **2026-09-13**. Verified release candidate: **1.0.0**.
This is a technical report, not release or hardware approval. Version history:
[changelog](../CHANGELOG.en.md). Reproduction commands:
[developer guide](DEVELOPMENT.en.md#development-environment-and-checks).

## Blog workflow 1.0.1

On 2026-09-13, the isolated workflow based on `main` / `1.0.0` passed 28 offline
tests under WSL/Python 3.14.7. They cover both assessments (compatibility and
improvements), source evidence, duplicate protection, request limits and failures
without issue publication. Ruff, formatting, Python syntax and offline lock
verification passed; the lockfile only changes the local project version to
`1.0.1` (154 packages). Four existing September posts and the source snapshot
fit into 230,009 UTF-8 input bytes. This is not a measured token count.

Gemini responses and GitHub writes are simulated in these tests. `GEMINI_API_KEY`
is stored as a repository secret. A real trial will run through GitHub Actions
after merging; its run report provides evidence of the live connection. The
weekly review proposes changes without editing integration code. These checks
do not provide a new receiver/interface acceptance test.

## Current local checks

The complete `1.0.0` release candidate was checked:

| Check | Result |
| --- | --- |
| Python tests with Home Assistant 2026.9.1 / Python 3.14.7 | 148 passed; 278.48 seconds; 92% statement coverage |
| Remote card JavaScript tests | 8 passed |
| Ruff lint, format check and Python syntax | passed |
| Local Hassfest against HA 2026.9.1 | 1 integration, 0 invalid integrations |
| Documentation links and YAML examples | 168 local references and ten examples valid |
| Version fields and offline lockfile check | synchronized; dependencies unchanged |
| Release and privacy validation | 84 Git-visible files; no local test data or private values included |

The Python tests use the real Home Assistant test framework with simulated receiver
responses and Internet providers. Local logs and reports are stored under `.work/`
and are not published.

### Previous development checks

| Check | Result |
| --- | --- |
| Python tests with Home Assistant 2026.9.1 / Python 3.14.7 | Full run: 147 passed, 1 failed; 276.28 seconds |
| Targeted rerun of the initially failing test | 1 passed; 1.53 seconds |
| Coverage in the full run | 90% statement coverage |
| Remote card JavaScript tests | 8 passed |
| Ruff lint and format checks | passed |
| Python syntax | passed |
| Local Hassfest against HA 2026.9.1 | 1 integration, 0 invalid integrations |

The full run also included the concurrently added thumbnail regeneration.
`test_regeneration_is_per_receiver_repeatable_and_survives_settings` failed in
that run and subsequently passed in a targeted rerun of the current working state.
No further complete suite run was performed afterwards.

Python tests use the real HA framework but simulate receiver responses and
internet providers. The FFmpeg test creates an artificial recording with a color
change and extracts real frames. It does not test a recording file on a receiver
or real TMDB/OMDb credentials. Card tests do not replace visual browser or mobile checks.

Documentation was compared with options, translations, actions, media browsers,
image preparation and error handling in the current code. Local links, heading
anchors, language links, YAML examples, version fields and the lockfile were
checked in the final review: 168 local references and ten YAML examples are valid. All 45 files in the original
documentation tree were verified with SHA-256 in the local archive. Active
branding sources and the font license were retained unchanged.

Local logs: `.work/docs-audit/pytest.log`, `ruff.log`, `format.log` and
`verification.log` plus `regeneration-recheck.log` in the same folder; Hassfest:
`.work/docs-restructure/hassfest.log`. These working files are not published.

## Existing hardware evidence

Earlier reports from 2026-09-13 cover the local `0.1.0` baseline, not the whole
current development version:

- **Octagon SF8008 4K Supreme, OpenWebif 2.4.0:** documented checks cover live
  TV/radio, recording playback, picons/screenshots, remote control, messages,
  timers/calendar, standby, GUI restart, reboot and deep standby. The card was
  checked on desktop, phone and tablet in light and dark themes.
- **Vu+ Solo², OpenWebif 1.4.4:** documented checks cover separate device targeting,
  setup without credentials, catalogs, remote control, messages and timers.
  Missing DVB input meant this was not a second acceptance test of video, audio,
  reception EPG or real recordings.

Original reports remain in the local documentation archive. No new receiver or
HA interface acceptance test was performed during this documentation revision.
The media tile, recording previews, background preparation and optional channel
folders in particular need suitable live checks in both interface languages for
current hardware approval.

## Publication and remaining limitations

Test, Hassfest and HACS workflows are present. A local run establishes neither
successful GitHub CI nor HACS approval for a release commit. Follow the checks
and explicit approvals in [RELEASING.en.md](../RELEASING.en.md) before publication.

Browser/Cast streaming, Wake-on-LAN, automatic discovery, creating recurring
timers and receiving screen-message answers are not implemented. Further edge
cases are covered in the developer guide.
