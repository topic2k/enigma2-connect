[Deutsch](CHANGELOG.md) | [English](CHANGELOG.en.md)

# Changelog

## Inhaltsverzeichnis

- [1.1.0-dev.4](#110-dev4)
- [1.0.0](#100)

## 1.1.0-dev.4

Unveröffentlichte Entwicklerversion.

- Lesende Hardware-Abnahme am Octagon SF8008 mit HA 2026.9.1 nachgewiesen:
  neun Plattformen, aktivierte Entitäten verfügbar, Signaldiagnosen deaktiviert,
  Aktualisierung, Duplikatschutz und Entladen erfolgreich. Screenshot und Picon
  sind dekodierbar. Handbücher und Prüfübersicht unterscheiden diesen Nachweis
  von den weiterhin offenen Netzwerk-, Oberflächen- und Bedienungsprüfungen.

- Wiederverwendbare, ausdrücklich gestartete Receiver-Abnahme mit isoliertem
  Home Assistant: Einrichtung, Entitäten, deaktivierte Signaldiagnosen,
  Aktualisierung, Duplikatschutz und Entladen. Eine Positivliste sperrt
  Receiver-Schreibbefehle; Berichte enthalten Versionen und einen Quelltext-Hash,
  aber keine Zugangsdaten. Der Helfer wurde mit simulierten Antworten geprüft;
  die lesende Abnahme am echten Octagon SF8008 ist inzwischen bestanden.

- OpenWebif-Dienste mit Bonjour-Namen werden zur Einrichtung vorgeschlagen.
  DHCP aktualisiert bekannte Receiver-Adressen erst nach bestätigter MAC-Identität;
  Zugangsdaten, Port, TLS-Einstellungen und Entitätskennungen bleiben erhalten.
- Diagnosen funktionieren auch ohne geladenen Receiver und bei Teilausfällen.
  Fehlendes FFmpeg erhält einen übersetzten Reparaturhinweis mit Abhilfeschritten.
  Optionale Signaldiagnosen sind bei neuen Entitäten zunächst deaktiviert.
- Entitätssymbole aus `icons.json`, Geräte-Lebenszyklus und lokale Markenbilder
  werden geprüft; beide Handbücher erläutern Erkennung, Aktualisierung und Geräteumfang.
- Sämtliche 23 Integrationsmodule sind strikt typisiert; mypy 2.3.1 wird als feste
  Entwicklungsabhängigkeit in CI ausgeführt. Receiver-Metadaten bleiben eine
  ausdrücklich gekennzeichnete flexible JSON-Grenze.

- Wöchentlicher GitHub-Workflow bewertet neue und geänderte Home-Assistant-
  Blogbeiträge ab September 2026 mit Google Gemini anhand des Integrationscodes.
  Neben Kompatibilitätsanpassungen bewertet jeder Beitrag unabhängig sinnvolle
  Ergänzungen und Verbesserungen mit Nutzen, Umsetzungsschritten und Code-Belegen.
  Höchstens eine KI-Anfrage für fünf Beiträge pro Lauf, zusammengefasste
  Berichts-Issues, überprüfte Code-Verweise und Duplikatschutz begrenzen Aufwand
  und Wiederholungen. Vorbereitung ohne KI-Aufruf und Dokumentation zur Nutzung
  eines eigenen Google-Free-Tier-Projekts; Kontingentfehler lassen Beiträge offen.

- **Listen aktualisieren** wartet auch bei direkt wiederholten Aufrufen auf einen
  neuen Abruf und meldet Verbindungsfehler als übersetzte Aktionsfehler.
- Zusätzliche Transport-, Bedienungs-, Bild- und Kalenderprüfungen sichern unter
  anderem Decoderabbruch, Downloadgrenzen, schnelle Senderwechsel, Cachegrenzen
  und fehlerhafte Receiver-/Bildanbieterantworten ab.
- Verbindungsparameter und Verhalten bei teilweiser beziehungsweise vollständiger
  Nichtverfügbarkeit sind in beiden Benutzerhandbüchern erläutert.
- Die CI verlangt zusätzlich über 95 % kombinierte Anweisungs-/Zweigabdeckung
  für jedes Integrationsmodul; die zehn zusätzlichen Silber-Regeln sind intern
  nachgewiesen. Lokale Brand-Dateien erfüllen die aktuelle Vorgabe für Custom-Integrationen.
- Einrichtung, erneute Anmeldung und Neukonfiguration erklären Verbindungsfelder
  jetzt auf Deutsch und Englisch direkt im Dialog.
- Zusätzliche Tests prüfen Fehlerkorrektur im selben Dialog, Geräteidentität,
  doppelte Receiver und das Erhalten von Einstellungen nach Eingabefehlern.
- Aktionsregistrierung ohne Receiver sowie einmalige Ausfall- und
  Wiederverbindungsmeldungen sind durch weitere Lifecycle-Tests abgesichert.
- Qualitätscheckliste mit Nachweisen und offenen Arbeiten für Bronze bis Platin;
  Zweigabdeckung und eine CI-Prüfung für vollständige Konfigurationsfluss-Abdeckung.
  Die Integration bleibt eine Custom-Integration ohne offizielle Qualitätsstufe.

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
