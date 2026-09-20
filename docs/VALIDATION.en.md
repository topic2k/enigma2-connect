[Deutsch](VALIDIERUNG.md) | [English](VALIDATION.en.md)

# Verification summary

## Home Assistant practical checks: 1.3.0-dev.6

Tested on **2026-09-20** in the user's actual HA installation. The integration page
showed **1.3.0-dev.6**, two receivers and 130 entities. Browser checks used
**Tools → Actions**, **Events** and **Calendar**, with direct receiver readback of
test timers. No dashboards or integration settings were changed.

- Channel/directory lists displayed both receivers with correct binding. The native
  calendar dialog and time controls were operated. Disabled timers created through
  the forms were stored on both receivers for 2026-09-29, 16:25–16:27 local time,
  with the selected channel, `/media/hdd/movie/` and `afterevent: 0`.
- **After recording** and **Message type** displayed all four named German options.
  Information messages sent through HA were visually confirmed on both receiver
  screenshots. Other message types were not individually rechecked on screen.
- Selecting the Vu+ device with Octagon channel/directory choices produced the
  translated targeting error and created no additional timer.
- Actual conflicts on **addition and editing, on both receivers**, were triggered
  through HA actions. Four events were received and individually inspected in the
  HA event viewer: correct `config_entry_id`, `action: timer_add` with
  `timer_state: unknown`, and `action: timer_edit` with `timer_state: changed`.
  The action UI showed concrete conflicts and the warning that timer data might
  already have changed. The event subscription was stopped.
- After enabling them, both form-created timers appeared in the HA calendar at
  16:25. Another HA edit changed the Octagon timer's name/end; the calendar displayed
  the new name and **16:25–16:30** in the event detail.
- All dedicated test timers were removed. Final readback showed the original seven
  Octagon timers and zero Vu+ timers; checked original fields were unchanged.
  Repeated deletion produced the expected error.

Evidence: `ha-ui-validation.json`, `.work/ha_ui_receiver_check.py`, and locally
inspected `ha-ui-message-0.jpg`/`ha-ui-message-1.jpg` under
`V:\enigma2-connect\.work\recording-workflows-checks` (harness in the parent
`.work/`). Reports contain no credentials. These findings supplement the separate
direct receiver and simulated HA checks.

**Section 3 accepted by both parties:** Codex confirmed the completed checks;
the user explicitly confirmed completion on **2026-09-20**. Completion commit on
`feature/recording-workflows`: `feat: add timer editing and action selectors`. Actual weekly recording execution
was not awaited; the Vu+'s missing DVB-S signal/EPG remains a known test boundary.
No production source changed and no full CI rerun is needed for this evidence update;
remote reconciliation and required current CI remain mandatory before PR/merge.

## Real receiver checks: 1.3.0-dev.6, section 3

On **2026-09-20**, with user authorization, the current production modules
`OpenWebifClient`, `TimerEditor`, `action_choices` and `timer_conflicts` were tested
against both physical receivers. The local harness invoked these modules directly;
it did not operate the HA frontend or call services on the user's HA installation.
Credentials came from an ignored local file and are excluded from reports.

| Check | Octagon SF8008 4K Supreme | Vu+ Solo² |
| --- | --- | --- |
| Reported OpenWebif | 2.4.1 | 1.4.4 |
| First TV bouquet channels / known paths | 41 / 4 | 34 / 1 |
| Create disabled timer, edit and preserve options | passed | passed |
| Reject stale identity without another change | passed | passed |
| Mon/Fri → Tue/Thu weekly masks, reject single scope | passed | passed |
| Ten-minute interval across midnight | passed | passed |
| Channel/directory choice values, local time, After recording = Do nothing | saved and read back | saved and read back |
| Enable/disable, delete, reject repeated deletion | passed | passed |
| Information message after rejection | API acknowledged; display unchecked | API acknowledged; display unchecked |
| Conflict on third simultaneous timer / conflict on edit | both detected | both detected |
| Timer state after rejected edit | `changed` | `changed` |
| Cleanup / original timers | no test timers; 7 unchanged | no test timers; still 0 |

Conflicts used dedicated test timers on different transponders two weeks ahead,
outside the computed windows of existing timers; all were removed immediately after
the checks. Each response contained three conflicts accepted by the production
parser. **Both images mutate the test timer before rejecting the edit.** Readback
in `TimerEditor` detects this; no automatic rollback occurs. Original timers were
compared before/after every run by identity, name, description, disabled status,
recording/zap mode, after-event behavior, weekly mask, tags and directory; these
fields remained unchanged.

The first series attempt retained Monday as the start date while changing to
Tue/Thu. Both receivers moved the date and the integration correctly raised
`CommandUnconfirmed`. Updating the first occurrence to Tuesday as instructed made
all series checks pass. Every attempt was cleaned up separately. Weekly masks and
stored dates were read back; actual weekly recording execution was not awaited.
According to the user file, the Vu+ has no DVB-S signal or EPG. Its directory came
from `movielist.directory`, not `timerlist.locations`.

Reports: `receiver-section3-*.json`; harness: `.work/receiver_section3.py` in the
original local checkout. Reports reside under
`V:\enigma2-connect\.work\recording-workflows-checks`, including the initial series
attempts. No production code changed.

The HA items pending at this stage were subsequently checked; see the preceding
Home Assistant practical-check section for results and acceptance status.

## Action controls: 1.3.0-dev.6, addition to section 3

As of **2026-09-20**. Implemented named channel choices, native date/time controls,
known receiver directory choices and named message-type/after-recording options.
[Practical guide](USER_GUIDE.en.md#test-section-3-on-the-receiver).

**Local checks passed:** 273 distinct tests across three overlapping runs using
Python **3.14.7**, Home Assistant **2026.9.1** and
pytest-homeassistant-custom-component **0.13.364**. The first run had 269 passing
tests and two failures caused by an outdated timezone test API. After switching to
`async_set_time_zone`, both cases and affected action tests passed on rerun.
Three existing instant-recording/device-targeting tests complete coverage for the
final source version. Receivers are simulated; this is not real frontend or receiver acceptance.

Checks cover HA selector schemas/translations, local-time conversion including
ambiguous/nonexistent times, two receivers and incorrect targeting, list updates
and unloading, directory sources, manual YAML alternatives, named options and
legacy integers 0–3 producing identical receiver parameters, defaults, and existing
timer, recording and error handling.

Combined statement/branch coverage uses the final action run for `services.py`
and the first run for other modules, whose source remained unchanged:

| Module | Coverage |
| --- | --- |
| `__init__.py` | 97.96 % |
| `action_choices.py` | 100.00 % |
| `coordinator.py` | 98.51 % |
| `models.py` | 95.52 % |
| `services.py` | 98.45 % |
| `timer_edit.py` | 100.00 % |
| `timer_conflicts.py` | 100.00 % |

All exceed the unchanged 95% threshold. Ruff, formatting, syntax, strict mypy for
**33** production modules, version/documentation checks and offline `uv lock --check`
(159 packages) passed. Reports: `action-choices-*`, `action-enums-*` and `action-tail-*` under
`V:\enigma2-connect\.work\recording-workflows-checks`. Quality review additionally
covers the new controls under `action-setup`, `action-exceptions`,
`exception-translations`, `strict-typing`, `test-coverage`, `docs-actions`,
`docs-data-update` and `docs-known-limitations`; no criteria were lowered.

The additional HA practical checks and acceptance by both parties are documented above. CI and remote reconciliation are required before PR/merge.

## Timer editing and conflicts: 1.3.0-dev.5, section 3

As of **2026-09-20**. Implemented `timer_edit`, extended creation options and
structured conflict events. [Plan and limits](DEVELOPMENT.en.md#section-3-timer-editing-and-conflicts),
[receiver test guide](USER_GUIDE.en.md#test-section-3-on-the-receiver).

**Local checks passed:** Python **3.14.7**, Home Assistant **2026.9.1**,
pytest-homeassistant-custom-component **0.13.364**. Initial run: 221 tests passed.
After reviewing authentication/cancellation during rejected-edit readback and
normalizing event action names, reran the same scope plus additional cases:
**228 tests passed**, with no failures or skipped cases. All receivers are
simulated, including those used in real HA action tests.

Checked: old/new identities, omitted-option preservation, VPS and padding,
incomplete/ambiguous timer data, weekday masks and explicit series scope,
midnight and explicit UTC offsets across clock changes, conflicts with and
without mutation, readback and uncertain successes, response loss, cancellation,
later-attempt guards, shared command lock, conflict projection without raw data,
translated errors, events, valid HA selectors, calls with/without responses
and isolation of two receivers. No independent conflict prediction or guarantee
that receiver rejection preserves timer values.

Scope: `test_timer_edit`, `test_workflow_actions`, `test_instant_recording`,
`test_integration`, `test_translations`, `test_silver_controls`, `test_channel_media`,
`test_gold_lifecycle`, `test_regressions`. Existing local HTTP tests continue
to verify protection from automatic timer-write replay. Combined statement/branch
coverage for changed/new production modules:

| Module | Coverage |
| --- | --- |
| `coordinator.py` | 99.48 % |
| `services.py` | 98.18 % |
| `timer_edit.py` | 100.00 % |
| `timer_conflicts.py` | 100.00 % |

All exceed the unchanged 95% threshold. Ruff, formatting, syntax and mypy strict
passed for **32** production modules. Version metadata and local documentation
targets are consistent; `uv lock --check --offline` passed, with only the project
version changing in the lockfile. Reports: `section3-tests.xml`, `section3-tests.log`,
`section3-coverage.json` under `V:\enigma2-connect\.work\recording-workflows-checks`.

Quality review: `action-setup`, `action-exceptions`, `parallel-updates`,
`exception-translations`, `icon-translations`, `strict-typing`, `test-coverage`,
`docs-actions`, `docs-triggers`, `docs-data-update`, `docs-known-limitations`.
No criteria or thresholds lowered. Unchanged modules retain their previous
evidence; no complete CI run or official HA quality tier is claimed.

**Historical status before subsequent practical acceptance (see above):** Follow the new guide on Octagon and Vu+ using
dedicated test timers. Option preservation, actual weekly recurrence and receiver
conflicts including mutation despite rejection are not yet practically confirmed.
A conflict that cannot be produced is not tested. Codex considers the local
implementation ready for testing; user confirmation and the section commit remain
pending. Refresh remote/main comparison before a PR; no merge or release here.

## Instant recording: 1.3.0-dev.4, section 2

As of **2026-09-20**. Implemented `record_now` and the **Record current programme**
button. [Plan and limits](DEVELOPMENT.en.md#section-2-instant-recording),
[new receiver test guide](USER_GUIDE.en.md#test-section-2-on-the-receiver).

**Local checks passed:** Python **3.14.7**, Home Assistant **2026.9.1**,
pytest-homeassistant-custom-component **0.13.364**. Initial run: **237 tests**
passed. After adding protection for unknown series-timer state and later EPG
timing corrections, reran the complete instant-recording test group. In total,
**240 distinct tests** passed in their respective latest run, with no skipped
or outstanding failed cases.

Checked: fresh EPG and time boundaries, standby/file playback, unknown timer
data, active series, running/disabled/zap timers, preservation of existing
recordings, concurrent starts and the shared command lock, EPG changes and
timing corrections, response loss, cancellation, list lag, rejection, unsupported
endpoints, authentication/connection errors, mismatched success replies and
rereading older response formats. Real HA action/button tests cover optional
responses and calls without them, list/state refresh, entity registration,
translations and isolation of two receivers. Section 1b HTTP tests remain
included. All receivers in these local tests are simulated.

Scope: `test_instant_recording`, `test_workflow_actions`, `test_workflow_models`,
`test_api`, `test_integration`, `test_silver_controls`, `test_translations`,
`test_channel_media`, `test_gold_lifecycle`, `test_regressions`.
Combined statement/branch coverage for affected modules:

| Module | Coverage |
| --- | --- |
| `api.py` | 97.02 % |
| `button.py` | 100.00 % |
| `coordinator.py` | 99.44 % |
| `instant_recording.py` | 100.00 % |
| `services.py` | 97.65 % |
| `workflow_models.py` | 100.00 % |

All exceed the unchanged 95% threshold. `instant_recording.py` was fully
remeasured after the final changes; the other modules retain the same source
as in the initial run. Ruff, formatting, syntax and mypy strict for **30**
production modules passed. Version metadata, local documentation links and
`uv lock --check --offline` checked; only the project version changes in the
lockfile. Reports under `V:\enigma2-connect\.work\recording-workflows-checks`:
`section2-tests.xml`, `section2-recheck.xml`, corresponding logs,
`section2-coverage.json`, `section2-instant-coverage.json`.

Quality review: `action-setup`, `action-exceptions`, `parallel-updates`,
`entity-unique-id`, `entity-translations`, `exception-translations`,
`icon-translations`, `test-coverage`, `strict-typing`, `docs-actions`,
`docs-data-update`, `docs-known-limitations`. No lowered criteria or thresholds.
Unchanged areas retain their previous evidence; no new complete CI run or
official HA quality tier is claimed.

**Practical feedback and completion on 2026-09-20:** The user confirms for
section 2: instant recordings are created; an already running recording returns
`started: false`; missing EPG prevents recording and displays an appropriate
message. The report does not provide separate results per receiver or additional
version details. Other test-guide details, particularly a playable file, actual
post-padding, standby and device selection, were not individually reported and
are therefore not established as practical evidence. Response loss and other
error cases remain covered by the simulated tests listed above.

The user and Codex confirm section 2 as complete. Corresponding completion commit:
`feat: add current programme instant recording`. No merge or release.

The local `origin/main` reference has meanwhile advanced to `df39aea` (1.2.1);
this working branch continues from the agreed baseline. Before a PR, recheck
remote/version state and reconcile intervening main fixes, including device
ownership lookup.

## Recording workflows: 1.3.0-dev.3, section 1b

As of **2026-09-20**. Implemented data models, optional responses for existing
timer actions and protection from automatic replay of uncertain timer commands.
Plan and limitations: [DEVELOPMENT.en.md](DEVELOPMENT.en.md#section-1b-data-models-action-responses-and-uncertain-outcomes).
Practical steps: [user guide](USER_GUIDE.en.md#test-section-1b-on-the-receiver).

**Local checks passed:** Python **3.14.7**, Home Assistant **2026.9.1**,
pytest-homeassistant-custom-component **0.13.364**. **201 distinct tests** passed
in their respective latest run. The initial run passed 186 cases; six local
HTTP cases failed because the `socket_enabled` fixture was missing, including
follow-on cleanup errors. After fixing the test setup, all 40 cases in the
targeted rerun passed (workflow actions and affected channel catalogs), including
an additional test for a failed reread. This test correction required no
production code changes.

Scope: `test_workflow_models`, `test_workflow_actions`, `test_api`,
`test_integration`, `test_silver_controls`, `test_translations`, `test_models`,
`test_gold_lifecycle`, `test_regressions`, `test_channel_media`. Real local
aiohttp connections to a simulated receiver confirm exactly one write after
response loss for all six protected timer endpoints and subsequent connectivity.
HA tests cover optional responses, existing calls, translated errors, reauth,
cancellation and list reconciliation after errors. Model tests distinguish
empty/unknown/invalid data and preserve identifiers.

Combined statement/branch coverage for affected modules: `api.py` **96.99%**,
`coordinator.py` **99.38%**, `services.py` **97.50%**, `workflow_models.py`
**100%**. All exceed the unchanged 95% threshold. Ruff, formatting, syntax and
mypy strict for all **29** production modules passed, as did version consistency,
local documentation link targets and `uv lock --check --offline`. Only the
project version changed in the lockfile. Reports in the original working
directory `V:\enigma2-connect`, under `.work/recording-workflows-checks/`:
`section1b-tests.xml`, `section1b-recheck.xml`, corresponding `.log` files and
`section1b-coverage.json`. Coverage combines both runs with unchanged production
code.

Affected quality rules reviewed: `action-setup`, `action-exceptions`,
`common-modules`, `parallel-updates`, `test-coverage`, `strict-typing`,
`exception-translations`, `docs-actions`, `docs-data-update`,
`docs-known-limitations`. No lowered status or new exemptions. Unchanged modules
retain their earlier evidence; no complete new CI run or new official HA quality
tier is claimed.

**Practical acceptance passed:** On **2026-09-20**, the user confirmed all
steps of the **1.3.0-dev.3** guide for the two requested test receivers:
Octagon SF8008 4K Supreme / OpenATV / OpenWebif 2.4.0 and Vu+ Solo² / VTi /
OpenWebif 1.4.4. This covers creation, disabling, enabling and deletion with
response data, automatic whitespace trimming, expected rejection of repeated
deletion, a subsequent message and existing calls without a response variable.
The operation sequence overlaps with 1a; the response and input properties
listed above are the new checks. No updated HA version or individual response
logs were supplied. Response loss and replay protection are evidenced only by
local HTTP tests; complete EPG/recording formats and image-specific conflict
behavior remain part of subsequent sections. The user and Codex confirm
section **1b** complete. Corresponding completion commit:
`feat: add recording workflow foundations`. No merge or release.

## Vu+ timer reference and input correction: 1.3.0-dev.2

User report dated **2026-09-20**, tested runtime **1.3.0-dev.1**: **Vu+ Solo²**,
**VTi-Team Image 15.0.0 (2025-06-23-vti-master (4ef8eb3a9))**, **OpenWebif 1.4.4**.
Screen message and timer creation passed. Enabling/disabling and the first
deletion returned “Die Receiver-Anfrage ist fehlgeschlagen oder wurde abgelehnt.”
Repeated deletion returned the same error; without confirmed prior deletion,
this is **not a passed rejection test**. The subsequent message worked;
no other issues were reported.

The initial timer run **did not pass**. Comparing the subsequently supplied
action inputs and stored timer establishes a mismatching identifier:

- `timer_toggle` contains a leading space before
  `1:0:19:283D:3FB:1:C00000:0:0:0:`; the stored timer reference has none.
- Requested times 2026-09-20, 12:00–12:02 at offset `+02:00` match the stored
  `begin=1789898400`, `end=1789898520` exactly.
- The user confirms the timer still exists, reporting `justplay=1`, `disabled=0`,
  `state=0`.

The previous code sends the mismatching identifier unchanged as `sRef`.
**User retest on 2026-09-20 passed:** After manually removing the space, disabling,
enabling and deleting the timer work. This confirms the mismatching input as the
cause; the finding does not establish a VTi/OpenWebif incompatibility. This retest
still concerns reported version **1.3.0-dev.1** with corrected input, not automatic
trimming in dev.2. Repeated deletion after successful deletion was not reported
again. Section 1a did not change timer parameters or time conversion.

**Fix in 1.3.0-dev.2:** The shared schema for `timer_add`, `timer_toggle` and
`timer_delete` trims outer whitespace and rejects empty identifiers before
contacting a receiver. Internal whitespace, case and times remain unchanged.
**12 targeted tests passed** using the real HA test framework with a simulated
receiver, including nine new parametrized regressions covering all three actions.
Scope: `tests/test_integration.py` with
`-k 'timer or service_target or actions_registered or action_rejection'`.
Ruff, formatting, strict type checking and syntax passed, as did version/document
consistency and the offline lock check. No new full coverage measurement or
reduced thresholds. Reports: `.work/recording-workflows-checks/timer-tests.xml`
and `timer-tests.log` under the original workspace `V:\enigma2-connect`.

**Practical status:** Vu+ timer actions with corrected input are user-confirmed;
automatic trimming in dev.2 is covered by the local regressions. Octagon evidence
and commit `e1dce95` retain their original scope. Affected rules:
`action-exceptions`, `test-coverage`, `strict-typing`, `docs-actions`,
`docs-known-limitations` and `docs-supported-devices`. The user and Codex confirmed
completion of this improvement on 2026-09-20. Corresponding completion commit:
`fix: trim whitespace in timer service references`. No new CI or acceptance for
other devices/features is claimed.

## Recording workflows: 1.3.0-dev.1, section 1a

Status **2026-09-19**, base `origin/main` at `1afa705`. Plan in the
[developer guide](DEVELOPMENT.en.md#implementation-plan-recording-workflows).
Structured API results and internal rejection details implemented. Targeted
checks with Python **3.14.7**, Home Assistant **2026.9.1** and
`pytest-homeassistant-custom-component 0.13.364`: **88 tests passed**, no
failures or skips. Scope: `test_api.py`, `test_integration.py`,
`test_regressions.py`, `test_silver_controls.py`. The changed `api.py` module
reaches **96.35% combined statement/branch coverage**; this is not a new
coverage measurement for the complete integration. Transport and receivers are
simulated; HA regression tests use the real framework. Checked success/rejection
responses, legacy return contract, shared command lock, cancellation/transport
errors and translated HA errors without raw metadata in messages or logs.

Ruff, formatting, strict mypy for the integration and syntax checks for the three
changed Python files passed. `uv lock --offline` and `uv lock --check --offline`
passed; only the local project version changed in the lockfile. Version locations
and local documentation link targets checked. Run directly against the worktree;
JUnit and API coverage reports are stored under
`V:\enigma2-connect\.work\recording-workflows-checks`.
**Practical evidence from the user's report on 2026-09-20:** Octagon SF8008
4K Supreme, OpenATV **7.6.0.20260831 (2026-08-30)**, OpenWebif **2.4.0**, tested
version **1.3.0-dev.1**. Screen message, timer creation, disabling/enabling and
deletion all **passed**. Deleting the removed test timer again produced the
expected German error: “Die Receiver-Anfrage ist fehlgeschlagen oder wurde
abgelehnt.” The subsequent screen message also worked; no other issues reported.
This test was performed by the user through Home Assistant with a real receiver,
separate from the simulations above. The user's installed HA version was not provided.

This confirms existing controls, visible rejection and continued operation on
this device/image. Internal structured responses, concurrency and cancellation
remain covered by automated tests only. No new receiver actions or current CI
evidence for this state. Acceptance does not extend to other devices, images or sections.

Affected quality criteria: `action-exceptions`, `parallel-updates`, `test-coverage`,
`strict-typing`. Preserve existing translated HA errors and serialization;
do not lower test thresholds. Response details are internal and must not be
included wholesale in logs or diagnostics. The remaining foundation and feature
sections 2–5 are pending. Section **1a** is complete for both parties following
the previous Codex confirmation and the user's fully successful test report on
2026-09-20. This evidence completes the same section and retains its tested
version **1.3.0-dev.1**; runtime code and tests are unchanged from the successful
local run. Recheck documentation links, version consistency and `git diff --check`
at completion; no reason to repeat the complete test run.
Earlier evidence below remains limited to its documented states.

## Release 1.2.0

Explicit publication instruction received on **2026-09-16**. Release preparation
changes only the two changelogs and verification summaries. Integration code,
tests, dependencies, quality checklist and check thresholds are unchanged from
`97ebd0f`. Its [PR tests](https://github.com/topic2k/enigma2-connect/actions/runs/35136701709),
[Hassfest/HACS](https://github.com/topic2k/enigma2-connect/actions/runs/35136701707)
and CodeQL passed. After this documentation update, current PR checks and then
checks for the actual merged release commit will be verified again before tagging
and publication. Final CI links will be recorded in [release 1.2.0](https://github.com/topic2k/enigma2-connect/releases/tag/v1.2.0).

Hardware evidence retains its documented scope. Real HA recording playback and
repeated seeks are supported by user testing and logs; Cast, endurance, real
concurrent viewers and other listed practical limitations remain pending.
This release does not extend device acceptance.

## PR preparation: 1.2.0

Remote branches, tags and published releases checked on **2026-09-16**:
`main` is at `271444a` (1.1.3), and the latest stable release is `v1.1.0`.
The backward-compatible streaming feature results in target version **1.2.0**;
the manifest, project metadata, lockfile and both changelogs use this version
without a development suffix. The version remains unreleased.

Pending local documentation changes have been combined with `develop`.
Current streaming descriptions, numbered ideas, branding and existing CI evidence
are preserved. Both languages now include the quality requirements for merging
into `main`. Integration code, tests, coverage thresholds and the quality checklist
are unchanged from `b1feaae`.

The [test run on `b1feaae`](https://github.com/topic2k/enigma2-connect/actions/runs/35135760298)
and [Hassfest/HACS](https://github.com/topic2k/enigma2-connect/actions/runs/35135760314)
passed. Successful CI for the new PR state is required again before merging.
Documented receiver/HA user checks retain their stated scope; this adds no
acceptance of Cast, endurance, real concurrent viewers or other listed practical
limitations. The coverage data branch will be published after successful `main` tests.

Local final checks passed: 122 local file links, 56 Python syntax checks, version consistency, preserved changelog history and unchanged dependencies. `uv lock --offline`, `uv lock --check --offline` and `git diff --check` passed.

## CI seek test: correction 1.2.0-dev.10

The [dev.9 CI run](https://github.com/topic2k/enigma2-connect/actions/runs/35132768651)
passed 413 tests; two HLS colour-test variants failed with FFmpeg 6.1.1.
Individual segments contained the expected colours. AAC encoder delay put the
relative 12.8-second seek before the intended video frame: container start
0.978667, video start 1.000000 seconds. The corrected check uses absolute video
time 13.8 seconds and additionally verifies each segment start within one 90 kHz
tick. No relaxed colour checks, skips, reduced coverage thresholds or integration
code changes. The quality checklist is unchanged. The [corrected CI run](https://github.com/topic2k/enigma2-connect/actions/runs/35134405193)
with FFmpeg 6.1.1 passes all Python/frontend tests, unchanged coverage thresholds,
Ruff, formatting and mypy. [Hassfest and HACS](https://github.com/topic2k/enigma2-connect/actions/runs/35134405186)
also pass. Both affected tests additionally passed locally with FFmpeg 8.1;
Python syntax and offline lock checks passed. Documented HA user acceptance
is retained; this test correction adds no new device acceptance.

## HA recording playback and seeking: user acceptance 1.2.0-dev.9

On **2026-09-16**, the user streamed a recording in real Home Assistant, sought
forward/backward repeatedly and approved integration into `develop` subject to
a clean log review. The reviewed 19:57:48–19:58:21 excerpt contains no streaming
errors, remux fallbacks or Enigma2 Connect warnings. HA's generic custom-integration
startup warning is unrelated to playback; the ESPHome traceback on changing log
levels concerns a disconnected ESPHome remote.

Evidence: automatic recording mode; original H.264 High 1280 × 720 at 50 fps;
MP2 stereo 48 kHz/256 kbit/s converted to AAC stereo 48 kHz/128 kbit/s;
HLS/MPEG-TS output with one quality variant. Startup takes 3.949 seconds from
request to `Started`. Fourteen remux requests include jumps to 580.980 seconds
(9:41), 1705.600 (28:26), 2029.840 (33:50) and back to 957.920 (15:58), followed
by subsequent sections. Segment durations around 6.6–7.1 seconds follow original
keyframes. The pool reports two occupied slots with a configured limit of four;
this does not establish two actively watching viewers. All logged coordinator
refreshes succeed, including one taking 5.234 seconds.

The browser and its version were not specified. This acceptance does not replace
separate Cast, endurance, expiry/cleanup or subjective audio/video sync checks.
The excerpt ends during active playback. The feature is considered provisionally
complete for the scope tested by the user.

Evidence: locally provided `home-assistant_enigma2_connect_2026-09-16T17-58-29.053Z.log`,
SHA-256 `e6960bfa8ad13e4fa744ca61f6c305175ca27c9280f7d9362ce3b3da80015d0a`. The full HA log remains outside the repository because
it contains unrelated operational data. No Python or test code changes in this
acceptance update; SHA-256 matches the passing dev.8 evidence. Integration checks
cover documentation, consistent versions and the merge with `develop`; detailed
streaming tests are documented below. Current CI and quality review are still
required before any later integration into `main`.

## Original tracks and seekable remux: 1.2.0-dev.8

Checked on **2026-09-15**, Python 3.14.7 / HA 2026.9.1 / FFmpeg 8.1.
The broader streaming run passed **158 of 160 tests**; two media tests exceeded
their time limits while other checks/receiver work ran concurrently. A focused
MP2 rerun passed. After preserving short original-video tails, **52 VOD/remux
tests passed** without concurrent load using locally copied FFmpeg binaries.
This overlapping group includes both affected cases. The other 110 streaming
tests passed in the broader run; unchanged modules match their SHA-256 evidence.

Media tests compare SHA-256 hashes of all original H.264 packets with remuxed
sections, proving video and 50 fps preservation. AAC packets are compared as
well; MP2 is converted to AAC. Tests cover seeking, full HLS decoding, short
tails, index bounds, stale/inconsistent indexes, unavailable FFmpeg features,
Compatibility mode and the 32 MiB total cache. FFmpeg 8.1 previously exposed an
extra AAC output packet in the old VOD encoder; an output-packet cap fixes it.

**Real receiver:** The authorized “Böhmi brutzelt” recording on the SF8008
provides HTTP byte ranges and a 55,696-byte index with 3,481 entries. Metadata:
H.264 High, 1280 × 720, 50 fps and MP2 as the first audio track. Four short sections
near the beginning/middle and an actual FFmpeg HLS seek to about 18:52 decoded
without errors; processing was `recording_vod+copy_video+encode_audio`.
With reduced read preroll, local preparation took about 4.2 seconds and new
sections about 2.0 seconds (a sample measurement, not a guarantee for the HA
host). No full download. The final duration edge correction does not change
this recording case and is covered by the final tests. HA browser UI, Cast and
subjective audio/video transitions still require practical verification.

Ruff, formatting, mypy (**28 modules**), syntax, offline lock validation and
local Hassfest passed. All 28 modules exceed 95% combined statement/branch
coverage (minimum 96.25%). Unchanged sources retain verified evidence;
the four changed/new streaming modules were remeasured. No new whole-integration
suite or remote CI run. Evidence: `.work/remux-full-tests.log`,
`.work/remux-final-tests.log`, corresponding `*-inventory.json`,
`.work/remux-verified-coverage.json` and `.work/remux-checks.log`.
Real-receiver evidence is in the main checkout's local tooling folder:
`.work/remux-receiver-validation.json`. Credentials are excluded from evidence
and Git contents.

## Seeking in recordings: 1.2.0-dev.7

Checked on **2026-09-14**, Python 3.14.7 / HA 2026.9.1. The broad streaming run
passed **133 tests**; one additional cache assertion compared 2.8 exactly with
2.8000000000000007 and was corrected to use numeric tolerance. Afterwards,
**25 targeted VOD tests** passed, including that case and a newly added
short final segment. These groups overlap. Production files are identical
in both runs, verified with SHA-256.

Actual FFmpeg colour-scene media verifies forward/backward jumps, an HLS-client
seek using the full playlist and complete decoding without timestamp errors.
Packet measurements established a shared clock, bounded decoding preroll and
aligned audio/video sections. Earlier reset/overlapping timestamp approaches
were discarded. Other cases cover byte ranges, invalid/unstable duration,
changing files, cache eviction/regeneration, shared requests, bounded queues,
cancellation/process termination, HA URLs and parallel sessions.

Ruff, formatting, mypy (**27 modules**), syntax, offline lock verification and
local Hassfest passed. All **27 modules exceed 95%** combined statement/branch
coverage (minimum 96.25%); unchanged modules retain their verified evidence,
and all three VOD-affected modules were fully remeasured. Quality checklist
reviewed: no new dependency, platform or reduced threshold. Evidence:
`.work/vod-full-tests.log`, `.work/vod-final-tests.log`, corresponding
`*-inventory.json`, `.work/vod-verified-coverage.json` and `.work/vod-checks.log`.

Receiver and HA browser requests are simulated; FFmpeg uses real synthetic media.
No new full-suite/remote-CI run. Seeking and subjective video/audio transitions
on the real SF8008 with Firefox, Edge and Cast still need practical verification.

## Media source name and HLS documentation: 1.2.0-dev.6

Checked on **2026-09-14**: **9 media-source/translation tests** passed, including
the HA media tile, German/English labels and fallback language. Ruff, formatting,
mypy (26 modules), Python syntax, offline lock verification and local Hassfest
(Core 2026.9.1) passed. Version fields and local documentation links agree.

Python changes are limited to two fallback labels. Reversing those text changes
and comparing SHA-256 confirms otherwise identical dev.5 code. No streaming/seek
logic changes, new platforms or dependencies. The targeted run does not replace
the earlier, broader coverage evidence. No new full-suite or real receiver/browser
test. Evidence: `.work/source-name-tests.log`, `.work/source-name-inventory.json`
and `.work/source-name-checks.log`.

## Streaming diagnostics: 1.2.0-dev.5

Checked on **2026-09-14**: **110 streaming/media-source/translation tests**
passed. The initial run had 109 passing tests and one cleanup failure: a new log
message checked expiry twice. The decision and log now use the same result; the
entire targeted group passed again with the corrected revision.
New checks verify detected format output, correlation of parallel streams, pool
limits, shared playback, fallback reasons and exclusion of credentials, URLs and
unfiltered exception/metadata contents from diagnostic messages.
Ruff, formatting, Python syntax, mypy (26 modules), offline lock verification and
local Hassfest (Core 2026.9.1, no invalid integration) passed.

All **26 Python modules remain above 95%** combined statement/branch coverage
(minimum 96.25%); unchanged Config Flow remains at **100%**.
Measurements for both changed modules were fully replaced; unchanged modules
reuse SHA-256-verified dev.4 evidence. Local evidence: `.work/diagnostics-tests.log`,
`.work/diagnostics-final-tests.log`, corresponding `*-inventory.json`,
`.work/diagnostics-verified-coverage.json` and `.work/diagnostics-checks.log`.

Python 3.14.7 / HA 2026.9.1. Receiver/browser requests are simulated; existing
synthetic FFmpeg media tests remain included. No new full-suite, remote CI or
real SF8008/browser acceptance run for this revision. Quality checklist reviewed:
no new platform/dependency or reduction of existing criteria; real-device
acceptance remains outstanding.

## Multiple external streams: 1.2.0-dev.4

Verified on **2026-09-14** in the existing feature worktree. **104 streaming,
media-source and translation tests** and **64 setup/options tests** passed.
The groups partially overlap. Also passed: Ruff, formatting, mypy (26 modules),
Python syntax, offline lock verification, **8 frontend tests** and local Hassfest
on the Core **2026.9.1** validation checkout.

New cases check two browser URLs continuing to play different channels, five
concurrently reserved slots and rejection of the sixth start without eviction,
configurable limits and 0 = unlimited, shared live TV (including pending startup),
independent recording playback, releasing expired or failed sessions and unloading
while starts are pending. Cancelling one viewer does not cancel startup shared
with another. Existing codec/HLS checks with real synthetic media still pass.

Config flow reaches **100% statement/branch coverage**; all **26 modules exceed
95%** (minimum 96.25%). Both changed Python modules were measured again in
full and their previous measurements replaced. Unchanged modules retain earlier
evidence; SHA-256 checks confirm file identity and that tested Linux copies match
the worktree. No new full-suite, remote CI or HACS run. Local evidence:
`.work/pool-tests.log`, `.work/pool-config-tests.log`, their `*-inventory.json`,
`.work/pool-verified-coverage.json` and `.work/pool-hassfest.log`.

Python 3.14.7 / HA 2026.9.1. Receiver and browser/Cast HTTP requests are simulated.
The actual number of usable tuners/encoders and simultaneous browser playback
on the SF8008 have not yet been tested for this version.

## Automatic stream processing: 1.2.0-dev.3

Verified on **2026-09-14** in the existing feature worktree. **340 Python
tests passed in the full run**; one new error-path test failed because its mock's
`__aexit__` swallowed the expected exception. The mock was corrected. Subsequently,
**89 targeted tests passed**, including that case, the final HTTPS
safeguard and improved ffprobe cleanup. The final check uses an
isolated copy of the final changes; SHA-256 comparisons confirm that it matches
the worktree. Measurements for the two production modules changed after the full
run were replaced completely by the final targeted measurements. Unchanged
modules retain their verified full-suite evidence.

All **26 integration modules exceed 95%** combined statement/branch coverage
(minimum 96.25%); config flow reaches 100%. Ruff, formatting, mypy, Python
syntax, offline lock verification, **8 frontend tests** and local Hassfest on the
Core **2026.9.1** validation checkout passed. No dependency changes. Remote CI
and HACS were not rerun.

Tests use real synthetic media: MPEG-2/MP2 with full conversion, H.264/AAC copied
without encoding, H.264/MP2 with audio-only conversion, and direct receiver HLS
relay without an FFmpeg encoder. Codec detection runs actual ffprobe; locally
produced HLS segments are decoded. Receiver endpoints are local HTTP test servers.
Additional checks cover missing/unsuitable receiver outputs, external playlist
addresses, authentication, size limits, token replacement during a request,
preserving HTTPS, probe cancellation and compatibility fallback.
Runtime: Python 3.14.7 / HA 2026.9.1.

Local evidence: `.work/optimized-full-tests.log`, `.work/optimized-corrected-tests.log`,
the associated `*-inventory.json`, `.work/optimized-verified-coverage.json` and
`.work/optimized-hassfest.log`. No new tests on the actual receiver; hardware
transcoding, browser picture/audio and CPU load of the optimized path remain
unverified. The user's Firefox/Edge report covers `dev.2`.

## Browser MIME correction: 1.2.0-dev.2

Fixed on **2026-09-14** after the user's unsupported-media report in Firefox
and Edge. Home Assistant's media dialog selects its HLS player only for the
exact value `application/x-mpegURL`; this integration previously reported
`application/vnd.apple.mpegurl`. Rejection happened during player selection,
before any actual decoding.

**39 targeted streaming, media-source and translation tests passed**,
including real FFmpeg conversion of synthetic media. A regression test now
explicitly checks HA's expected MIME spelling in the resolved media result and
HTTP header rather than merely comparing the same constant. The streaming
module again reaches 100% statement/branch coverage. Ruff, formatting, mypy
(24 modules), Python syntax and offline lock checks passed; no dependencies
changed. No new full-suite/CI run. Earlier full-suite evidence below remains
tied to `dev.1`.

Tests used Python 3.14.7 / HA 2026.9.1 and a SHA-256-verified Linux copy.
Local evidence: `.work/browser-mime-tests.log` and `.work/browser-mime-inventory.json`.
The user subsequently confirmed playback in Firefox and Edge. Starting a second
stream ended the first after its buffer drained, as expected. This user report
covers the previous full conversion; it does not validate receiver HLS, optimized
processing, Safari or Cast.

## External playback: 1.2.0-dev.1

Checked on **2026-09-14**, on branch `feature/external-media-playback` in worktree
`V:\enigma2-connect-worktrees\external-media-playback`. Unreleased development
version; no release, CI or device approval.

- The full run passed **291 Python tests**. After adding CORS and HEAD,
  **35 targeted streaming/media-source tests** passed. The changed
  streaming module's earlier coverage data was discarded and measured afresh;
  unchanged modules retain their full-suite evidence.
- **100% statement/branch coverage** for config flow and the new `media_stream.py`;
  all **24 modules above 95%** (minimum 96.25%). The existing Silver gate
  passed without weakening its requirements.
- Ruff, formatting, mypy (24 modules), Python syntax and **8 frontend tests**
  passed. Local Hassfest using the available Core **2026.9.1** checker found
  one integration and no invalid integrations. HACS and remote CI were not
  rerun for this unpublished state.
- Manifest, `pyproject.toml`, both changelogs and `uv.lock` versions agree.
  `uv lock --offline` and `uv lock --check --offline` passed; only the local
  project version changed in the lockfile. Local Markdown link targets and
  `git diff --check` were verified.

Runtime: **Python 3.14.7, Home Assistant 2026.9.1,
pytest-homeassistant-custom-component 0.13.364** in the existing WSL environment.
Receiver and Cast HTTP requests are simulated. The FFmpeg test actually generates
MPEG-2/MP2 media, converts it through the authenticated local relay into H.264/AAC
HLS, then checks codecs, resolution and error-free segment decoding. Automated
checks cover tokens, CORS, HEAD, filename/path restrictions, redirect refusal,
byte ranges, HTTPS destination selection, startup errors, expiry, replacement,
HA shutdown and unload. No receiver commands were sent.

The initial slow Windows-mount run was interrupted after 143 passing tests and
does not count as a complete suite. The full suite and final media checks used a
SHA-256-verified temporary Linux copy of the worktree. Local reports are
`.work/external-linux-tests.log`, `.work/external-final-tests.log`,
`.work/external-final-inventory.json` and `.work/external-hassfest.log`; they are
not distributed.

**Outstanding device acceptance:** picture/audio on actual browsers and Cast
devices, access through the chosen HA URL/certificate chain, real receiver
streaming authentication, tuner/decryption availability, prolonged playback
and CPU load. Verify these separately before approving particular devices.
Earlier evidence below remains tied to its original versions.

## Synchronizing develop with main – 1.1.4-dev.1

Current `main`, including PR #6 and #8, has been incorporated into development.
The monitor implementation, workflow and tests match `main`; the social preview
and branch rules from `develop` remain unchanged. Conflicts only affected version
metadata and both changelogs; the development version is synchronized at
1.1.4-dev.1. Existing validation evidence from both branches is retained.
70 offline blog tests, Python syntax, version consistency and the lockfile were
checked after integration. Integration code and the quality checklist are
unchanged; no additional receiver or Home Assistant runtime tests were performed.

## Silent blog reviews – 1.1.3

70 offline script tests passed. New cases cover entirely uneventful results
without issues, mixed findings with an independent improvement, uncertainty
still reported for review, publication failure alongside silent success, failed
state persistence and invalid review receipts. After reloading state, unchanged
posts stay completed while edited content becomes eligible again. Python syntax
and Ruff passed.

The four stored real Junie responses from
[run 35125959582](https://github.com/topic2k/enigma2-connect/actions/runs/35125959582)
were replayed locally through the new completion logic: four silent receipts,
no issue calls, no retries and no selection the following Monday. This neither
changed GitHub state nor called AI services. Live deployment of this filter has
not yet been verified by this replay.

The quality checklist is unchanged: integration code (except metadata version),
frontend, integration tests and coverage thresholds are unaffected. No new
receiver or Home Assistant runtime checks were performed; existing outstanding
evidence remains outstanding. Current successful CI checks are required before merge.

## Automated Junie monitor – 1.1.2

64 offline script tests cover individual post packets, first and second failures,
partial success, next-day retry, wrong post IDs, fabricated source citations,
independent enhancement proposals, usage metadata and side-effect-free dry runs.
Ruff, Python syntax, workflow/shell syntax, lock consistency and version/documentation
links passed. Existing retry logic is reused across the separated jobs.

The quality checklist was reviewed for impact: no change to integration behavior,
coverage requirements or outstanding hardware and Home Assistant evidence.
The [complete dry run 35123242339](https://github.com/topic2k/enigma2-connect/actions/runs/35123242339)
at `57e825a` passed with four separate assessments. Modbus lists 2026.9,
2026.10 and 2027.10; selectors correctly have no announced version; OAuth2 and
lawn mowers list 2026.10. All four German assessments match their posts, with
no impact or concrete optional benefit for the existing OpenWebif integration.
These classifications were checked manually against blog texts and code.
Positive impacts and concrete enhancement proposals are covered by simulated
validation tests, not yet by a matching current live blog case.

Reported model costs for the whole dry run: **0.307334 USD** for four posts,
with no missing usage. This is distinct from a confirmed top-up deduction.
The state branch remained at `fa6aa32`; no issues were created. Production-style
analysis, collection, validation and report generation are therefore live-tested.
Full CI at `57e825a` (Tests, hassfest, HACS and CodeQL) was green. Only two offline
edge-case tests and documentation evidence were added afterwards; current green
checks remain required for the final PR revision before merge.

## Junie single-post trial on 2026-09-16 – 1.1.2-dev.4

[Run 35120165171](https://github.com/topic2k/enigma2-connect/actions/runs/35120165171)
at `a6e4ba7` succeeded: 52 script tests followed by a live assessment of one
Modbus post. The Junie job took 1 minute 50 seconds; CLI execution took about
69 seconds. The prepared context was unchanged.

The German response matches the post and includes all three milestones:
availability in 2026.9, deprecation in 2026.10 and removal in 2027.10.
The `no-impact` assessment matches the supplied OpenWebif-based code, which
uses neither Modbus components nor `modbus-connection`. Optional improvement
was assessed independently as `none`, with no concrete benefit identified.
Empty evidence lists are valid for these classifications. Automatic checks
validated schema, post identity and citation format; topic association,
deadlines and reasoning were also reviewed manually.

Junie's `llmUsage` and `taskCostUsd` report **0.0483518 USD**. Reported tokens:
65,759 input, 145,549 cached input and 6,475 output. The main model was
`gemini-3.7-flash`, with helper models `gpt-4.1-mini-2025-04-14`,
`gpt-4.1-2025-04-14` and `gpt-5.4-nano`. The default model is dynamic;
this successful JetBrains access was therefore not a Gemini-independent trial.
The top-up display remained at 3.77 credits when rechecked. This does not mean
the call was free; the actual account deduction is not yet demonstrated there.
Four equally priced posts per week would cost approximately 0.77 USD over four
weeks, without a guarantee for different posts or models.

Local syntax, Ruff, workflow/shell, lock, version/documentation-link checks
passed, alongside an offline check of preparation, report rendering and wrong
post-ID rejection. All 52 script tests passed locally and on GitHub. These
checks do not replace receiver or Home Assistant practice tests. Integration
behavior and quality criteria were unchanged.

One negative relevance case does not establish quality for required migrations
or useful enhancements. The other three individual assessments remain pending.
No issues, state writes, production switch, extra purchases, plan changes,
merges or releases.

## Cloudflare follow-up on 2026-09-16 – 1.1.2-dev.3

The authorized next-day trial started at 08:30 CEST. After a fresh dashboard
reload, Cloudflare showed **0/10,000 neurons today** before the request; the
separate 24-hour chart showed about 10,020 neurons from the previous day.
This does not prove that the server-side access restriction had reset.

The [selector trial 35064196248](https://github.com/topic2k/enigma2-connect/actions/runs/35064196248)
at `fb1b55b` passed its 52 script tests, but its single Cloudflare request was
rejected with **HTTP 429 / internal code 4006**. Input: 267,346 bytes. No model
results or usage metadata were returned. Unknown usage is not measured zero usage.

Stopped as authorized for quota errors: no OAuth2 or lawn-mower requests and no
additional Modbus deadline test. The [official error list](https://developers.cloudflare.com/workers-ai/platform/errors/)
lists 3036 for daily allocation exhaustion and 3040 for capacity shortages,
but does not list 4006. The exact reason for the dashboard/API discrepancy
therefore remains unresolved.

The 2026-09-15 quality assessment still applies: per-post association improved
for Modbus, but 2027.10 was omitted. The other three individual assessments
remain unverified. No production switch, issues, state writes, new credentials,
plan changes or releases. This documentation update affects no integration
behavior or quality criteria; unrelated local changes were preserved.

## Cloudflare per-post trial – 1.1.2-dev.2

On 2026-09-15, per-post processing passed 52 local script tests, Ruff, Python
syntax, lockfile and workflow/documentation checks. Tests verify one post ID per
API call, rejection of foreign IDs and retention of completed results and usage
when a later request fails. The quality checklist and integration runtime are unchanged.

The live [Modbus trial 34993573743](https://github.com/topic2k/enigma2-connect/actions/runs/34993573743)
at `6ab68a7` used 70,336 input / 541 output tokens and 2,274.84 neurons. The German
explanation belongs to the correct post and no-impact agrees with the absence of
Modbus usage. No irrelevant source evidence is cited. The removal deadline
**2027.10** is still missing; only 2026.10 is reported. Four similar requests
would use approximately 9,100 neurons; five would use 11,375, exceeding the daily
free allocation. This is an estimate, not a usage guarantee for other posts.

The 2026-09-16 follow-up is documented above; the other three individual
assessments remain pending because the API rejected the request. No production
provider change, issues, state updates or releases.

## Cloudflare trial – 1.1.2-dev.2

On 2026-09-15, Cloudflare Workers AI and `@cf/openai/gpt-oss-120b` were tested
on an isolated branch using the four stored September posts. 50 local script tests,
Python syntax, Ruff, lockfile and 72 documentation links passed. Branch CI at
`b1ff764` and `f771ab5` passed. Quality checklist impact review: integration runtime,
criteria and coverage thresholds are unchanged; no new HA/receiver hardware evidence.

- Initial run [34991469621](https://github.com/topic2k/enigma2-connect/actions/runs/34991469621):
  successful API response, but parser error. The adapter was corrected against an
  actual small diagnostic response and verified offline.
- Full run [34992280735](https://github.com/topic2k/enigma2-connect/actions/runs/34992280735):
  72,212 input / 1,975 output tokens, 2,432.30 neurons. Schema and source-line checks
  passed, but prose was English, deadlines missing and license citations irrelevant.
- Refined instructions, run [34992652727](https://github.com/topic2k/enigma2-connect/actions/runs/34992652727):
  72,344 input / 1,957 output tokens, 2,435.27 neurons. German prose and empty rather
  than irrelevant evidence, but explanations were mixed up between Modbus, selectors
  and OAuth2. The Modbus removal deadline 2027.10 was still missing; the selector
  post received a version that its text did not state.

**Assessment:** Access and free-tier budget work for a combined weekly request.
Structural validation does not detect semantically misassigned explanations.
The tested model and batch approach are not sufficiently reliable to replace the
scheduled monitor. No issues published, state updates or main-branch deployment.
State remained at `fa6aa32eda38a2454d30fd3b11aab0d8198dc972`. Per-post analysis or another
model needs a separate quality and budget trial. These four no-impact examples
provide no evidence of long-term availability or reliable detection of real impact.

## Blog check retries – 1.1.1

On 2026-09-14, 45 offline tests passed, including 17 new scheduler/state tests.
Coverage includes non-error first failures, second failures on the following day,
no duplicate same-day attempts, late catch-up, partial successes, original post
content during retries, manual recovery and GitHub state writes protected against
lost updates. Ruff, formatting, Python syntax and offline lock verification
(159 packages) passed. Tests simulate Google, GitHub and multiple calendar days;
they do not establish an actual next-day scheduled run or additional Home Assistant/
receiver acceptance. PR CI checks the complete repository state.

Checked on **2026-09-13**. Shared development version: **1.1.0-dev.10**.
This is a technical report, not release or hardware approval. Version history:
[changelog](../CHANGELOG.en.md). Reproduction commands:
[developer guide](DEVELOPMENT.en.md#development-environment-and-checks).

Release **1.1.0** carries this development state forward with a stable version
and updated release documentation. The hardware evidence below remains tied to
its stated versions and test conditions; publication does not extend its scope.
CI evidence for the final commit is recorded in [release 1.1.0](https://github.com/topic2k/enigma2-connect/releases/tag/v1.1.0).
Actual Bonjour discovery, automatic DHCP receipt in running HA and subjective
picture/audio playback remain pending.

## README badges: 1.2.0-dev.11

Locally checked on **2026-09-16**: YAML structure and publication guards,
unchanged existing CI checks, six statement/branch coverage extraction cases
and ten simulated GitHub API cases. Checks covered initial publication,
updates preserving history/files, superseded runs, permission errors, missing
commits and invalid measurements. Python syntax, version consistency and
`uv lock --check --offline` passed.
The nine already available badge URLs return HTTP 200 and the expected labels;
the coverage endpoint awaits its first publication. Shields rejected the default
Python client with HTTP 403; the read-only check with an identified test client
succeeded. This does not verify image display inside the chat.

Quality checklist reviewed: `docs-installation-instructions` covers the updated
HACS guide; `config-flow-test-coverage` and `test-coverage` retain their existing
checks and thresholds. Runtime code and HA compatibility are unchanged.
GitHub release `v1.1.0` and absence from the default HACS catalog were confirmed
with read-only queries. This did not include an actual HACS installation.

API checks are simulations, not a successful GitHub publication run. The [test run on `516424f`](https://github.com/topic2k/enigma2-connect/actions/runs/35135496532)
passed Ruff, formatting, mypy, Python/frontend tests, coverage gates and the new
extraction step. [Hassfest and HACS](https://github.com/topic2k/enigma2-connect/actions/runs/35135496450)
also passed. The subsequent evidence update changes only these two verification
summaries. Publication was correctly skipped on `develop`; the first write to
the `badges` data branch remains pending. The coverage endpoint becomes available only after successful `main`
tests with the new workflow. Earlier CI and hardware evidence below remains
limited to the versions stated there.

## Dependabot: cryptography and CVE-2026-69247

[Dependabot alert 1](https://github.com/topic2k/enigma2-connect/security/dependabot/1)
reports `cryptography 48.0.1` in `uv.lock`. According to the
[upstream advisory](https://github.com/pyca/cryptography/security/advisories/GHSA-g6cj-pr64-35w5),
PKCS#7 EnvelopedData decryption functions from version 44 and before 50 are
affected; version 50 fixes distinguishable errors and timing during RSA key
decryption. Searching the integration code found no calls to these functions.
This does not assess every feature of a production Home Assistant installation.

Here, the dependency enters through the development group and HA test package.
Both HA 2026.9.1 and the checked current 2026.9.2 still require cryptography 48.0.1
and pyOpenSSL 26.2.0. The documented uv override replaces these in the test stack
with **cryptography 50.0.1** and **pyOpenSSL 26.4.0**. The latter allows cryptography
from 49 and below 51 according to its package metadata. All other package records
remain unchanged from `80f9eda`; only these two packages and the project version
changed in the lockfile. The override applies to development/CI, not an installed
HA runtime. Integration requirements in the manifest remain empty.

The full [CI on `65be728`](https://github.com/topic2k/enigma2-connect/actions/runs/34772846926)
confirmed installation of cryptography 50.0.1 and pyOpenSSL 26.4.0. **270 Python tests**
passed in 8.45 seconds, along with **8 frontend tests**, Ruff, formatting, mypy
and the coverage gate: config flow 100%, all 23 modules above 95%.
[Hassfest and HACS](https://github.com/topic2k/enigma2-connect/actions/runs/34772846924)
also passed. Local checks covered documentation, syntax, versions and the limited
package changes. The additional run in the separate `.work/security-env` environment
was stopped after successful CI and is not counted as a passed local full test.
Earlier receiver evidence still applies to its original package versions. The Dependabot
alert on the default branch remains open until the fix is merged into `main`;
it is not manually dismissed as a false positive.

## GitHub CI and the FFmpeg prerequisite

**Node.js 24 migration in 1.1.0-dev.9:** All direct uses of `checkout@v4`,
`setup-uv@v6` and `upload-artifact@v4` were replaced with `v7`, `v10.1.0` and `v7`,
respectively. Action metadata for the reviewed releases
[Checkout 7.0.1](https://github.com/actions/checkout/blob/v7.0.1/action.yml),
[setup-uv 10.1.0](https://github.com/astral-sh/setup-uv/blob/v10.1.0/action.yml) and
[Upload Artifact 7.0.1](https://github.com/actions/upload-artifact/blob/v7.0.1/action.yml)
declares `node24`. Workflow triggers, permissions, upload path and retention are
preserved. This replaces deprecated action versions previously forced to run on
Node.js 24 by GitHub ([migration notice](https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/)).
The blog monitor and its upload step remain intentionally skipped on branch pushes;
CI verification does not start their external API execution.

The first `quality-scale` push, commit `0fe1cb2`, passed
[Hassfest and HACS](https://github.com/topic2k/enigma2-connect/actions/runs/34771537254)
and the [blog-monitor tests](https://github.com/topic2k/enigma2-connect/actions/runs/34771537165).
The [test run](https://github.com/topic2k/enigma2-connect/actions/runs/34771537046)
passed Ruff, formatting, mypy and 269 tests; one test was skipped because FFmpeg
was missing. Consequently, the Silver coverage gate failed for
`recording_snapshot.py` at 92.45%, while config flow reached 100%.
Version **1.1.0-dev.8** explicitly installs FFmpeg and verifies its invocation in
CI. Coverage thresholds and integration behavior remain unchanged.

**Correction passed on commit `ffdf007`:** The
[test workflow](https://github.com/topic2k/enigma2-connect/actions/runs/34771754492)
passed **270 Python tests without skips** in 13.44 seconds and **8 frontend tests**.
Ruff, formatting and mypy passed. Config flow reaches 100% statement/branch
coverage, all 23 modules exceed the 95% threshold, and `recording_snapshot.py`
now reaches 99.06% combined coverage.
[Hassfest and HACS](https://github.com/topic2k/enigma2-connect/actions/runs/34771754483)
also passed. Blog-monitor test code was unchanged from the successful run linked
above. This evidence applies to the stated commit; subsequently documenting the
result does not change integration code.

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

## Social preview – 2026-09-14

Exported and visually checked the new 1280 × 640 GitHub image for 1.1.2-dev.1.
Checked PNG dimensions, fully opaque background, SVG structure and reproducible
export using `-SocialOnly`. The eight HA brand files and integration logic remain
unchanged, so the quality checklist is unaffected. No new HA/receiver test.
Source and export instructions: [Branding](../assets/branding/README.md).
