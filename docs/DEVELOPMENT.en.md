[Deutsch](ENTWICKLUNG.md) | [English](DEVELOPMENT.en.md)

# Developer guide

This guide collects the information needed to change Enigma2 Connect. For setup
and everyday use, see the [user guide](USER_GUIDE.en.md). The
[README](../README.md#english) remains a short introduction for users.

## Contents

- [Project and requirements](#project-and-requirements)
- [Development environment and checks](#development-environment-and-checks)
- [Monitor the Home Assistant developer blog](#monitor-the-home-assistant-developer-blog)
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

From the project directory on Linux/WSL with Python 3.14.2 or later:

```sh
uv sync --locked --group dev
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest --cov=custom_components.enigma2_connect --cov-report=term-missing
uv run --locked python -m compileall -q custom_components tests
node --test tests/frontend.test.cjs
git diff --check
```

`pyproject.toml` specifies direct development dependencies; `uv.lock` pins their
resolution. After a version change, run `uv lock --offline` and verify that only
the expected project metadata changed. Do not update dependencies incidentally.
A fresh environment needs access to package sources for its first sync.

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

## Monitor the Home Assistant developer blog

The [Home Assistant developer blog](../.github/workflows/ha-developer-blog.yml)
workflow checks the complete posts in the official
[blog repository](https://github.com/home-assistant/developers.home-assistant/tree/master/blog)
on **Mondays at 07:23 UTC**. It considers new and edited posts from **2026-09-01**.
Each run assesses at most **five posts together in one Gemini request**. No new
posts means no AI call. Additional posts remain pending for the next run; source
code is never silently truncated.

The [Gemini script](../scripts/ha_blog_gemini.py) uses Google's API directly with
`gemini-3.8-flash`. One fixed request avoids variable agent loops. There are no
tools, web searches, automatic retries or model fallbacks. Limits are 400,000 UTF-8
input bytes and 8,192 output tokens, including thinking tokens at thinking level `low`.
Oversized batches are reduced. If even one post with the complete code exceeds
the input cap, the run fails and requires manual review.

Google receives the blog text and an allowlist of publishable sources: integration
Python modules, manifest, translations, icons, quality checklist, service definitions, dashboard card,
project and HACS metadata. Local archives, `.env`, receiver data and test data are
excluded. Every new post is assessed; the former keyword filter does not select
posts for AI. The [heuristic script](../scripts/ha_blog_monitor.py) remains available
as an independent local tool, not as a silent substitute for AI.

Each post receives two independent assessments. Compatibility results are
`impacted` (concrete adaptation required), `no-impact` (no impact
identified), or `uncertain` (manual clarification required), with reasons, next
steps, HA versions/deadlines when stated and code references. File paths, line
numbers and exact source lines are validated locally. This verifies the citation,
not the AI's conclusion. The complete batch must be valid before an issue is
created. AI assessments do not replace Home Assistant compatibility tests.

Gemini also reviews **enhancements and improvements**: new features, usability,
performance, reliability and maintainability. The `opportunity` field contains
`recommended` (concrete proposal), `none` (no useful proposal) or `uncertain`
(requires investigation), with benefits, implementation steps, prerequisites and
tradeoffs. Recommendations require a validated source citation as an integration
point; the new API need not already be used. A `no-impact` post can therefore
still recommend an enhancement; required adaptations and optional improvements
can also coexist. Existing features and mandatory migrations are not enhancements.
Missing assessments or required evidence prevent report publication. Both reviews
use the same weekly request. Reports propose changes; implementation is decided
separately.

Each successful run with new posts creates **one combined report issue**, even
when all assessments are `no-impact`. Hidden markers durably record the reviewed
post content. Closed reports also count and are never edited or reopened; preserve
reports and markers. Content changes trigger another review, code-only changes
do not. Previous heuristic issues are not AI review receipts. The summary and
JSON reports are also retained as Actions artifacts for 30 days.

### Configure free Google access

1. In [Google AI Studio](https://aistudio.google.com/api-keys), create a key for a
   dedicated **Free Tier project without paid billing enabled**. Do not link a
   billing account or upgrade to a Paid Tier.
2. Check the active model limits in AI Studio. Google's
   [pricing page](https://ai.google.dev/gemini-api/docs/pricing#free) lists free
   input/output for Gemini 3.8 Flash; request/token limits are
   [project-dependent](https://ai.google.dev/gemini-api/docs/rate-limits).
   One small request per week is expected to fit but cannot be guaranteed before
   a real trial with that project. The Free Tier prevents paid usage; the workflow
   cannot inspect a key's billing status. A key from a Paid Tier project may incur costs.
3. In GitHub, open **Settings → Secrets and variables → Actions → New repository
   secret** and store the key as **GEMINI_API_KEY**. Never put it in files, issues
   or chat messages.
4. After an approved PR merges the workflow into `main`, open **Actions → Home
   Assistant developer blog → Run workflow** and select the default branch.
   Keep **Run Gemini and generate a report; do not create an issue** enabled for
   the first trial. This consumes AI quota but does not save durable review
   markers. Inspect the report and the JSON `usage` field.
5. Disable the dry-run switch to publish an issue manually. Scheduled weekly
   runs publish the combined report automatically.

Google processes the supplied sources under its Free Tier terms; the
[pricing page](https://ai.google.dev/gemini-api/docs/pricing#free) links to the terms
governing use of content for product improvement. Use only repository content
suitable for this disclosure.

HTTP 429, other API errors, a missing key or an invalid response fail the run
visibly. Posts without a saved report remain pending for the next run; there is
no automatic paid fallback. After an ambiguous issue publication response, the
next run finds any report that was already saved by its markers.

The publishing job only runs in the original repository on its default branch.
Pushes and PRs only run offline tests; forks do not publish reports. Permissions
are `contents: read` and `issues: write`; Actions and Issues must be enabled.
Concurrent runs are serialized. GitHub can delay schedules and disables them
for public repositories after 60 days without repository activity
([GitHub schedules](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)).

Local preparation without Google requests or GitHub writes:

```sh
python -m unittest discover -s scripts/tests -v
python scripts/ha_blog_gemini.py --blog-dir /path/to/developers.home-assistant/blog --prepare-only
```

Without `--prepare-only`, `GEMINI_API_KEY` is required and a real AI call may occur.
GitHub writes additionally require explicit `--publish`.


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
automatic discovery and creating recurring timers are also outside the current scope.

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
