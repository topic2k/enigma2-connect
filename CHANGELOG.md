[Deutsch](CHANGELOG.md) | [English](CHANGELOG.en.md)

# Changelog

## Inhaltsverzeichnis

- [1.0.1](#101)
- [1.0.0](#100)

## 1.0.1

Unveröffentlicht.

- Wöchentlicher GitHub-Workflow prüft neue und geänderte Home-Assistant-Blogbeiträge
  ab September 2026 mit Gemini anhand des Integrationscodes. Er bewertet nötige
  Anpassungen und sinnvolle Ergänzungen unabhängig mit Nutzen, Umsetzungsschritten
  und überprüften Code-Belegen. Höchstens eine KI-Anfrage für fünf Beiträge je Lauf;
  zusammengefasste Berichts-Issues vermeiden doppelte Prüfungen.
- Einrichtung mit einem Google-Free-Tier-Projekt, manueller Probelauf und
  lokale Vorbereitung ohne KI-Aufruf sind dokumentiert. Offline-Tests prüfen
  Auswahl, Antwortvalidierung, Verbesserungsvorschläge und Fehlerfälle.
- Der Optionsdialog-Test isoliert den automatischen Neuladevorgang und prüft
  dessen Aufruf, damit kein Hintergrund-Timer den CI-Testabschluss stört.

## 1.0.0

Veröffentlicht am **13.09.2026**.

Erste öffentliche Veröffentlichung von Enigma2 Connect:

- Home-Assistant-Integration für Enigma2/OpenWebif mit Medienplayer,
  Fernbedienung, Sender- und Bouquetwahl, Sensoren, Kalender, Bildschirmfoto,
  Nachrichten und Receiver-Aktionen.
- Aufnahmen und optional Sender in den Home-Assistant-Medienbrowsern,
  einschließlich Receiverzuordnung und optionalen Vorschaubildern.
- Grafisch konfigurierbare Fernbedienungskarte für das Dashboard.
- Konfigurationsfluss, Optionen, Reauthentifizierung, Mehrgerätebetrieb sowie
  deutsche und englische Dokumentation.
