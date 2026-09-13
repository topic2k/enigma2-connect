[Deutsch](CHANGELOG.md) | [English](CHANGELOG.en.md)

# Changelog

## Contents

- [1.1.0-dev.4](#110-dev4)
- [1.0.0](#100)

## 1.1.0-dev.4

Unreleased development version.

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

- A weekly GitHub workflow assesses new and edited Home Assistant blog posts
  from September 2026 with Google Gemini against the integration code. Each post
  independently assesses compatibility adaptations and useful enhancements with
  benefits, implementation steps and source evidence. At most
  one AI request for five posts per run, combined report issues, validated code
  references and duplicate protection bound usage. Includes preparation without
  AI calls and instructions for a dedicated Google Free Tier project; quota
  failures leave posts pending.

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
