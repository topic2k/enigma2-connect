[Deutsch](ENTWICKLUNG.md) | [English](DEVELOPMENT.en.md)

# Developer guide

This guide collects the information needed to change Enigma2 Connect. For setup
and everyday use, see the [user guide](USER_GUIDE.en.md). The
[README](../README.md#english) remains a short introduction for users.

## Contents

- [Project and requirements](#project-and-requirements)
- [Development environment and checks](#development-environment-and-checks)
- [Read-only receiver acceptance](#read-only-receiver-acceptance)
- [Monitor the Home Assistant developer blog](#monitor-the-home-assistant-developer-blog)
- [Cloudflare trial](#cloudflare-trial)
- [Quality tiers and next steps](#quality-tiers-and-next-steps)
- [Structure and data flow](#structure-and-data-flow)
- [Implementation rules](#implementation-rules)
- [Documentation and changes](#documentation-and-changes)
- [Identity and data handling](#identity-and-data-handling)
- [Action validation](#action-validation)
- [Recorded ideas](#recorded-ideas)
- [Files and local archives](#files-and-local-archives)

## Project and requirements

Enigma2 Connect is a standalone Home Assistant custom integration for Enigma2
receivers using the OpenWebif JSON API. Its domain and component package are
`enigma2_connect`; the repository and Python project are `enigma2-connect`.
It targets Home Assistant **2026.9 or later** and Python **3.14.2 or later**.
Development uses Linux or WSL; Node.js runs the optional dashboard card's tests.

The project grew from an analysis of `homeassistant-enigma-player` and
`HAVUOpenWebif`. Integration logic was rewritten around a shared architecture.
Production code is licensed under [Apache-2.0](../LICENSE); see [NOTICE](../NOTICE)
and the [license review](LIZENZEN.md). Local research files and test tools in
`.work/` retain their respective licenses and are not published. The software
was developed with assistance from generative AI.

## Development environment and checks

FFmpeg must be on PATH for the actual recording-frame extraction test (on
Debian/Ubuntu: `sudo apt-get install ffmpeg`). Without it, this test is skipped
locally and the Silver coverage gate may fail. CI explicitly installs FFmpeg
and checks its invocation before running tests.

GitHub workflows use `actions/checkout@v7`, `astral-sh/setup-uv@v10.1.0` and
`actions/upload-artifact@v7` with the Node.js 24 action runtime. Hosted
`ubuntu-latest` runners support these versions. This does not change the
integration's Python requirements. Existing warnings in older workflow runs
remain part of their historical logs.
setup-uv uses its full release tag because the upstream repository does not
provide a `v10` major-version alias.

From the project directory on Linux/WSL with Python 3.14.2 or later:

```sh
uv sync --locked --group dev
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
uv run --locked pytest --cov=custom_components.enigma2_connect --cov-branch --cov-report=term-missing --cov-report=json:coverage.json
uv run --locked python scripts/check_config_flow_coverage.py coverage.json --silver
uv run --locked python -m compileall -q custom_components tests scripts
node --test tests/frontend.test.cjs
git diff --check
```

`pyproject.toml` specifies direct development dependencies; `uv.lock` pins their
resolution. After a version change, run `uv lock --offline` and verify that only
the expected project metadata changed. Do not update dependencies incidentally.
A fresh environment needs access to package sources for its first sync.

**Temporary security override:** Home Assistant 2026.9.1 and 2026.9.2 pin
`cryptography==48.0.1` and `pyOpenSSL==26.2.0`. To address
[CVE-2026-69247](https://github.com/pyca/cryptography/security/advisories/GHSA-g6cj-pr64-35w5),
`[tool.uv].override-dependencies` selects `cryptography==50.0.1` and
`pyopenssl==26.4.0` in the development environment. The second upgrade is necessary
because pyOpenSSL 26.2.0 requires cryptography below 49, while 26.4.0 supports 50.
This deliberately differs from Home Assistant's package metadata and is checked
by our integration tests; it is not a general HA compatibility certification.
When updating the HA test stack, remove the override once its requirements allow
patched cryptography from version 50, then recheck the lockfile and tests.
The custom integration does not install these packages itself; its manifest
requirements remain empty. Production HA installations retain their own package
versions, which this repository change does not update.

Python tests use the real Home Assistant framework with simulated receiver
responses and transports. They cover configuration, device targeting, platforms,
errors, calendars, recordings, media sources and translations. JavaScript tests
cover card registration, editing, button presses, repeats and language changes;
they do not replace visual checks.

The [tests.yml](../.github/workflows/tests.yml) and
[validate.yml](../.github/workflows/validate.yml) workflows run tests, Ruff,
Hassfest and HACS validation. Local results do not establish successful CI for a
later commit. [VALIDATION.en.md](VALIDATION.en.md) records scope, tested versions and
actual receiver/interface checks. Historical results apply only to their
documented build.

The existing local WSL environment can use `.work/run_tests.sh`; it is not part
of a fresh installation. On the Windows mount, `--capture=sys` avoids known
pytest capture issues. The validation document records further local paths and reports.

## Read-only receiver acceptance

After installing development dependencies,
[receiver_acceptance.py](../scripts/receiver_acceptance.py) loads the current code
in temporary Home Assistant and reads the explicitly selected receiver:

```sh
uv run --locked python scripts/receiver_acceptance.py --host RECEIVER --username root
```

The password prompt hides input. Automated callers can use `--password-env NAME`
to read an existing environment variable. Omit `--username` for anonymous access.
`--https` and `--port PORT` select the protocol and port; HTTPS verifies the
certificate. The default report is `.work/receiver-acceptance.json`; use
`--output PATH` to keep separate reports for each receiver.

Checks cover setup, all nine platforms, the three signal diagnostics disabled by
default, entity states, refresh, duplicate prevention and unloading. Optional
failures and unavailable entities are reported as endpoint names or counts to
account for standby and different receiver capabilities. `passed: true` confirms
the technical flow; assess these details separately for device acceptance.

The transport only allows the required read API calls. Background image generation
is deferred. Credentials and HA storage remain in memory; raw pytest logs are not
printed. The JSON report contains the test stage, exit status, versions, source
hash and technical summaries. Exit status 0 requires a completed flow; errors or
skipped execution cannot produce successful evidence.

This runs a real HA backend with test fixtures, not an existing HA installation.
UI, picture/audio, Bonjour and physical DHCP changes still require the separate
acceptance below. Normal pytest/CI runs do not contact receivers; directly running
the hardware test file without acceptance configuration skips the test.

## Monitor the Home Assistant developer blog

The [workflow](../.github/workflows/ha-developer-blog.yml) checks new or changed
posts in the official [blog repository](https://github.com/home-assistant/developers.home-assistant/tree/master/blog)
on Mondays at **07:23 UTC** (09:23 CEST / 08:23 CET). Each run analyzes at most
**five posts individually and sequentially using Junie**. Additional new posts
wait for the next weekly run. No due posts means no AI task.

### Assessment and report

Every post is assessed independently for **required adaptations** and **useful
optional enhancements**, including usability, capabilities, reliability and
maintainability. Mandatory migrations must not be repackaged as optional benefits.
Junie is instructed to explain its findings in German, give actionable next
steps and include every announced availability, deprecation and removal deadline.
New opportunities are considered even if the API is not yet used by the code.

Concrete impact or recommended enhancements require exact existing source lines
as integration points. A separate trusted job checks post identity, structure,
paths, line numbers and quotations against the source snapshot captured before
analysis. An AI assessment does not replace compatibility tests and can still
be semantically wrong.

Successful assessments are published together in a GitHub issue, including
no-impact findings. Content-based markers prevent duplicate analysis; closed
issues still count. Existing Gemini-era markers remain compatible. Code changes
alone do not trigger another assessment. Reports and structured results are
retained for 30 days in the `ha-developer-blog-report` artifact.

### Retries and permissions

The [Junie monitor](../scripts/ha_blog_junie_monitor.py) reuses the established
[state and retry logic](../scripts/ha_blog_scheduler.py). A first failure queues
only the affected post for the next day and leaves the run successful. Other
weekdays at 07:23 UTC retry only due stored posts. A second failure of the same
post fails the run. Missed retries are caught up later. Exhausted entries require
an explicit manual retry.

The `ha-blog-monitor-state` branch stores `.github/ha-blog-state.json`, containing
post text, original blog revision, attempts, due date and sanitized error detail.
Attempts are reserved before AI work to avoid silently spending credits again
after interrupted runs. Successful partial reports are retained. Unsafe state
persistence is an infrastructure error and is reported immediately.

Planning, analysis and publication run in separate jobs. Only planning and
publication have write permissions for state and issues. Junie receives **no
write-capable GitHub token**. Publication independently downloads the original
plan, revalidates agent output and refuses to overwrite concurrently changed
state. Pushes and pull requests run offline tests only. Publication is restricted
to the original repository and default branch; manual dry runs also work on
work branches. Workflow runs are serialized.

### Access, costs and operation

1. Create a CLI token in the [Junie account](https://junie.jetbrains.com/tokens)
   and save it as the repository secret **JUNIE_API_KEY**. Never put the token in
   code, issues or chat. Keep existing JetBrains credits available.
2. Under **Actions → Home Assistant developer blog → Run workflow**, keep
   **Run Junie without publishing issues or changing retry state** enabled for
   a dry run. It consumes credits but changes neither issues nor attempt counts.
   For manual publication, disable it and select the default branch.
3. **Retry exhausted entries only** explicitly retries terminally failed posts.
   It also supports dry runs.
4. Review the assessment and **model costs reported by Junie**. Totals come from
   `llmUsage[].cost`, model names from `llmUsage[].model`. Missing usage is shown
   as unknown. These USD values do not establish actual JetBrains credit deductions.

Production runs **Junie CLI 3110.6** directly, the same version tested through the
official action. This gives separate control over per-post tasks, artifacts and
error handling. JetBrains determines the default model, which may change; the
first trial used Gemini 3.7 Flash and smaller helper models. One agent task can
make multiple model calls. Each post has a five-minute process timeout, **not a
hard credit cap**. No immediate retry, automatic Google/Cloudflare fallback or
credit purchase is performed.

Junie receives public blog content and the established allowlist: integration
Python files, manifest, translations, services, quality checklist, frontend card
and project metadata. Analysis runs on a GitHub runner with the public repository.
Plan and result artifacts are retained for seven days; raw Junie session logs are
not uploaded by the production workflow. The heuristic script remains a separate
local aid and does not prefilter posts for AI analysis.

Offline checks: `python -m unittest discover -s scripts/tests -v`.
Production no longer needs Google or Cloudflare credentials. Historical provider
trials are documented in the [verification summary](VALIDATION.en.md).

## Cloudflare trial

Set `cloudflare_individual=true` to analyze each stored post separately with
the same complete source snapshot. `cloudflare_post` selects one exact stored
filename. At most five requests run sequentially; an error stops the test while
retaining completed results and usage in the artifact. Separate requests multiply
input usage; the daily free-tier limit still applies.

**Trial status 2026-09-16:** API calls succeeded yesterday, but today returned
HTTP 429/4006 despite a 0/10,000 dashboard counter. Batch analysis mixed up
explanations; the Modbus per-post assessment omitted a deadline. Remaining
individual trials stopped due to API rejection. Not approved for scheduled use. Results:
[validation overview](VALIDATION.en.md).

The manual workflow input `cloudflare_test=true` tests stored posts using
`@cf/openai/gpt-oss-120b`. It requires the `CLOUDFLARE_API_TOKEN` secret
(Workers AI Read/Edit for one account) and the `CLOUDFLARE_ACCOUNT_ID` Actions
variable. Use Workers Free without upgrading to paid billing. The trial reads
the state branch, sends the same allowlisted source snapshot and validates
responses using the existing evidence checks. It writes only the
`ha-blog-cloudflare-test` artifact, without issues or retry state updates.
Batch mode makes one request; individual mode makes one per post.
There is no automatic provider fallback.
`cloudflare_smoke=true` limits the trial to a small connection check. The artifact
also includes the provider response for offline re-evaluation; request headers
and the token are not stored. The scheduled Gemini
monitor remains unchanged; quality and availability still need evaluation.


## Quality tiers and next steps

Enigma2 Connect remains a **custom integration without an official quality tier**.
The [HA quality scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
guides development. The complete
[rule checklist](../custom_components/enigma2_connect/quality_scale.yaml) records
implementation and outstanding evidence separately. `done` is an internal
assessment; an official tier requires review by Home Assistant. Use exemptions
only when the rule permits them and evidence supports the reason. Uninvestigated
items remain `todo`.

The first stage adds field descriptions and tests for setup, reauthentication,
reconfiguration and options. Tests specifically cover recovery in the same flow,
host/MAC duplicates, wrong devices and receivers without MAC identity. Additional
runtime tests verify action registration without an entry and single failure and
recovery log messages. CI now measures **statement and branch coverage** and
requires 100% of each for `config_flow.py`. This combined coverage is not directly
comparable with previous statement-only figures. Current results are recorded in
[VALIDATION.en.md](VALIDATION.en.md).

The second stage adds transport, control, calendar, image-provider and snapshot
failure tests to the regular suite. Previously local-only tests for rapid channel
changes and cancelled screenshot requests now also run in CI. **Refresh lists**
waits for an immediate fetch instead of a potentially deferred update and reports
its failure. CI additionally requires **above 95% combined statement/branch
coverage in each of the 23 integration modules**; a missing module or exactly 95%
fails the check. Config flows still require 100% of both measures.

The third stage adds discovery, verified DHCP address updates, resilient
diagnostics, device lifecycle tests, translated repair issues and icons. All 23
production modules have complete function signatures and use `EnigmaConfigEntry`.
`uv run --locked mypy` enforces `strict = true`; no modules are excluded and missing
import types are not globally ignored. `follow_imports = "silent"` suppresses
diagnostics from dependencies while retaining their type information. `JsonObject`
describes flexible, image/version-specific receiver metadata; fixed state and
service models are dataclasses. Overloads distinguish image bytes, JSON objects
and optional lists. The bundled package includes `py.typed`.

The network client uses an injected HA-managed `aiohttp` session. Recording artwork
delegates file access, FFmpeg path lookup and Pillow operations to
`async_add_executor_job`. FFmpeg runs as an asynchronous subprocess; transfer limits,
timeouts, process termination and relay cleanup are tested. Parsing bounded JSON
responses remains in-memory work with no synchronous network or filesystem access.

**Correction to the earlier brands assessment:** Since HA 2026.3, custom integrations
can officially include local `brand/` files. The eight shipped PNGs follow this path;
a separate brands PR is no longer required for this custom integration. Sources:
[HA announcement][quality-local-brands] and [brands repository][quality-brand-requirements].
This is an internal assessment of the current custom integration, not a Core review.

| Tier | Local status and remaining evidence |
| --- | --- |
| Bronze | All 20 criteria implemented internally, including local brands. Flows must retain 100% statement and branch coverage. |
| Silver | All 10 additional criteria implemented internally; each of the 23 Python modules must retain above 95% combined coverage. |
| Gold | All 21 additional criteria implemented internally. An actual DHCP address change passed with an explicitly triggered HA handler; actual Bonjour announcements and automatic DHCP receipt in running HA remain pending. |
| Platinum | All three additional criteria implemented internally: async client, injected session and strict typing enforced in CI. CI evidence applies to the commits named in the verification summary; releases require another check of the final commit. |

### Discovery and device lifecycle

OpenWebif registers HTTP/HTTPS services through Bonjour or Avahi; see its
[upstream implementation][quality-openwebif]. The manifest limits new discoveries
to Bonjour names `openwebif*` on `_http._tcp.local.` and `_https._tcp.local.`.
Avahi announcements without that name do not establish OpenWebif identity and
do not trigger generic web-server discovery. Manual setup remains available.
DHCP watches only registered MAC addresses. A successful `about` response confirming
the saved identity is required before adopting an IP. Authentication errors,
missing MAC metadata and different hardware preserve the saved configuration;
port, TLS policy and credentials are unchanged. Flow behavior is tested; actual
network announcements have not yet been verified.

Each entry owns exactly one receiver; channels and recordings are not additional
devices. Adding another entry creates its entities without restarting HA. Offline
receivers stay registered. The permanent removal path is deletion of the receiver's
integration entry: HA removes its device/entity associations and the integration
deletes its repair issue. Other receivers remain intact. This is the tested removal
path for this single-device architecture; hub reconciliation or automatic deletion
after an outage would be inappropriate.

Connectivity and catalog refresh are diagnostics, as are signal quality, SNR and
BER. The latter three start disabled for new entities; existing user choices are
preserved. Connectivity uses `CONNECTIVITY`. Percentage quality, signal-to-noise
ratio and the receiver's unnormalized BER have no additional semantically suitable
device class: SNR is not RSSI power and BER is not an invented percentage. Standby,
recording and streaming retain their own states and icons. Device-class icons are
not overridden. User-facing action failures use translation keys; internal parser
errors are translated at the HA boundary rather than exposed directly.

Missing FFmpeg with snapshots selected creates an issue per receiver. Installing
it or fixing the path and reloading, or deselecting snapshots, clears the issue.
Ordinary receiver outages do not create additional repair issues. Authentication
continues through the existing HA reauthentication mechanism.

[quality-local-brands]: https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/
[quality-brand-requirements]: https://github.com/home-assistant/brands/blob/master/README.md
[quality-openwebif]: https://github.com/E2OpenPlugins/e2openplugin-OpenWebif/blob/master/plugin/httpserver.py

Every tier requires all preceding tiers. For each completed stage, update the
version, lockfile, both changelogs and documentation under the project rules;
rerun tests, Ruff, syntax checks and Hassfest. Additionally verify reception,
picture, sound and new discovery flows on real receivers and record the exact
scope. Automated tests use simulated receiver responses.

Core inclusion is a separate project: first establish the API library architecture,
dependencies, HA brands, official user documentation and Core review requirements.
Development does not claim an official tier in the manifest. Merge and publication
remain subject to the approvals in [RELEASING.en.md](../RELEASING.en.md).

The following acceptance checks remain before hardware/publication approval:

- [x] Tested the current integration code in an isolated HA backend with the real
  Octagon; versions and scope are in the [validation overview](VALIDATION.en.md#current-read-only-octagon-acceptance).
  Setup, nine platforms, refresh, duplicate prevention and unloading passed;
  this does not include visual inspection of an installed HA interface.
- [x] Checked the Octagon HTTPS read flow and rejection of its untrusted certificate;
  the exception remained limited to the test.
- [x] Technically decoded video and audio from a short live-stream sample without
  changing channels or saving content; subjective playback checks remain pending.
- [ ] Verify an actual Bonjour announcement including name, HTTP/HTTPS and port;
  confirm setup, repeated announcements and manual setup.
- [x] Verified a real DHCP address change with explicitly triggered HA handling:
  matching MAC after GUI restart, retained identifiers, credentials and TLS.
  Missing MAC correctly blocked adoption beforehand; wrong identity and address
  conflicts are additionally covered by simulations; see the [report](VALIDATION.en.md#physical-dhcp-address-change-missing-identity-data).
- [ ] Verify automatic receipt and handling of an actual DHCP announcement
  in a continuously running HA installation.
- [x] Checked new icons, disabled signal diagnostics, options dialogs and FFmpeg
  repair in the real test interface; text and remediation in German and English.
- [x] Generated and decoded artwork from an existing recording; checked volume,
  mute, message submission and an owned temporary timer. Verified restoration
  of the original state and preservation of existing timers/recordings.
- [x] GitHub CI passed for `ffdf007`: tests including FFmpeg and the coverage
  gate, frontend, Hassfest and HACS; evidence in the
  [verification summary](VALIDATION.en.md#github-ci-and-the-ffmpeg-prerequisite).
  Separate PR/merge and release approvals still apply as described in the release guide.

## Structure and data flow

| Area | Responsibility |
| --- | --- |
| `custom_components/enigma2_connect/__init__.py` | Set up config entries, load and unload platforms |
| `api.py` | OpenWebif access, authentication, TLS, response validation and serialized commands |
| `models.py` | Data models, normalization, device identity and timer calculations |
| `coordinator.py` | Shared status requests, catalogs, timers and recordings |
| `config_flow.py` | Setup, reauthentication, reconfiguration and options |
| `entity.py` and platform modules | Shared device association and Home Assistant entities |
| `services.py` / `services.yaml` | Device action validation and descriptions |
| `recordings.py` / `media_source.py` | Recording folders, titles and shared media tile |
| `channel_media.py` | Optional channel folders, receiver ownership and authenticated picons |
| `recording_images.py` / `recording_snapshot.py` | Recording previews, image providers, private cache and bounded FFmpeg extraction |
| `diagnostics.py` | Diagnostics export restricted to allowed technical fields |
| `strings.json` / `translations/` | Text, errors and German/English translations |
| `www/enigma2-connect-remote-card.js` | Separately installed dashboard card |
| `tests/` | Python and JavaScript regression tests |

Each config entry represents one receiver. Its typed `runtime_data` holds an
`EnigmaCoordinator`, which uses the OpenWebif client with a shared Home Assistant
HTTP session and provides snapshots to nine platforms: `media_player`, `remote`,
`notify`, `select`, `sensor`, `binary_sensor`, `camera`, `calendar` and `button`.
The manifest declares `device` and `local_polling`. No additional runtime packages
are declared.

Status, signal and EPG share the configurable polling cycle, normally 15 seconds.
Timers and recordings normally refresh every 120 seconds, channel catalogs every
300 seconds. List actions can trigger earlier updates. Screenshots load on demand
and use a five-second cache.

The dashboard card calls only Home Assistant's `remote.send_command` and uses no
receiver credentials. The [user guide](USER_GUIDE.en.md#dashboard-remote) explains
card installation and updates.

## Implementation rules

The regenerate action stores a random per-receiver `recording_image_generation`
value, included in thumbnail URLs and cache keys. `OptionsFlowWithReload`
stops old jobs and restarts bounded preparation. Old files remain subject
to the existing cache limit; other receivers are unaffected. Normal option
saves preserve the generation value.

Bouquet options use a fixed name dropdown (`custom_value=False`) so HA renders
the selected value as a label. The stored value remains the service reference.
Missing saved entries are retained with their bouquet file name as a fallback;
the empty selection remains available.

### Recording images

Frames require an FFmpeg executable inside the HA runtime; Enigma2 Connect does
not install it. When HA's FFmpeg integration is loaded, its `binary` is used;
otherwise `ffmpeg` is resolved through the HA process's search path. Configure
a custom path using `ffmpeg_bin` in HA's FFmpeg configuration. The executable
must be accessible inside the actual runtime, including inside the container
for container installations. Restart HA after changing its configuration.
This configures FFmpeg, not Enigma2 Connect through YAML. Also check OpenWebif
file access and the selected snapshot position when diagnosing failures.

Media browsers receive a relative, authenticated HA image URL containing the
receiver ID, a recording-reference hash and a settings hash. The HTTP endpoint
checks the recording against the current catalog. Credentials and recording
paths are absent from both image URLs and FFmpeg arguments.

`recording_images.py` only calls selected providers. External images are limited
to five MiB and stored as JPEGs of at most 640 × 640 pixels. HTML, external SVGs
and HTTP redirects are not accepted. The cache under
`.storage/enigma2_connect_thumbnails/<entry_id>/` holds at most 128 images per
receiver, valid for seven days. Concurrent requests for the same recording share
a job; each receiver runs one image generation job at a time.

A background queue starts after platform setup. Existing catalog refreshes
reconcile it even when lists are unchanged, also checking retry deadlines and
cache expiry. Newer recordings come first; preparation is limited to the newest
128 entries. Jobs are spaced by five seconds and pending image requests take
priority. Deleted entries leave the queue; unloading cancels both the worker and
image jobs. No additional receiver polling loop is introduced.

Ongoing recordings are identified by timer filename and state, with a conservative
fallback using receiver status, file age and duration. Snapshots wait for their
configured position; completed short recordings use the midpoint.
`tests/test_recording_preparation.py` covers startup, catalog refreshes, priority,
ongoing recordings, cache reuse and expiry, retries, bounded archive preparation
and unloading with simulated receiver/image responses.

`recording_snapshot.py` provides FFmpeg with a temporary loopback endpoint. This
reads only the selected file through OpenWebif `/file?action=download&file=…`,
including HTTP Range requests. Execution is limited to 45 seconds and a total of
64 MiB of video data. A timeout, unreadable file or missing FFmpeg falls back to
the next selected provider or the neutral placeholder. Unloading cancels pending jobs.

`tests/test_recording_images.py` covers options, disabling, provider fallback,
caching, size limits, authentication and cancellation. The FFmpeg test creates
a synthetic MPEG-TS file with a color change and verifies real images at two and
ten minutes through a local HTTP file server supporting Range requests. This
single test is skipped when FFmpeg is absent. TMDB/OMDb responses and receivers
are simulated; this does not establish testing with real API keys or a recording
file on receiver hardware.

### General rules

Optional channels use `Snapshot.media_channels`. A dedicated media bouquet loads
with regular channel catalog refreshes without switching the source bouquet.
An empty selection reuses the source catalog. Failure of the additional bouquet
request does not make normal receiver control unavailable.

Channel IDs contain the receiver ID and a hash of the service reference. Playback
and the picon endpoint validate enabled browsing, the current catalog and receiver
ownership. Picons reuse local reference/name lookup; the browser receives only
the HA image URL. The memory cache holds at most 256 images, for 15 minutes on
success or two minutes for placeholders; at most four picon requests run at once.
`tests/test_channel_media.py` covers options, independent bouquets, both media
views, playback through HA, receiver ownership, authentication, caching and missing
picons with simulated receiver responses. Channel images are not prefetched.

- Centralize polling in the coordinator instead of adding per-entity polling
  loops. Serialize mutations and complete key sequences so parallel automations
  do not interleave remote buttons.
- Use existing HA actions for standard controls (`media_player.*`,
  `remote.send_command`, `notify.send_message`, `select.select_option`,
  `button.press`, `camera.snapshot`). Custom device actions require an explicit
  `device_id`; never silently choose the first receiver.
- Distinguish unavailable optional data from empty lists. Connection failures
  must not appear as standby; authentication failures trigger reauthentication.
  Do not retry restart or shutdown commands after an uncertain response.
- Keep credentials in request headers. Do not log credentials, raw responses or
  message contents. Use an allowlist for diagnostics exports.
- The recordings tile serves all receivers. Its layout option is saved across
  entries. Playback must validate the receiver that owns the recording;
  resolving a recording does not provide a browser or Cast stream.
- Firmware does not reliably report pause state. Do not present assumed playback
  state as confirmed pause or timeshift feedback.
- Maintain backend text and translation keys together. The card uses the profile
  language; recording titles and automatic entity names use the HA system language.
  Fall back to English for unsupported languages; preserve receiver-provided text.

### Recurring timers and daylight-saving transitions

Receiver-supplied timestamps take priority. Further weekly occurrences are
calculated in the receiver's time zone. Nonexistent spring start/end times are
skipped; projected occurrences use the first occurrence of a duplicated autumn
time. If the clock change leaves a timer without a positive local wall-clock
duration, later occurrences use its actual elapsed duration. Calendar expansion
does not change receiver timers. Compare edge cases with the actual firmware.
Deleting or toggling a timer requires its original values, not those of an
expanded calendar occurrence.

## Documentation and changes

Before editing, understand the existing code and behavior and write a short
implementation plan. Preserve unrelated existing changes. Afterwards, run tests,
check syntax and locally available HA compatibility, and update affected
documentation in both languages.

Documentation has three entry points:

- `README.md`: a shared short user overview, requirements, first steps and links;
  German first, followed by English.
- `docs/BENUTZERHANDBUCH.md` / `docs/USER_GUIDE.en.md`: complete setup, everyday use,
  options, automations and troubleshooting instructions.
- `docs/ENTWICKLUNG.md` / this document: developer information and links to deeper
  technical documentation and verification reports.

The README offers jump links to both languages; separate language files for other
documents link to their counterparts. Version history belongs only in
the two changelogs. The binding [project instructions](../AGENTS.en.md) define
automatic version increases. Keep the manifest, `pyproject.toml`, local package
entry in `uv.lock` and both changelogs synchronized.

Work on `develop` or a working branch. Merging into `main` requires explicit user
approval and a pull request. A current remote/tag/release comparison is required
before the PR. A release needs a separate explicit request. Follow the full
[release guide](../RELEASING.en.md). Do not create ZIP files unless explicitly requested.


## Identity and data handling

Device identity uses a normalized usable MAC address, falling back to a normalized
host. Change addresses through Reconfigure. MAC-based entries verify identity;
a host fallback cannot detect replacement hardware behind the same address.

The first successful coordinator refresh precedes platform setup.
`OptionsFlowWithReload` applies option changes. The coordinator uses
`always_update=False`; missing optional lists are `None`, not empty lists. The
connection binary sensor remains available as a request-status indicator.
Optional endpoints are retried and authentication errors remain visible. Bouquet
changes and polling share a data lock; new channel lists are published only after
successful retrieval.

Recording retrieval uses `movielist` with `recursive=1`. Navigation reflects the
returned file paths; it does not independently scan network drives. Recording
dates and times use the HA time zone. Current channel state comes from the
receiver response, not optimistic local selection. In screenshot mode, the first
image request waits at least one second after a detected channel change; this
does not guarantee a finished image on every firmware.

Signal values are normalized. An integer percentage substitute in a dB field is
not published as a real dB reading; BER has no invented unit. Temperature, free
RAM/disk space and uptime are not implemented. Browser/Cast streaming, Wake-on-LAN,
and creating recurring timers are also outside the current scope.

## Action validation

Action names and usage examples are in the
[user guide](USER_GUIDE.en.md#actions-and-examples).

Custom device actions have no implicit default device. Their schemas are in
`services.py` and `services.yaml`. The notify entity uses the receiver's message
options; `enigma2_connect.message` uses its own action values instead
(defaults: type 1, duration 10 seconds).

Timer actions accept Unix timestamps or ISO dates with a time zone offset.
Deleting and toggling use the original receiver timestamps; successful timer
actions invalidate the lists.

Remote commands accept named keys from `const.py` and numeric Linux keycodes
from 0 to `0x2FF`. `hold_secs > 0` sends OpenWebif's `long` key type; firmware
controls actual duration. A channel number sends digits followed by OK. Obtain
service references from OpenWebif; `/api/bouquets` supplies bouquet references.
The current options interface uses a fixed name dropdown and retains previously
saved custom references.

## Recorded ideas

These ideas are tentative; priorities are an assessment, not a commitment for
the next version. Existing parts of the proposed features are identified below.

### Extensions from the OpenWebif research

The research of 13 September 2026 into
[oe-alliance/OpenWebif](https://github.com/oe-alliance/OpenWebif) identified the
following opportunities. Interfaces were examined through documentation and
source code; this does not establish that their additional functionality has
been tested on the two test receivers or in a real HA installation. Check
support and response formats for each OpenWebif version and image before implementation.

| Priority | Idea | Benefit, interface and limitations |
| --- | --- | --- |
| High | Search EPG and record results directly | Find programmes by title, search repeat broadcasts and record results without entering times manually. Uses `epgsearch`, `epgsimilar`, `timeraddbyeventid`. Current/next programme display already exists; search and recording a result would be added. [EPG API][ideas-api] |
| High | Edit timers and create weekly schedules | Extend existing timers and set weekdays, recording folders and tags. Creation, deletion, enabling/disabling and read-only calendar recurrences already exist. Extend through `timerchange` and `repeated`; distinguish individual calendar occurrences from the entire receiver timer. [Timer implementation][ideas-timers] |
| High | Expose recording conflict details | Display conflicting programmes and times and make them available to automations. OpenWebif returns structured `conflicts` when creating/editing timers. This would extend current error handling, not establish a separate conflict prediction API. [Timer implementation][ideas-timers] |
| High | Dedicated instant recording action | Dashboard button or voice action to record the current programme through `recordnow`. Event mode requires EPG; the alternative mode called “infinite” is limited to ten hours in the examined code. [Timer implementation][ideas-timers] |
| High | Extend the recording library | Recording folders and the HA media source now exist. Further additions: tags/filters, metadata such as file size and previous playback progress, plus renaming, moving and deleting. OpenWebif offers `movielist`, `fullmovielist` and management actions. Account for image-specific deletion/trash behaviour. [Recording management][ideas-movies] |
| Medium | Disk space and system diagnostics | Monitor free recording space; add RAM and uptime as optional diagnostic sensors. `about` supplies the underlying information. Normalize units and poll slowly; reported free RAM includes buffers and cache in the examined code. [Information model][ideas-info] |
| Medium | Select audio tracks | Select original audio, another language or audio description through a dynamic `select` entity. Uses `getaudiotracks` and `selectaudiotrack`; refresh choices after channel changes. [Audio API][ideas-api] |
| Medium | Explicit timeshift controls and status | Start/stop actions and a timeshift-active indicator through `tsstart`, `tsstop`, `tsstate`. `timeshiftEnabled` does not reliably indicate pause; the examined stop path suppresses the save prompt. [Controller][ideas-controller] |
| Medium | Playback position for recordings | Display progress and remaining time in the media player. The already queried `getcurrent` returns a position in seconds for certain local recordings. This alone does not reliably establish pause state. [Controller][ideas-controller] |
| Medium | Receiver sleep timer | “Standby in 30 minutes” with status display through the receiver's own `sleeptimer`. Available fields and behaviour vary by image. [Timer implementation][ideas-timers] |
| Optional | Power on without waking the television | For radio or background automations: `supports_powerup_without_waking_tv` and `set_powerup_without_waking_tv` are documented. Check image support; this does not replace waking from deep standby. [Control API][ideas-api] |
| Optional | Send text to input fields | Enter search terms directly instead of sending individual remote keys. `remotecontrol` accepts a `text` parameter; the active receiver input field determines where it goes. [Controller][ideas-controller] |
| Larger project | Play live TV and recordings on other devices | Extend the existing recording media source with verified browser/Cast playback and live TV. OpenWebif provides stream/playlist endpoints including an HLS entry point. Address codec support, authentication and possibly transcoding separately; an API endpoint does not establish playback compatibility with every target device. [Streaming endpoints][ideas-controller] |

A possible first phase is **instant recording → timer editing with conflict
details → EPG search with a recording action**. This is a suggested order, not
an implementation request.

[ideas-api]: https://github.com/oe-alliance/OpenWebif/wiki/OpenWebif-API-documentation
[ideas-timers]: https://github.com/oe-alliance/OpenWebif/blob/main/plugin/controllers/models/timers.py
[ideas-movies]: https://github.com/oe-alliance/OpenWebif/blob/main/plugin/controllers/models/movies.py
[ideas-info]: https://github.com/oe-alliance/OpenWebif/blob/main/plugin/controllers/models/info.py
[ideas-controller]: https://github.com/oe-alliance/OpenWebif/blob/main/plugin/controllers/web.py

### Other recorded ideas

**Generate snapshots on the receiver:** An optional service or Enigma2 plugin
could use receiver-side FFmpeg to supply a frame. Retain per-receiver position
settings and avoid starting playback. Evaluate decoders, processing capacity,
installation/updates, authentication, restricted file access, caching, ongoing
recordings and standby first. The normal screenshot endpoint does not replace
frame extraction from an arbitrary recording file.

**Interactive messages:** Answers to yes/no questions are not available in HA.
A later extension could use `messageanswer`. Configurable default answers,
choices such as “Now/Later/Cancel” and distinguishable timeouts need a suitable
receiver interface. Evaluate question/answer association, simultaneous dialogs
and firmware differences first; the last answer alone does not establish manual
confirmation. Starting points:
[OpenWebif message model](https://github.com/E2OpenPlugins/e2openplugin-OpenWebif/blob/master/plugin/controllers/models/message.py)
and [Enigma2 dialog](https://github.com/openatv/enigma2/blob/master/lib/python/Screens/MessageBox.py).

## Files and local archives

`docs/` holds the user and developer guides in German and English, the bilingual
[verification summary](VALIDATION.en.md) and the retained
[license record with source revisions](LIZENZEN.md). The German license assessment
is a dated provenance record, not new legal advice.

Active logo sources, the required font with its OFL license and the export script
are in [assets/branding](../assets/branding/README.md). The eight finished runtime
PNGs stay in the component's `brand/` folder. Version history and release workflow
remain in the changelogs and release guides at the project root.

Earlier analyses, feature comparisons, detailed historical reports, source
inventories and logo concepts exist only in the local `.local-archive/` folder.
The complete pre-cleanup state was preserved and verified with SHA-256; each
archive contains an `inventory.json`. `.gitignore` excludes this folder. It is
therefore unavailable in a fresh clone and needs a separate backup when required.
Existing Git history is not rewritten by this change.

Publish only `custom_components/enigma2_connect` as the integration; provide the
optional card under `www/` separately. Exclude `.work/`, `.local-archive/`, local
test environments and caches. Required instructions must not exist only in the
local archive. Before a PR, inspect new files and removed old paths as well;
`git diff --check` alone checks neither untracked files nor documentation links.

## Manual Junie trial

The dispatch input `junie_test=true` assesses exactly the stored Modbus post
dated 2026-09-02 using the repository secret `JUNIE_API_KEY`. The official action
v1.7.9 is pinned to a commit and uses `silent_mode`, Junie CLI 3110.6 and the
default model. GitHub permissions are read-only.

Existing state is only read. One analysis task assesses required adaptations
and optional improvements in German. Result structure and source citations are
validated afterwards; semantic correctness still requires manual review.
The `ha-blog-junie-test` artifact is retained for seven days. The Junie step
has a six-minute timeout. This is not a hard credit limit; one agent task can
make multiple model calls. No automatic retry, provider fallback or weekly
activation. The trial uses existing credits; it purchases none and changes no plan.

Status on 2026-09-16: the Modbus trial succeeded and included every deadline.
Junie reported about USD 0.048 in model costs; its default model was Gemini
3.7 Flash. The top-up deduction is not yet confirmed. Production execution and further relevance cases are validated separately. See [verification summary](VALIDATION.en.md).
