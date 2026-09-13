[Deutsch](CHANGELOG.md) | [English](CHANGELOG.en.md)

# Changelog

## Contents

- [1.1.0-dev.10](#110-dev10)
- [1.0.2](#102)
- [1.0.1](#101)
- [1.0.0](#100)

## 1.1.0-dev.10

Unreleased development version.

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
