[Deutsch](VALIDIERUNG.md) | [English](VALIDATION.en.md)

# Verification summary

Checked on **2026-09-13**. Shared development version: **1.1.0-dev.8**.
This is a technical report, not release or hardware approval. Version history:
[changelog](../CHANGELOG.en.md). Reproduction commands:
[developer guide](DEVELOPMENT.en.md#development-environment-and-checks).

## GitHub CI and the FFmpeg prerequisite

The first `quality-scale` push, commit `0fe1cb2`, passed
[Hassfest and HACS](https://github.com/topic2k/enigma2-connect/actions/runs/34771537254)
and the [blog-monitor tests](https://github.com/topic2k/enigma2-connect/actions/runs/34771537165).
The [test run](https://github.com/topic2k/enigma2-connect/actions/runs/34771537046)
passed Ruff, formatting, mypy and 269 tests; one test was skipped because FFmpeg
was missing. Consequently, the Silver coverage gate failed for
`recording_snapshot.py` at 92.45%, while config flow reached 100%.
Version **1.1.0-dev.8** explicitly installs FFmpeg and verifies its invocation in
CI. A successful run of this correction is established separately; coverage
thresholds and integration behavior remain unchanged.

## Physical DHCP address change: missing identity data

**Result after GUI restart: address adoption passed.** OpenWebif once again
reported the previously captured MAC and new address for `wlan0`. The explicitly
triggered DHCP handler adopted the address and reloaded the entry over HTTPS.
All 64 registered entity identifiers, device associations, credentials, port,
TLS settings and options were preserved; all nine platforms and 17 enabled
entities were available. Refresh, repeated discovery without another receiver
request and unloading passed with 13 read requests in total. The existing exception
for the untrusted certificate remained limited to the isolated test configuration.

The user changed the DHCP assignment on the router and restarted the Octagon's
network interface. Beforehand, its identity, connection settings and 64 registered
entities (17 enabled) were captured in an isolated HA instance. OpenWebif responds
at the new address even before the GUI restart; the local ARP entry confirmed the
same MAC as before the change. However, repeated `/api/about` responses contained
only `wlan0` with `mac: null` and `ip: 0.0.0.0`.

DHCP handling was explicitly triggered in an isolated HA instance using the real
new address and previously captured MAC. Before the GUI restart, it aborted with
`wrong_device` and did not adopt the address; protection against an unconfirmed
identity worked correctly. No actual DHCP network message
was captured. Registrations were reconstructed from the baseline in the test;
this is not acceptance of a continuously running production HA installation.

OpenWebif obtains adapter data from Enigma2's `iNetwork`; `/api/about` requests
full information. A stale or incomplete Enigma2 interface list is therefore a
plausible cause, but remains unconfirmed ([OpenWebif adapter data](https://github.com/E2OpenPlugins/e2openplugin-OpenWebif/blob/master/plugin/controllers/models/info.py),
[About endpoint](https://github.com/E2OpenPlugins/e2openplugin-OpenWebif/blob/master/plugin/controllers/web.py)).
The subsequent GUI restart performed by the user restored MAC reporting in this
attempt. The earlier assumption of a missing LAN adapter was incorrect; OpenWebif
identifies the interface as `wlan0`. A regression
test reproduces the actual incomplete response. All **11 discovery tests passed**
under HA 2026.9.1 / Python 3.14.7. The separate hardware check also confirms that
the original connection data and registered entity identifiers remain intact
when adoption is rejected. Local evidence:
`.work/quality-live/dhcp-baseline.json`, `new-identity.json`,
`dhcp-before-gui-restart.json` and `dhcp-changed.json`. Credentials are excluded
from these reports. Another twelve-second Bonjour observation after the GUI
restart found no matching service (`octagon-discovery-after-restart-Windows.json`).
Automatic receipt of an actual DHCP announcement in running HA and Bonjour setup
remain pending. Version **1.1.0-dev.7** updates documentation and version metadata;
the tested integration code is unchanged.

## Extended hardware and integration checks

On **2026-09-13**, the merged code after reconciling `main` through `640de18`
passed **269 integration tests** in **465.79 seconds**. Coverage remains
**99.70% statements**, **97.86% branches** and **99.29% combined**; configuration
flows achieve 100% in both measurements, and all 23 modules pass the Silver gate.
The **28 blog-monitor tests** also passed. Additional dependencies used for the
local UI check are not added to integration requirements or the lockfile.

**HTTPS on the real Octagon:** Strict verification rejects the untrusted
certificate. Only in the isolated test, `verify_ssl=False` was then used: HTTP
and HTTPS returned the same hardware identity, and HTTPS setup, all nine
platforms, refresh, duplicate prevention and unloading passed with 16 read
requests. This does not establish a trusted certificate chain; production TLS
settings were not changed.

**Live video/audio:** A sample of roughly 3 MiB from the already selected channel
was examined only in memory. FFmpeg decoded two H.264 frames at 1920 × 1080 pixels
and one second of six-channel AC3 audio at 48 kHz. The channel did not change,
and no content was saved. This verifies technical decoding, not subjective
picture/audio quality on a TV or speaker, nor HA stream playback.

**Real HA interface:** Using frontend 20260826.6 matching the HA version, the
Octagon device page, brand artwork, icons and three disabled signal diagnostics
were visually checked. Options menus and field descriptions display correctly
in German and English. A deliberately invalid FFmpeg path in the temporary HA
instance produced the expected repair issue and remediation text in both
languages. Deselecting the snapshot source through the options dialog reloaded
the entry; the repairs page then reported no pending repairs. Receiver credentials
and test configuration stayed local. Production HA settings and receiver control
states were unchanged. The test interface was subsequently stopped. Evidence:
`ui-server.log` and `ui-repair-server.log` under `.work/quality-live/`, plus browser
views inspected in this session. The missing FFmpeg path was a test condition;
receiver requests and the frontend were real.

**Bonjour:** A further twelve-second observation directly on Windows found no
HTTP/HTTPS announcement from this receiver. Real Bonjour setup evidence therefore
remains pending. Physical DHCP testing requires a controlled address change on
the router; the completed attempt and its identity issue are documented above.

**Recording thumbnail and controls:** The production snapshot path produced a
fully decodable JPEG at 640 × 360 pixels from an existing recording (17,007 bytes
after normalization). Transfer was capped at 64 MiB; no image content was saved,
and the channel and standby state stayed unchanged. Twelve subsequent checks
with bounded control actions passed: changing and restoring volume, muting
including repeated identical target states, a three-second screen message, and
creating, enabling, disabling and removing an owned future zap timer. Volume
and mute were restored; the six existing timers and seven recordings in the
non-recursive comparison list remained unchanged. There were no cleanup errors.
This verifies API controls; the message was not visually confirmed on the TV.
Evidence: `octagon-recording-image.json` and `controls-results.json` under
`.work/quality-live/`.

Evidence: `.work/quality-live/integrated-tests.log`, `coverage-integrated.json`,
`octagon-https.json`, `octagon-stream.json` and `octagon-discovery-Windows.json`.
Documentation and version metadata advance to **1.1.0-dev.5**.

## Current read-only Octagon acceptance

On **2026-09-13**, the current code was checked with a **real Octagon SF8008 4K
Supreme** over live HTTP. Environment: **Home Assistant 2026.9.1**, **Python 3.14.7**,
**OpenWebif 2.4.0**, image **7.6.0.20260831**, Enigma2 **2026-08-30**.
The first run on **1.1.0-dev.3** passed. The resulting **1.1.0-dev.4** changes only
documentation and version metadata.

| Check | Result |
| --- | --- |
| Setup with actual OpenWebif authentication | Passed |
| Platforms | All 9 loaded |
| Enabled entities | 17, with 0 unavailable |
| Signal diagnostics | All 3 disabled by default |
| Refresh and diagnostics export | Passed, no optional endpoint errors |
| Duplicate setup | Aborted as already configured |
| Unloading | Successful, config entry no longer loaded |
| Receiver requests during HA acceptance | 16, all read-only |
| Screenshot | JPEG, 720 × 405 pixels, fully decoded |
| Channel logo | PNG, 220 × 132 pixels, fully decoded |

The HA instance used isolated test fixtures and in-memory configuration storage;
receiver responses were real. Images were decoded only in memory and not saved.
No channel, volume, timer, recording or power state was changed.

A twelve-second Bonjour observation from WSL received no matching announcements.
The observation path means this does not establish that the receiver advertises
no services; Bonjour evidence remains pending. The subsequently completed HTTPS,
media, control and interface checks are described above. Automatic receipt of
actual DHCP announcements and subjective picture/audio checks remain pending.

Evidence: `.work/quality-live/octagon-acceptance-dev3.json`, `octagon-images.json`
and `octagon-discovery.json`. Credentials remain in the local, Git-ignored file
provided by the user and are not included in this validation overview.

## Addition: repeatable receiver acceptance

Build **1.1.0-dev.3**, **2026-09-13**: The new
[acceptance helper](DEVELOPMENT.en.md#read-only-receiver-acceptance) was checked on
HA 2026.9.1 / Python 3.14.7. **6 targeted tests passed**; directly running the
hardware test without acceptance configuration produced **one expected skip**.
The complete CLI invocation against a local **simulated HTTP receiver** passed
with 16 read requests, authentication, nine platforms, three disabled signal
diagnostics, refresh, duplicate prevention and successful unloading. Neither
the test password nor the authentication header appeared in CLI output or the
report. A closed local port correctly produced a failing exit status and
`passed: false`.

This addition changes no production integration code; the complete 263-test run
below still applies to its documented previous build. Ruff, formatting, syntax
and lock consistency were checked again. Evidence: `.work/quality-live/tests.log`,
`cli-smoke.log`, `simulated-cli.json` and `refused-final.json`.
This is **not new physical receiver acceptance**.

Read-only inspection found successful GitHub runs on remote `main` at
`f3a4e94de7cbc7f9fc6696fc72f5bfd075fd9cf8` for
[Tests](https://github.com/topic2k/enigma2-connect/actions/runs/34765832310) and
[Validate](https://github.com/topic2k/enigma2-connect/actions/runs/34765832294).
They do not validate the uncommitted changes on `quality-scale`; CI evidence
for their intended commit remains pending.

## Quality scale: integration validation

Local version **1.1.0-dev.2**, branch `quality-scale`, **13 September 2026**.
The internal checklist now marks **54 of 54 criteria implemented**. Formally this
remains a **custom integration**; an official tier requires a separate Home Assistant
review.

| Check | Result |
| --- | --- |
| Complete integration suite on HA 2026.9.1 / Python 3.14.7 | 263 passed; 480.66 seconds |
| Statements / branches / combined | 99.70% / 97.86% / 99.29% |
| Configuration flows | 100% statements and branches; CI gate passed |
| Silver gate per module | All 23 modules above 95% combined; minimum 96.25% |
| Strict mypy 2.3.1 | All 23 production modules pass |
| Ruff, formatting and Python syntax | Passed |
| JavaScript remote-card tests | 8 passed |
| Local Hassfest for HA 2026.9.1 | 1 integration, 0 invalid integrations |
| Lockfile | 159 packages; only local metadata and five mypy packages changed from the previous dependency set |

The full run includes Bonjour confirmation, DHCP identity, preserved TLS and
credentials, address conflicts, diagnostics without runtime data, partial/offline
receivers, repair recovery and independent device addition/removal. The eight
actual PNG files are served by HA's local brands API with no CDN calls; icon keys
match the entity catalog. The earlier assessment that a brands PR was necessarily
outstanding is superseded for this custom integration by [HA's 2026.3 change][local-brands].

Announcements, receivers and artwork providers are simulated. No new real Bonjour/
DHCP announcements, physical IP changes, receiver video/audio or HA interface
acceptance tests were performed. These hardware checks remain pending before a
corresponding approval. This is also not a new GitHub CI run. The separate blog
monitor script tests belong to their own validation below, not the integration
suite above.

Evidence: `.work/quality-final/full-tests.log`, `coverage.json`, `coverage-gate.log`,
`style-syntax.log`, `frontend.log`, `docs.log` and `hassfest.log`; mypy:
`.work/quality-final/static.log`. The earlier 260-test run and 51 targeted
checks are in `.work/quality-gold/`.

[local-brands]: https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/

## Additional blog monitor checks

On **2026-09-13**, version **1.1.0-dev.2**, the weekly Gemini variant passed
**28 offline tests** on Windows and WSL/Python 3.14.7: 16 for the AI integration
and 12 for the still-available
heuristic script. Checks include a single request without tools, input/batch
limits, duplicate protection including closed no-impact reports, rechecking
edited posts, invalid source paths/quotes and quota errors without saved success
markers. New checks cover recommendations despite `no-impact`, all combinations
of the two independent assessments, and missing assessments or invalid improvement
evidence preventing publication. Preparation using the existing real blog sources
selected four posts with **273,299 UTF-8 input bytes**, including instructions and
sources, below the 400,000-byte limit. This is a byte count, not a measured token count.

Ruff, formatting, Python syntax, workflow YAML/Bash, version consistency,
60 local documentation links and offline lock verification (159 packages) passed. Sources and
post selection were prepared locally; Gemini responses and GitHub issues were
simulated in tests. `GEMINI_API_KEY` has since been saved in GitHub; AI Studio
shows 20 requests per day and 250,000 tokens per minute for Gemini 2.5 Flash in
the free project. **No real Google API request and no GitHub Actions run**;
suitability for the actual request has not yet been verified in practice.
No additional HA/receiver checks for
this workflow-only change. Local preparation data:
`.work/blog-monitor/gemini-report/request-info.json`.

### Previous heuristic checks

On **2026-09-13**, version **1.0.1-dev.3**, scoped to the new workflow:

- Twelve offline tests passed on Python 3.14.7: API/topic matching, complete
  post text, dates/drafts, dry runs, paginated duplicate detection including
  closed issues, failures before/during publication, and the five-issue limit.
- Dry run against the actual official blog sources: four September posts
  assessed, three with code matches requiring review, one without matches.
  No issues created. Shared API examples can cause false positives.
- Workflow YAML and Bash syntax, twelve tests, project-wide Ruff, Python syntax,
  58 local documentation links and version metadata passed validation.
  `uv lock --check --offline` passed; only the local package version changed.

Reports: `.work/blog-monitor/report/summary.md` and `report.json`, including the
retrieved upstream commit in the JSON report. GitHub issue responses and errors
were simulated. No GitHub Actions run, actual issue publication or additional
HA/receiver validation was performed for this workflow change. The integration
checks below still refer to their own earlier version.

## Previous local Silver checks

Second stage: additional Silver requirements on `quality-scale`.

| Check | Result |
| --- | --- |
| Full integration run with HA 2026.9.1 / Python 3.14.7 | 242 passed; 423.49 seconds |
| Subsequently added receiver-without-MAC test | 1 passed; 9.76 seconds |
| Combined coverage from both runs | 99.68% statements; 97.81% branches; 99.25% combined |
| Silver coverage gate | All 23 integration modules above 95% combined; minimum 96.15% |
| Config flow | Still 100% statements and branches |
| Remote card JavaScript tests | 8 passed |
| Ruff, format check and Python syntax | passed |
| Local Hassfest against HA 2026.9.1 | 1 integration, 0 invalid integrations |
| Version fields and offline lockfile check | synchronized; dependencies unchanged |

The full integration run passed; one additional test for missing MAC metadata was
then added and run separately. Integration production code remained unchanged
between those runs. Coverage was combined using `--cov-append`. These are **243
integration checks across two runs**, not a new full run after adding the final
test. The concurrently added blog monitor is outside this section's test scope.

**Refresh lists** now waits for a completed fetch and reports connection failures.
New coverage includes lost power-command responses without retries, image and
decoder failures, download limits, cancellation cleanup, rapid channel changes,
invalid catalogs and repeated/skipped hours at timezone transitions. Transports
and image providers are simulated; the existing FFmpeg test uses a synthetic
recording file.

Evidence: `.work/quality-silver/full-tests.log`, `no-mac.log`,
`full-coverage.json` (full run), `coverage.json` (combined), `.coverage`,
`hassfest.log` and `frontend.log`. The ten additional Silver rules are internally
verified. External Bronze brands evidence remains open, so no complete or
official Silver rating is claimed. No new hardware, UI or GitHub CI acceptance
was performed.

### Previous Bronze stage for 1.0.1-dev.1

First quality improvement stage on the `quality-scale` working branch:

| Check | Result |
| --- | --- |
| Python tests with Home Assistant 2026.9.1 / Python 3.14.7 | 185 passed; 309.43 seconds |
| Config flow | 124/124 statements and 36/36 branches covered: 100% each |
| Overall coverage | 92.90% statements; 82.16% branches; 90.47% combined |
| Coverage gate | Complete report accepted; missing statements, branches, branch measurement and module evidence rejected |
| Quality checklist | All 54 rules present; valid HA 2026.9.1 schema |
| Remote card JavaScript tests | 8 passed |
| Ruff lint, format check and Python syntax | passed |
| Local Hassfest against HA 2026.9.1 | 1 integration, 0 invalid integrations |
| Documentation links and YAML examples | 182 local references and ten examples valid |
| Version fields and offline lockfile check | synchronized; only local package version changed |

Tests use the real HA framework with simulated receiver responses. No new
hardware, UI or GitHub CI acceptance was performed. Config-flow tests check
recovery within the same flow, identity and duplicate devices. An additional
runtime check confirms single failure and recovery log messages. Combined
coverage includes branches for the first time and is not directly comparable
with the earlier statement-only percentages.

Local evidence is stored in `.work/quality-scale/`: `full-tests.log`,
`coverage.json`, `.coverage`, `hassfest.log` and `frontend.log`.
The [quality checklist](../custom_components/enigma2_connect/quality_scale.yaml)
is an internal self-assessment. External brands evidence remains open for Bronze;
Silver through Platinum are not yet fully met. Next steps are described in the
[developer guide](DEVELOPMENT.en.md#quality-tiers-and-next-steps).

### Previous verification of 1.0.0

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

Browser/Cast streaming, Wake-on-LAN, creating recurring
timers and receiving screen-message answers are not implemented. Further edge
cases are covered in the developer guide.
