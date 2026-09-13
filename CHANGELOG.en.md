[Deutsch](CHANGELOG.md) | [English](CHANGELOG.en.md)

# Changelog

## Contents

- [1.0.1](#101)
- [1.0.0](#100)

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
