[Deutsch](CHANGELOG.md) | [English](CHANGELOG.en.md)

# Changelog

## Contents

- [1.3.0](#130)
- [1.2.1](#121)
- [1.2.0](#120)
- [1.1.3](#113)
- [1.1.2](#112)
- [1.1.1](#111)
- [1.1.0](#110)
- [1.0.2](#102)
- [1.0.1](#101)
- [1.0.0](#100)

## 1.3.0

Unreleased. Target for the requested EPG, timer and
recording extensions. Instant recording and timer editing are implemented;
EPG search and cards have passed joint acceptance; library management has also passed joint acceptance.

- Idea no. 6: free space per mounted disk and optional RAM/uptime sensors. Diagnostics refresh every five minutes; unknown values and disconnected disks are not reported as zero.

- Added the HA dependencies required by real selector checks to the test
  environment; aligned the device-ownership regression test with timer context.

- Incorporated newer fixes from `main`: current HA device ownership lookup
  for actions and exact-commit HACS validation are retained alongside the new
  recording workflows.

- Move/delete guards now match the selected recording rather than blocking all
  receiver activity. Unrelated HA streams, reported streams and playback remain
  usable; active timers are matched by file path. Unresolved file operations block
  new streams only for source/destination paths. Deletion asks about the selected
  title with its own button and requires fresh confirmation after action changes.

- Completed recording titles can be changed during streaming or recording
  playback; missing streaming status no longer blocks title-only changes.
  Media paths and bytes stay unchanged. Recording/preparation guards and stricter
  move/delete protection remain in place.

- Recording management uses a modal dialog with keyboard support. Errors and
  unconfirmed operations are clearly highlighted and remain visible on the card
  after closing. Library loading failures are also prominent alerts.

- Recording management in the card and HA actions: change title, move and
  explicitly confirm deletion. Fresh selection checks, activity/destination
  guards, unresolved-write lock and read-only completion checks. Section 5b
  jointly accepted following local, Octagon and HA dialog checks.
- Recording library card: automatic columns based on available list width.
  Display order: title, duration, recording date, channel, progress, size.
  Priority: title, recording date, channel, duration, progress, size. Updates
  during use while preserving expanded details.
- Recording library card: second compact row view with extra scrollbar spacing selectable in the visual
  editor. Rows show extra fields when space permits; expand it for all
  metadata. Existing detail view remains the default. Requires card file dev.16;
  the library action introduced in dev.13 remains compatible.
- Read-only recording library with a separate dashboard card and
  `recordings_list` action: combined title/channel, tag, directory and progress
  filters, complete catalog without a result limit, file size and receiver-reported
  percentage. Missing values remain unknown; zero percent does not necessarily
  mean unwatched. Native media views also show file size and tags.
  The dev.13 library scope passed actual HA checks; the dev.16 row view
  passed local checks; section 5a jointly accepted.
  Title changes, move and delete are implemented and jointly accepted in 5b.
- EPG search and similar programmes return all matching received results without
  a local limit. List/single display with arrows around the count:
  “[‹] Result 10 of 30 [›]”. Both cards default to single view; remote search is off.
  Both integration and card require dev.12.
- Reset search now clears input and results together. Late search replies are
  discarded while pending recording requests retain their acknowledgement.
- Remote card sections for EPG search, playback and numbers are independently
  optional; added an EPG-only card and an explicit clear-input button.
- Added EPG title search, similar programmes and guarded event recording as HA
  actions plus a search/record view in the optional remote card. Fresh event and
  timer checks and uncertain-write protection prevent stale/duplicate requests.
  Direct Octagon and actual HA checks passed; section 4 jointly accepted.

- Completed practical HA checks of selection controls, calendar updates, conflict
  events and visible information messages with both receivers.
- Documented direct receiver checks of editing, series, choice values and conflicts
  on Octagon/OpenWebif 2.4.1 and Vu+/1.4.4. Both images may mutate a timer despite
  rejecting an edit; see the additional practical HA checks.
- Timer actions now offer named channel choices, native date/time controls in
  the HA timezone and known receiver recording directory choices. Actions also offer
  named message types and after-recording behavior. Channel/directory selections
  are receiver-bound; manual YAML inputs remain supported. Ambiguous/nonexistent
  local clock-change times are rejected.
- Added timer editing with a separate old identity, preservation of omitted options
  and readback. Add/edit support weekly series, directories, tags, disabled state
  and recording type. Single timers and entire series are explicitly distinguished.
  Receiver conflicts produce translated errors and structured HA events; rejected
  edits may already have changed values. No automatic replay or rollback.
  Section 3 accepted by both parties on 2026-09-20 following receiver and HA checks.

- Added the “Record current programme” action and button: check fresh EPG and
  timers, start event-mode recording and refresh state. Existing recordings remain
  unchanged. Guard repeated/concurrent calls and lost responses; no fallback to
  long recording. Optional responses identify the start or existing timer.
  The user confirms creation, `started: false` for an existing recording and
  rejection without EPG; section 2 confirmed complete by both parties.
- Added section 1b foundations: validated internal EPG, timer, conflict and
  recording models; existing timer actions offer optional HA response data
  identifying the addressed timer. Errors remain translated exceptions.
- Prevented automatic replay of timer writes after response loss. Uncertain
  acknowledgements receive a dedicated error; timer actions refresh lists after
  failures too and invalidate them on cancellation. Added regression tests and
  bilingual practical test instructions. The user confirms all practical steps
  on Octagon/OpenWebif 2.4.0 and Vu+/OpenWebif 1.4.4; both parties confirmed
  section 1b complete. Response loss was tested using local simulation.
- Recorded a differing user test on Vu+ Solo² with VTi 15.0.0 and OpenWebif
  1.4.4: timer creation and messages passed; toggling timer status and deletion
  initially failed. Subsequently supplied action and timer data establish a mismatching
  service reference due to leading whitespace, with matching times. After manually
  removing the space, the user confirms disabling, enabling and deletion on dev.1.
  No general image incompatibility is established.
- Timer actions trim outer whitespace from service references and reject empty
  identifiers before contacting the receiver. Added regression tests for creation,
  toggling and deletion; internal whitespace is preserved. Automatic trimming
  tested locally; Vu+ retest with manually corrected input on dev.1 passed.
- Documented the implementation plan for feature ideas 1–5 in both languages,
  including confirmation by both parties before committing each finished section.
- Started the API foundation: retain structured command responses and internal
  rejection details. Existing commands still return `None`; exception messages
  exclude raw receiver messages.
- Section 1a confirmed through user testing on Octagon SF8008 4K Supreme with
  OpenATV 7.6.0.20260831 and OpenWebif 2.4.0: messages, timer creation,
  enabling/disabling and deletion, expected rejection of repeated deletion and
  subsequent operation passed. Recorded practical evidence and completion by
  both parties.

## 1.2.1

Unreleased.

- HACS validates the exact commit instead of the branch name so special
  characters such as `#` in working branches do not cause `Not Found` failures.

- Device actions use `DeviceEntry.config_entry_id` instead of the deprecated
  `config_entries` property (issue #10). Loaded-entry validation and the
  translated error for invalid targets are preserved. Regression tests cover
  target validation and selection between two receivers.

## 1.2.0

Released on 2026-09-16.

- Require successful CI for the current PR state, continued compliance with all
  integration quality requirements and maintained or improved quality status
  before merging into `main`. Targeted local checks are sufficient; current CI
  evidence does not require a complete local rerun. Additionally check affected
  requirements outside CI. Aligned project, release and developer instructions in
  both languages; completed release commands with existing type and coverage checks.

- Added `flat-square` README badges for releases, requirements, license, tests,
  Hassfest/HACS, coverage, HACS installation and documentation. After successful
  tests on `main`, coverage is updated on the separate `badges` data branch with
  source commit and run link; existing quality checks remain in place. Updated
  the HACS custom repository installation instructions.

- Use explicit video timestamps in the HLS seek test so AAC encoder delay cannot
  shift the target across colour/segment boundaries. Additionally verify the
  start timestamp of every test segment; streaming processing remains unchanged.

- Recording playback and repeated forward/backward seeks confirmed in real
  Home Assistant through user testing and debug logs. Original video is preserved
  and only MP2 audio is converted to AAC; feature approved for integration into `develop`.

- Optimized recording streams: preserve suitable original H.264 video, frame rate
  and quality; copy compatible AAC or convert audio only. Existing Enigma2 indexes
  provide keyframe-aligned HLS seeking without a full scan. Index/FFmpeg validation,
  explicit fallback logs and a 32 MiB total segment cache per session. Compatibility
  mode remains available.

- Seeking in completed TS recordings through a full HLS VOD timeline and
  on-demand generation of requested sections with continuous timestamps.
  Bounded caching, independent playback sessions and automatic fallback when
  receiver prerequisites are missing. VOD fallback uses HA H.264/AAC encoding with the
  existing quality settings.

- Media source consistently named “Enigma2 Connect” in all languages.
  Updated navigation instructions and documented HLS duration and seeking limits
  in the developer guides; existing quality settings remain documented.

- Streaming debug logs include an independent session identifier, detected codecs,
  video/audio parameters, processing path, fallback reasons and pool events.
  Credentials and playback URLs are excluded from these messages.

- Multiple external streams per receiver: configurable limit defaulting to 5,
  with 0 for unlimited. Additional starts do not end existing streams. Viewers
  share the same live channel; recordings start independently. Concurrent startup
  requests respect the limit; at capacity, only the extra start is rejected with
  a translated message.

- Automatic stream processing: relay suitable receiver HLS, copy compatible
  video/audio tracks and check receiver transcoding before software conversion.
  Only incompatible tracks are re-encoded. Compatibility mode can force the
  previous full conversion when needed.

- Fixed browser playback: HLS now uses the exact MIME type expected by Home
  Assistant's media dialog, `application/x-mpegURL`. This selects the built-in
  HLS player instead of the unsupported-media message. A regression test
  verifies the exact spelling.

- Idea no. 13: optional external playback of live TV and TS recordings through
  the HA media source. Software video conversion produces H.264 up to 720p/25 fps;
  compatible original tracks retain their quality.
- Receiver credentials stay in the backend; random playback URLs expire on
  inactivity, unload or after six hours at most. Multiple streams per receiver
  have independent resources and lifetimes. Suitable recordings provide a full
  timeline; fallback recording playback uses a limited sliding window.
- Live TV port and HTTPS are configurable independently of OpenWebif. Added
  German/English guidance, simulated tests and local FFmpeg tests. Browser/Cast
  device acceptance is recorded separately.
- New project worktrees must be located under `V:\enigma2-connect-worktrees`.
- Added a 1280 × 640 GitHub social preview: device symbol centered above the
  wordmark on white, with PNG, SVG source and `-SocialOnly` export.
- Use a separate branch for every task and an additional worktree for larger
  tasks. Merge checked, completed changes into `develop` and push it.
  Prepare and open a PR into `main` only after user approval; merging and
  releasing also require their respective explicit approvals.
- Merged current `main`, including the Junie blog monitor and silent review
  receipts, into `develop`, preserving the social preview and branch rules.

## 1.1.3

Unreleased.

- The blog monitor only publishes posts needing adaptation, enhancement or
  review. Uneventful results are durably recorded without an issue, preventing
  repeated AI credit consumption for unchanged posts.

## 1.1.2

Unreleased.

- Switched the blog monitor to individual Junie assessments: weekly discovery,
  next-day retries, separate validation/publication and reported model costs.

- Junie trial succeeded: German assessment with complete Modbus deadlines;
  reported model cost about USD 0.048, actual top-up deduction still unconfirmed.

- Manual Junie single-post trial with read-only GitHub permissions and subsequent
  validation of the result structure and source citations.

- Documented Cloudflare follow-up: the API rejected the first request with
  HTTP 429/4006 despite a reset dashboard counter; remaining tests stopped.

- Cloudflare per-post trial with one request per article, exact filename selection,
  aggregate usage and preservation of completed reports when a later request fails.

- Manual Cloudflare trial with gpt-oss-120b for stored blog posts, using the same
  source evidence validation; report artifacts only, no issues or state changes.

## 1.1.1

Unreleased.

- Failed blog posts are durably queued after the weekly check and retried on
  the following day. Only a second failure for the same content fails the run;
  partial successes are completed separately.
- A state branch records attempt counts and original posts. Daily retry runs
  do not select new posts; exhausted entries can be retried manually. Reports
  distinguish Gemini, response validation and GitHub publication failures.

## 1.1.0

Released on 2026-09-13.

- Released the verified quality improvements as version 1.1.0. Actual Bonjour
  discovery, automatic DHCP receipt in running Home Assistant and subjective
  picture/audio playback remain documented as pending practical checks.

- Replaced vulnerable transitive test dependency `cryptography 48.0.1` with
  `50.0.1` (CVE-2026-69247), together with compatible `pyOpenSSL 26.4.0`.
  The temporary uv override for Home Assistant's exact pins is documented and
  affects only the development/test environment.

- Migrated GitHub Actions to Node.js 24: `checkout@v7`, `setup-uv@v10.1.0` and
  `upload-artifact@v7` across all affected workflows, replacing the deprecated
  Node.js 20 action versions.

- CI explicitly installs and runs FFmpeg before testing so actual recording-frame
  extraction is not skipped. The requirement of above 95% coverage per integration
  module remains unchanged.
  Corrected CI passes 270 Python and 8 frontend tests plus Hassfest/HACS;
  CI evidence and completed checklist entries are documented.

- Checked an actual DHCP address change on the Octagon: missing MAC data after
  restarting the interface correctly prevents adoption. After a GUI restart,
  identity verification and address adoption passed with identifiers, credentials
  and HTTPS settings preserved. Added a regression test and user guidance;
  automatic receipt of the DHCP announcement remains a separate pending check.

- Recording snapshot and twelve bounded control checks passed on the Octagon;
  original volume, mute state and existing timers/recordings were preserved.

- Brand artwork, icons, disabled signal diagnostics and options dialogs checked
  in the real HA interface; FFmpeg repair text and remediation verified in German
  and English.
- HTTPS on the real Octagon checked, including certificate rejection and the
  complete HA read flow; a bounded live-stream sample delivers decodable 1080p
  video and multichannel audio without changing channels. Native Bonjour
  observation, remaining hardware limits and remote reconciliation are documented.
- Incorporated newer `main` changes, including the blog-monitor correction and
  options-dialog test, while preserving the existing version history.

- Read-only hardware acceptance on the Octagon SF8008 with HA 2026.9.1 verified:
  nine platforms, enabled entities available, signal diagnostics disabled,
  refresh, duplicate prevention and unloading successful. Screenshot and picon
  decode correctly. Guides and validation distinguish this evidence from the
  outstanding network, interface and control checks.

- Reusable, explicitly started receiver acceptance using isolated Home Assistant:
  setup, entities, disabled signal diagnostics, refresh, duplicate prevention and
  unloading. An allowlist blocks receiver write commands; reports include versions
  and a source hash without credentials. The helper was checked with simulated
  responses; read-only acceptance on the real Octagon SF8008 has now passed.

- OpenWebif services with Bonjour names are offered for setup. DHCP updates known
  receiver addresses only after confirming their MAC identity; credentials, port,
  TLS settings and entity identifiers are preserved.
- Diagnostics also work without a loaded receiver and during partial failures.
  Missing FFmpeg produces a translated repair issue with recovery instructions.
  Optional signal diagnostics start disabled for new entities.
- Entity icons from `icons.json`, device lifecycle and local brand images are
  checked; both guides explain discovery, updates and device support.
- All 23 integration modules are strictly typed; pinned mypy 2.3.1 runs in CI.
  Receiver metadata remains an explicitly identified flexible JSON boundary.

- **Refresh lists** waits for a fresh fetch even on immediately repeated calls
  and reports connection failures as translated action errors.
- Additional transport, control, artwork and calendar checks cover decoder
  cancellation, download limits, rapid channel changes, cache limits and malformed
  receiver/image provider responses.
- Both user guides document connection parameters and partial/full unavailability.
- CI additionally requires above 95% combined statement/branch coverage for every
  integration module; the ten additional Silver rules are internally verified.
  Local brand files satisfy the current custom-integration branding requirement.
- Setup, reauthentication and reconfiguration now explain connection fields
  directly in the dialog in German and English.
- Additional tests cover recovery in the same flow, device identity, duplicate
  receivers and preserving settings after invalid input.
- Additional lifecycle tests verify action registration without a receiver and
  single failure and recovery log messages.
- Quality checklist with evidence and remaining Bronze through Platinum work;
  branch coverage and a CI gate for complete config-flow coverage.
  This remains a custom integration without an official quality tier.

## 1.0.2

Unreleased.

- The blog workflow uses Gemini 3.8 Flash with low thinking effort and current
  request parameters. The first real Gemini 2.5 Flash request returned HTTP 404.
  Weekly scheduling and fixed request limits are preserved.

## 1.0.1

Unreleased.

- A weekly GitHub workflow reviews new and edited Home Assistant blog posts
  from September 2026 with Gemini against the integration code. It independently
  assesses required adaptations and useful enhancements with benefits, implementation
  steps and validated source evidence. At most one AI request for five posts per run;
  combined report issues prevent duplicate reviews.
- Documents setup with a Google Free Tier project, a manual dry run and local
  preparation without AI calls. Offline tests cover selection, response validation,
  enhancement proposals and failure handling.
- The options-flow test isolates and verifies automatic reload, preventing a
  background timer from interfering with CI test cleanup.

## 1.0.0

Released on **2026-09-13**.

First public release of Enigma2 Connect:

- Home Assistant integration for Enigma2/OpenWebif with media player, remote
  control, channel and bouquet selection, sensors, calendar, screenshots,
  messages and receiver actions.
- Recordings and optional channels in the Home Assistant media browsers,
  including receiver assignment and optional preview images.
- Graphically configurable dashboard remote card.
- Config flow, options, reauthentication, multi-device support, and German and
  English documentation.
