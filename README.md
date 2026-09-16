# Enigma2 Connect

[Deutsch](#deutsch) | [English](#english)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="custom_components/enigma2_connect/brand/dark_logo@2x.png">
  <img src="custom_components/enigma2_connect/brand/logo@2x.png" alt="Enigma2 Connect" width="720">
</picture>

## Deutsch

Bediene deinen Enigma2-Receiver direkt in Home Assistant: Sender wechseln,
Lautstärke regeln, Aufnahmen auf dem Fernseher abspielen und Nachrichten anzeigen.
Eine optionale Fernbedienungskarte bringt die wichtigsten Tasten ins Dashboard.

### Was du brauchst

- Home Assistant **2026.9 oder neuer**.
- Einen Enigma2-Receiver mit aktiviertem **OpenWebif ab Version 1.4.4**, der von Home Assistant erreichbar ist.
- Die Adresse und gegebenenfalls die Zugangsdaten deines Receivers.

Der verfügbare Funktionsumfang hängt zusätzlich vom Receiver und dessen Firmware ab.

Die Bedienoberfläche ist auf Deutsch und Englisch verfügbar.
Aufnahmen laufen auf dem Receiver. Optional lassen sich Live-TV und TS-Aufnahmen
über Home Assistant auf HLS-fähigen Browsern und Mediengeräten abspielen.
Bei geeigneten abgeschlossenen TS-Aufnahmen ist Spulen über die gesamte Aufnahme möglich.
Voraussetzungen und Grenzen stehen im [Benutzerhandbuch](docs/BENUTZERHANDBUCH.md#auf-anderen-geräten-abspielen).

### Erste Schritte

1. Prüfe, ob du OpenWebif im Browser öffnen kannst.
2. Kopiere den Ordner `custom_components/enigma2_connect` nach
   `/config/custom_components/enigma2_connect` und starte Home Assistant neu.
3. Öffne **Einstellungen → Geräte & Dienste → Integration hinzufügen** und
   suche nach **Enigma2 Connect**.
4. Trage die Adresse, den OpenWebif-Port und bei Bedarf die Zugangsdaten ein.
5. Füge den Medienplayer deines Receivers deinem Dashboard hinzu.

Weitere Receiver kannst du auf dieselbe Weise hinzufügen. Aufnahmen findest du
unter **Medien → Enigma2 Connect**, Timer im Kalender von Home Assistant.

### Anleitungen und Hilfe

- [Benutzerhandbuch](docs/BENUTZERHANDBUCH.md): Einrichtung, Bedienung,
  Fernbedienungskarte, Automationen und Hilfe bei Problemen.
- [Entwicklerdokumentation](docs/ENTWICKLUNG.md): Projektaufbau, Entwicklungsumgebung und Tests.
- [Changelog](CHANGELOG.md) und [Release-Anleitung](RELEASING.md).
- [Fehler melden](https://github.com/topic2k/enigma2-connect/issues).

Mit Unterstützung generativer KI entwickelt. Lizenz: [Apache-2.0](LICENSE),
ergänzende Hinweise in [NOTICE](NOTICE).

---

## English

Control your Enigma2 receiver directly from Home Assistant: change channels,
adjust the volume, play recordings on your TV and display messages.
An optional remote card brings the main buttons to your dashboard.

### What you need

- Home Assistant **2026.9 or later**.
- An Enigma2 receiver with **OpenWebif 1.4.4 or later** enabled and reachable from Home Assistant.
- Your receiver's address and login details, if required.

Available features also depend on the receiver and its firmware.

The interface is available in German and English. Recordings play on the receiver.
Optionally, live TV and TS recordings can play through Home Assistant on browsers
and media devices that support HLS. Suitable completed TS recordings support
seeking across the full recording. See the [user guide](docs/USER_GUIDE.en.md#play-on-other-devices) for requirements and limits.

### Getting started

1. Check that you can open OpenWebif in your browser.
2. Copy `custom_components/enigma2_connect` to
   `/config/custom_components/enigma2_connect` and restart Home Assistant.
3. Open **Settings → Devices & services → Add integration** and search for
   **Enigma2 Connect**.
4. Enter the address, OpenWebif port and login details, if required.
5. Add your receiver's media player to your dashboard.

Add further receivers in the same way. Find recordings under
**Media → Enigma2 Connect** and timers in the Home Assistant calendar.

### Guides and help

- [User guide](docs/USER_GUIDE.en.md): setup, everyday use, remote card,
  automations and troubleshooting.
- [Developer guide](docs/DEVELOPMENT.en.md): project structure, development environment and tests.
- [Changelog](CHANGELOG.en.md) and [release guide](RELEASING.en.md).
- [Report a problem](https://github.com/topic2k/enigma2-connect/issues).

Developed with assistance from generative AI. License: [Apache-2.0](LICENSE),
with additional information in [NOTICE](NOTICE).
