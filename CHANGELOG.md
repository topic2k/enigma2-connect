[Deutsch](CHANGELOG.md) | [English](CHANGELOG.en.md)

# Changelog

## Inhaltsverzeichnis

- [1.1.2-dev.1](#112-dev1)
- [1.1.1](#111)
- [1.1.0](#110)
- [1.0.2](#102)
- [1.0.1](#101)
- [1.0.0](#100)

## 1.1.2-dev.1

Unveröffentlichte Entwicklerversion.

- GitHub-Social-Preview in 1280 × 640 Pixeln ergänzt: Gerätesymbol mittig über
  der Wortmarke auf weißem Hintergrund, mit PNG, SVG-Quelle und `-SocialOnly`-Export.
- Aufgaben auf eigenen Branches bearbeiten, umfangreichere Aufgaben zusätzlich
  in eigenen Worktrees. Fertige Änderungen geprüft nach `develop` übernehmen
  und pushen. PR-Vorbereitung und PR nach `main` erst nach Nutzerfreigabe;
  Merge und Release erfordern ebenfalls die jeweils ausdrückliche Freigabe.

## 1.1.1

Unveröffentlicht.

- Fehlgeschlagene Blogbeiträge werden nach dem wöchentlichen Check dauerhaft
  vorgemerkt und am Folgetag erneut versucht. Erst ein zweiter Fehlschlag für
  denselben Inhalt macht den Lauf rot; Teilerfolge werden separat abgeschlossen.
- Statusbranch mit Versuchszähler und Originalbeitrag, täglicher Nachholtermin
  ohne neue Beitragsauswahl und manueller Neustart nach zwei Fehlern. Berichte
  unterscheiden Gemini-, Antwortvalidierungs- und GitHub-Veröffentlichungsfehler.

## 1.1.0

Veröffentlicht am 13.09.2026.

- Geprüften Qualitätsstand als Version 1.1.0 freigegeben. Echte Bonjour-Erkennung,
  automatischer DHCP-Empfang in laufendem Home Assistant und die subjektive
  Bild-/Tonprüfung bleiben als offene Praxisnachweise dokumentiert.

- Verwundbare transitive Testabhängigkeit `cryptography 48.0.1` durch `50.0.1`
  ersetzt (CVE-2026-69247); `pyOpenSSL` auf das passende `26.4.0` angehoben.
  Die befristete uv-Ausnahme für Home Assistants feste Versionsvorgaben ist
  dokumentiert und betrifft ausschließlich die Entwicklungs-/Testumgebung.

- GitHub Actions auf Node.js 24 umgestellt: `checkout@v7`, `setup-uv@v10.1.0` und
  `upload-artifact@v7` in allen betroffenen Workflows. Die veralteten
  Node.js-20-Action-Versionen werden damit ersetzt.

- FFmpeg wird vor den CI-Tests ausdrücklich installiert und aufgerufen, damit
  der Test zur tatsächlichen Aufnahmebild-Extraktion nicht übersprungen wird.
  Die Grenze von über 95 % Abdeckung pro Integrationsmodul bleibt unverändert.
  Die korrigierte CI besteht 270 Python- und 8 Frontend-Tests sowie Hassfest/HACS;
  CI-Nachweise und abgehakte Prüflisten sind dokumentiert.

- Tatsächlichen DHCP-Adresswechsel am Octagon geprüft: Fehlende MAC-Daten nach
  dem Schnittstellen-Neustart verhindern die Übernahme erwartungsgemäß. Nach
  GUI-Neustart bestanden Identitätsprüfung und Adressübernahme mit erhaltenen
  Kennungen, Anmeldung und HTTPS-Einstellungen. Regressionstest und Bedienhilfe
  ergänzt; automatischer Empfang der DHCP-Meldung bleibt separat offen.

- Aufnahme-Snapshot und zwölf begrenzte Bedienprüfungen am Octagon bestanden;
  ursprüngliche Lautstärke, Stummschaltung und vorhandene Timer/Aufnahmen erhalten.

- Markenbilder, Symbole, deaktivierte Signaldiagnosen und Optionsdialoge in der
  echten HA-Oberfläche geprüft; FFmpeg-Reparaturhinweis und Abhilfe auf Deutsch
  und Englisch erfolgreich kontrolliert.
- HTTPS am echten Octagon einschließlich Zertifikatsablehnung und vollständigem
  HA-Leseablauf geprüft; ein begrenzter Live-Stream-Ausschnitt liefert dekodierbares
  1080p-Video und Mehrkanalton ohne Senderwechsel. Native Bonjour-Beobachtung,
  verbleibende Hardware-Grenzen und Remote-Abgleich sind dokumentiert.
- Neuere Änderungen von `main` einschließlich Blog-Monitor-Korrektur und
  Optionsdialog-Test übernommen; bestehende Versionshistorie erhalten.

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

## 1.0.2

Unveröffentlicht.

- Der Blog-Workflow verwendet Gemini 3.8 Flash mit niedriger Denkstufe und
  den aktuellen Anfrageparametern. Der erste echte Aufruf von Gemini 2.5 Flash
  hatte HTTP 404 geliefert. Wochenrhythmus und feste Anfragegrenzen bleiben erhalten.

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
