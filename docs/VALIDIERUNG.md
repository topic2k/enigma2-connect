[Deutsch](VALIDIERUNG.md) | [English](VALIDATION.en.md)

# Prüfübersicht

Prüfdatum: **13.09.2026**. Gemeinsamer Entwicklungsstand: **1.1.0-dev.4**.
Dies ist ein technischer Prüfbericht, keine Release- oder Hardwarefreigabe.
Versionshistorie: [Changelog](../CHANGELOG.md). Reproduktionsbefehle:
[Entwicklerdokumentation](ENTWICKLUNG.md#entwicklungsumgebung-und-prüfungen).

## Aktuelle lesende Octagon-Abnahme

Am **13.09.2026** wurde der aktuelle Code mit einem **echten Octagon SF8008 4K
Supreme** und Live-HTTP-Zugriff geprüft. Umgebung: **Home Assistant 2026.9.1**,
**Python 3.14.7**, **OpenWebif 2.4.0**, Image **7.6.0.20260831**, Enigma2
**2026-08-30**. Der Erstlauf auf **1.1.0-dev.3** bestand. Die daraus entstandene
Fassung **1.1.0-dev.4** ändert ausschließlich Dokumentation und Versionsmetadaten.

| Prüfung | Ergebnis |
| --- | --- |
| Einrichtung mit tatsächlicher OpenWebif-Anmeldung | Bestanden |
| Plattformen | Alle 9 geladen |
| Aktivierte Entitäten | 17, davon 0 nicht verfügbar |
| Signaldiagnosen | Alle 3 standardmäßig deaktiviert |
| Aktualisierung und Diagnoseexport | Bestanden, keine Fehler optionaler Endpunkte |
| Doppelte Einrichtung | Als bereits eingerichtet abgebrochen |
| Entladen | Erfolgreich, Config Entry nicht mehr geladen |
| Receiver-Aufrufe im HA-Abnahmelauf | 16, ausschließlich lesend |
| Screenshot | JPEG, 720 × 405 Pixel, vollständig dekodiert |
| Senderlogo | PNG, 220 × 132 Pixel, vollständig dekodiert |

Die HA-Instanz verwendete isolierte Test-Fixtures und einen Konfigurationsspeicher
im Arbeitsspeicher; die Receiver-Antworten waren echt. Bilddaten wurden nur im
Arbeitsspeicher dekodiert und nicht gespeichert. Es wurden keine Sender-,
Lautstärke-, Timer-, Aufnahme- oder Energiezustände verändert.

Ein zwölfsekündiger Bonjour-Beobachtungslauf aus WSL lieferte keine passenden
Ankündigungen. Das beweist wegen des Beobachtungswegs nicht, dass der Receiver
keine Dienste ankündigt; der Bonjour-Nachweis bleibt offen. Ebenso offen:
physischer DHCP-Wechsel, HTTPS-Abnahme, laufende Bild-/Tonwiedergabe, Aufnahmebilder,
Bedienaktionen und Sichtprüfung der neuen HA-Oberflächen in beiden Sprachen.

Nachweise: `.work/quality-live/octagon-acceptance-dev3.json`,
`octagon-images.json` und `octagon-discovery.json`. Zugangsdaten liegen nur in der
vom Nutzer bereitgestellten, von Git ignorierten lokalen Datei und werden nicht
in die Prüfübersicht übernommen.

## Ergänzung: wiederholbare Receiver-Abnahme

Stand **1.1.0-dev.3**, **13.09.2026**: Der neue
[Abnahme-Helfer](ENTWICKLUNG.md#lesende-receiver-abnahme) wurde unter
HA 2026.9.1 / Python 3.14.7 geprüft. **6 gezielte Tests bestanden**;
der direkte Hardware-Test ohne Prüfkonfiguration wurde erwartungsgemäß
**einmal übersprungen**. Der vollständige CLI-Aufruf gegen einen lokalen
**simulierten HTTP-Receiver** bestand mit 16 lesenden Anfragen, Anmeldung,
neun Plattformen, drei deaktivierten Signaldiagnosen, Aktualisierung,
Duplikatschutz und erfolgreichem Entladen. Testpasswort und Authentifizierungsheader
erschienen weder in der CLI-Ausgabe noch im Bericht. Ein geschlossener lokaler
Port ergab erwartungsgemäß einen Fehlerstatus und `passed: false`.

Diese Ergänzung verändert keinen produktiven Integrationscode; die vollständige
263-Test-Prüfung unten gehört weiterhin zum dokumentierten Vorgängerstand.
Ruff, Formatierung, Syntax und Lockdateiabgleich wurden erneut geprüft.
Nachweise: `.work/quality-live/tests.log`, `cli-smoke.log`, `simulated-cli.json`
und `refused-final.json`. Dies ist **keine neue physische Receiver-Abnahme**.

Die lesend abgerufenen GitHub-Läufe für Remote-`main` bei
`f3a4e94de7cbc7f9fc6696fc72f5bfd075fd9cf8` waren für
[Tests](https://github.com/topic2k/enigma2-connect/actions/runs/34765832310) und
[Validate](https://github.com/topic2k/enigma2-connect/actions/runs/34765832294)
grün. Sie bestätigen nicht die noch uncommitteten Änderungen auf `quality-scale`;
der CI-Nachweis für deren vorgesehenen Commit bleibt offen.

## Qualitätsskala: Integrationsprüfung

Lokaler Stand **1.1.0-dev.2**, Arbeitsbranch `quality-scale`, **13.09.2026**.
Die interne Checkliste enthält jetzt **54 von 54 Kriterien als umgesetzt**.
Formell bleibt dies eine **Custom-Integration**; eine offizielle Qualitätsstufe
setzt eine gesonderte Prüfung durch Home Assistant voraus.

| Prüfung | Ergebnis |
| --- | --- |
| Vollständige Integrationssuite unter HA 2026.9.1 / Python 3.14.7 | 263 bestanden; 480.66 Sekunden |
| Anweisungen / Zweige / kombiniert | 99.70 % / 97.86 % / 99.29 % |
| Konfigurationsflüsse | 100 % Anweisungen und Zweige; CI-Sperre bestanden |
| Silber-Sperre je Modul | Alle 23 Module über 95 % kombiniert; Minimum 96.25 % |
| Striktes mypy 2.3.1 | Alle 23 Produktionsmodule ohne Fehler |
| Ruff, Formatierung und Python-Syntax | Bestanden |
| JavaScript-Tests der Karte | 8 bestanden |
| Lokales Hassfest für HA 2026.9.1 | 1 Integration, 0 ungültige Integrationen |
| Lockdatei | 159 Pakete; nur lokale Metadaten und fünf mypy-Pakete gegenüber dem bisherigen Bestand geändert |

Der Gesamtlauf enthält die neuen Tests für Bonjour-Bestätigung, DHCP-Identität,
unveränderte TLS-/Anmeldedaten, Adresskonflikte, Diagnosen ohne Laufzeitdaten,
teilweise/offline Receiver, Reparaturhinweise und getrenntes Hinzufügen/Entfernen
von Geräten. Die acht echten PNG-Dateien werden über die lokale HA-Brands-API
ausgeliefert, ohne CDN-Aufruf; Symbolschlüssel stimmen mit dem Entitätskatalog
überein. Die frühere Einschätzung eines zwingend offenen Brands-PRs ist für diese
Custom-Integration durch die [HA-Änderung ab 2026.3][local-brands] überholt.

Netzankündigungen, Receiver und Bildanbieter sind simuliert. Keine neue Prüfung
echter Bonjour-/DHCP-Ankündigungen, physischer IP-Wechsel, aktueller Receiver-
Bild-/Tonwiedergabe oder HA-Oberflächen durchgeführt. Diese Hardware-Nachweise
bleiben vor einer entsprechenden Freigabe offen. Ebenso ist dies kein neuer
GitHub-CI-Lauf. Die separaten Blog-Monitor-Skripttests gehören zum unten genannten
Prüfbericht ihres eigenen Arbeitsumfangs, nicht zur Integrationssuite oben.

Nachweise: `.work/quality-final/full-tests.log`, `coverage.json`, `coverage-gate.log`,
`style-syntax.log`, `frontend.log`, `docs.log` und `hassfest.log`; mypy:
`.work/quality-final/static.log`. Der frühere
260-Test-Lauf und die gezielten 51 Tests liegen unter `.work/quality-gold/`.

[local-brands]: https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/

## Ergänzende Prüfung des Blog-Monitors

Am **13.09.2026**, Stand **1.1.0-dev.2**, wurde die wöchentliche Gemini-Variante
lokal geprüft: **28 Offline-Tests** bestanden unter Windows und WSL/Python 3.14.7,
davon 16 für die KI-Anbindung und
12 für das weiterhin verfügbare heuristische Skript. Die Tests prüfen unter
anderem eine einzelne Anfrage ohne Werkzeuge, Eingabe-/Beitragsgrenzen,
Duplikatschutz auch für geschlossene Berichte ohne Auswirkungen, neue Prüfung
geänderter Beiträge, ungültige Dateiverweise/Zitate und Kontingentfehler ohne
gespeicherte Erfolgsmarker. Neu geprüft sind Empfehlungen trotz `no-impact`, alle
Kombinationen beider unabhängigen Bewertungen sowie fehlende Bewertungen und
ungültige Verbesserungsbelege ohne Issue-Veröffentlichung. Die Vorbereitung mit
den vorhandenen echten Blogquellen ergab vier Beiträge und **273.299 UTF-8-Eingabebytes**
einschließlich Anweisungen und Quelltexten, unter der Grenze von 400.000 Bytes.
Das ist eine Bytezählung, keine gemessene Tokenzahl.

Ruff, Formatierung, Python-Syntax, Workflow-YAML/Bash, Versionsabgleich,
60 lokale Dokumentationslinks und Offline-Lockprüfung (159 Pakete) bestanden. Quellen und
Beitragsauswahl wurden lokal vorbereitet; Gemini-Antworten und GitHub-Issues sind
in den Tests simuliert. `GEMINI_API_KEY` wurde inzwischen in GitHub gespeichert;
AI Studio zeigt für das kostenlose Projekt 20 Anfragen pro Tag und 250.000 Tokens
pro Minute für Gemini 2.5 Flash. **Kein echter Google-API-Aufruf und kein
GitHub-Actions-Lauf**; die Eignung für den konkreten Aufruf ist noch nicht praktisch
bestätigt. Keine zusätzliche HA-/Receiverprüfung für
diese Workflow-Änderung. Lokale Vorbereitungsdaten:
`.work/blog-monitor/gemini-report/request-info.json`.

### Vorherige heuristische Vorprüfung

Am **13.09.2026**, Stand **1.0.1-dev.3**, ausschließlich für den neuen Workflow:

- Zwölf Offline-Tests unter Python 3.14.7 bestanden: API-/Themenabgleich,
  vollständiger Beitragstext, Datum/Entwürfe, Probelauf, paginierte Duplikatsuche
  einschließlich geschlossener Issues, Fehler vor/während Veröffentlichung und
  die Begrenzung auf fünf neue Issues pro Lauf.
- Probelauf mit den echten offiziellen Blogquellen: vier September-Beiträge
  bewertet, drei mit Code-Treffern zur Prüfung, einer ohne Treffer. Keine Issues
  erzeugt. Gemeinsame API-Beispiele können Fehlalarme auslösen.
- Workflow-YAML und Bash-Syntax, zwölf Tests, Ruff für das gesamte Projekt,
  Python-Syntax, 58 lokale Dokumentationslinks und Versionsstellen gültig.
  `uv lock --check --offline` bestanden; nur die lokale Paketversion geändert.

Berichte: `.work/blog-monitor/report/summary.md` und `report.json`, mit dem
abgerufenen Upstream-Commit im JSON-Bericht. GitHub-Issue-Antworten und Fehler
wurden simuliert. Kein GitHub-Actions-Lauf, keine echte Issue-Veröffentlichung
und keine zusätzliche HA-/Receiverprüfung für diese Workflow-Änderung.
Die folgende Integrationsprüfung beschreibt weiterhin ihren eigenen älteren Stand.

## Vorherige lokale Silber-Prüfungen

Zweite Etappe: zusätzliche Silber-Anforderungen auf `quality-scale`.

| Prüfung | Ergebnis |
| --- | --- |
| Integrations-Gesamtlauf unter HA 2026.9.1 / Python 3.14.7 | 242 bestanden; 423,49 Sekunden |
| Anschließend ergänzter Test ohne Receiver-MAC | 1 bestanden; 9,76 Sekunden |
| Gemeinsame Coverage beider Läufe | 99,68 % Anweisungen; 97,81 % Zweige; kombiniert 99,25 % |
| Silber-Coverage-Sperre | Alle 23 Integrationsmodule über 95 % kombiniert; Minimum 96,15 % |
| Konfigurationsfluss | Weiterhin 100 % Anweisungen und Zweige |
| JavaScript-Tests der Fernbedienungskarte | 8 bestanden |
| Ruff, Formatprüfung und Python-Syntax | bestanden |
| Lokales Hassfest gegen HA 2026.9.1 | 1 Integration, 0 ungültige Integrationen |
| Versionsstellen und Offline-Lockdateiprüfung | synchron; keine Abhängigkeiten geändert |

Der vollständige Integrationslauf bestand; anschließend wurde ein weiterer Test
für fehlende MAC-Metadaten ergänzt und separat ausgeführt. Der Produktionscode
der Integration blieb zwischen diesen beiden Läufen unverändert. Die Abdeckung
wurde mit `--cov-append` zusammengeführt. Dies sind **243 Integrationsprüfungen in
zwei Läufen**, kein neuer vollständiger Lauf nach Ergänzung des letzten Tests.
Der parallel ergänzte Blog-Monitor gehört nicht zum Prüfumfang dieses Abschnitts.

Die Aktion **Listen aktualisieren** wartet jetzt auf einen tatsächlich
abgeschlossenen Abruf und meldet Verbindungsfehler. Neu abgedeckt sind unter
anderem verlorene Antworten auf Abschaltbefehle ohne Wiederholung, Bild- und
Decoderfehler, Downloadgrenzen, Abbruchbereinigung, schnelle Senderwechsel,
ungültige Kataloge und die wiederholte beziehungsweise übersprungene Stunde bei
Zeitumstellungen. Transporte und Bildanbieter sind simuliert; der bestehende
FFmpeg-Test arbeitet mit einer künstlich erzeugten Aufnahmedatei.

Nachweise: `.work/quality-silver/full-tests.log`, `no-mac.log`,
`full-coverage.json` (Gesamtlauf), `coverage.json` (zusammengeführt), `.coverage`,
`hassfest.log` und `frontend.log`. Die zehn zusätzlichen Silber-Regeln sind
intern nachgewiesen. Der externe Bronze-Brands-Nachweis bleibt offen; deshalb
wird keine vollständige oder offizielle Silber-Einstufung behauptet.
Keine neue Hardware-, Oberflächen- oder GitHub-CI-Abnahme durchgeführt.

### Vorherige Bronze-Etappe von 1.0.1-dev.1

Erste Etappe der Qualitätsarbeiten auf dem Arbeitsbranch `quality-scale`:

| Prüfung | Ergebnis |
| --- | --- |
| Python-Tests unter Home Assistant 2026.9.1 / Python 3.14.7 | 185 bestanden; 309,43 Sekunden |
| Konfigurationsfluss | 124/124 Anweisungen und 36/36 Zweige abgedeckt: jeweils 100 % |
| Gesamtabdeckung | 92,90 % Anweisungen; 82,16 % Zweige; kombiniert 90,47 % |
| Coverage-Sperre | Vollständiger Bericht akzeptiert; fehlende Anweisungen, Zweige, Zweigmessung und Modulnachweise abgewiesen |
| Qualitätscheckliste | Alle 54 Regeln vorhanden; Schema von HA 2026.9.1 gültig |
| JavaScript-Tests der Fernbedienungskarte | 8 bestanden |
| Ruff-Codeprüfung, Formatprüfung und Python-Syntax | bestanden |
| Lokales Hassfest gegen HA 2026.9.1 | 1 Integration, 0 ungültige Integrationen |
| Dokumentationslinks und YAML-Beispiele | 182 lokale Verweise und zehn Beispiele gültig |
| Versionsstellen und Offline-Lockdateiprüfung | synchron; nur lokale Paketversion geändert |

Die Tests nutzen das echte HA-Framework mit simulierten Receiver-Antworten.
Keine neue Hardware-, Oberflächen- oder GitHub-CI-Abnahme. Die Konfigurations-
tests prüfen Fehlerkorrektur im selben Ablauf, Identität und doppelte Geräte.
Eine zusätzliche Laufzeitprüfung bestätigt die einmalige Meldung von Ausfall
und Wiederverbindung. Die kombinierte Abdeckung enthält erstmals Zweige und ist
nicht direkt mit den früheren Statement-Prozentwerten vergleichbar.

Nachweise liegen lokal unter `.work/quality-scale/`: `full-tests.log`,
`coverage.json`, `.coverage`, `hassfest.log` und `frontend.log`.
Die [Qualitätscheckliste](../custom_components/enigma2_connect/quality_scale.yaml)
ist eine interne Selbsteinschätzung. Der externe Brands-Nachweis bleibt für Bronze
offen; Silber bis Platin sind noch nicht vollständig erfüllt. Den nächsten Umfang
beschreibt die [Entwicklerdokumentation](ENTWICKLUNG.md#qualitätsstufen-und-nächste-schritte).

### Vorherige Prüfung von 1.0.0

Der vollständige Release-Kandidat `1.0.0` wurde geprüft:

| Prüfung | Ergebnis |
| --- | --- |
| Python-Tests unter Home Assistant 2026.9.1 / Python 3.14.7 | 148 bestanden; 278,48 Sekunden; 92 % Statement-Coverage |
| JavaScript-Tests der Fernbedienungskarte | 8 bestanden |
| Ruff-Codeprüfung, Formatprüfung und Python-Syntax | bestanden |
| Lokales Hassfest gegen HA 2026.9.1 | 1 Integration, 0 ungültige Integrationen |
| Dokumentationslinks und YAML-Beispiele | 168 lokale Verweise und zehn Beispiele gültig |
| Versionsstellen und Offline-Lockdateiprüfung | synchron; keine Abhängigkeiten geändert |
| Release- und Datenschutzprüfung | 84 Git-sichtbare Dateien; keine lokalen Testdaten oder privaten Werte enthalten |

Die Python-Tests verwenden das echte Home-Assistant-Testframework mit simulierten
Receiver-Antworten und Internetanbietern. Lokale Protokolle und Berichte liegen
unter `.work/` und werden nicht veröffentlicht.

### Vorherige Entwicklungsprüfungen

| Prüfung | Ergebnis |
| --- | --- |
| Python-Tests unter Home Assistant 2026.9.1 / Python 3.14.7 | Gesamtlauf: 147 bestanden, 1 fehlgeschlagen; 276,28 Sekunden |
| Gezielter Nachlauf des zunächst fehlgeschlagenen Tests | 1 bestanden; 1,53 Sekunden |
| Abdeckung im Gesamtlauf | 90 % Statement-Coverage |
| JavaScript-Tests der Fernbedienungskarte | 8 bestanden |
| Ruff-Codeprüfung und Formatprüfung | bestanden |
| Python-Syntax | bestanden |
| Lokales Hassfest gegen HA 2026.9.1 | 1 Integration, 0 ungültige Integrationen |

Der Gesamtlauf erfasste auch die parallel ergänzte Bild-Neugenerierung.
`test_regeneration_is_per_receiver_repeatable_and_survives_settings` schlug darin
fehl und bestand anschließend im gezielten Nachlauf des aktuellen Arbeitsstands.
Ein weiterer vollständiger Gesamtlauf wurde danach nicht ausgeführt.

Die Python-Tests verwenden das echte HA-Framework, simulieren aber Receiver-
Antworten und Internetanbieter. Der FFmpeg-Test erzeugt eine künstliche Aufnahme
mit Farbwechsel und gewinnt daraus echte Einzelbilder. Das ist keine Prüfung
einer Aufnahmedatei auf einem Receiver und keine Prüfung mit echten TMDB-/OMDb-
Schlüsseln. Die Kartentests ersetzen keinen visuellen Browser- oder Mobilgerätetest.

Die Dokumentation wurde mit Optionen, Übersetzungen, Aktionen, Medienbrowsern,
Bildvorbereitung und Fehlerverhalten im aktuellen Code abgeglichen. Lokale Links,
Sprungmarken, Sprachverweise, YAML-Beispiele, Versionsstellen und Lockdatei wurden
abschließend geprüft: 168 lokale Verweise und zehn YAML-Beispiele sind gültig. Der vollständige
alte Dokumentationsbestand mit 45 Dateien wurde per SHA-256 im lokalen Archiv
verifiziert. Aktive Branding-Quellen und Schriftlizenz wurden unverändert übernommen.

Lokale Protokolle: `.work/docs-audit/pytest.log`, `ruff.log`, `format.log` und
`verification.log` sowie `regeneration-recheck.log` im selben Ordner; Hassfest: `.work/docs-restructure/hassfest.log`.
Diese Arbeitsdateien werden nicht veröffentlicht.

## Vorhandene Hardware-Nachweise

Die früheren Berichte vom 13.09.2026 beziehen sich auf die lokale Ausgangsfassung
`0.1.0`, nicht auf den gesamten jetzigen Entwicklungsstand:

- **Octagon SF8008 4K Supreme, OpenWebif 2.4.0:** dokumentiert sind Live-TV/Radio,
  Aufnahmewiedergabe, Picons und Bildschirmfotos, Fernbedienung, Nachrichten,
  Timer/Kalender, Standby, GUI-Neustart, Neustart und Tiefschlaf. Die Karte wurde
  auf Desktop, Smartphone und Tablet sowie in hellen/dunklen Ansichten geprüft.
- **Vu+ Solo², OpenWebif 1.4.4:** dokumentiert sind getrennte Gerätezuordnung,
  Einrichtung ohne Zugangsdaten, Kataloge, Fernbedienung, Nachrichten und Timer.
  Wegen fehlenden DVB-Eingangssignals war dies keine zweite Abnahme von Bild,
  Ton, Empfangs-EPG oder echten Aufnahmen.

Die Originalberichte bleiben im lokalen Dokumentationsarchiv erhalten. Bei dieser
Dokumentationsüberarbeitung wurde keine neue Receiver- oder HA-Oberflächenabnahme
durchgeführt. Insbesondere Medienkachel, Aufnahmebilder, Hintergrundvorbereitung
und optionale Senderordner benötigen für eine aktuelle Hardwarefreigabe passende
Live-Prüfungen in beiden Oberflächensprachen.

## Veröffentlichung und verbleibende Grenzen

Die Workflows für Tests, Hassfest und HACS sind vorhanden. Ein lokaler Lauf
belegt keine erfolgreiche GitHub-CI und keine HACS-Freigabe für einen Release-
Commit. Vor einer Veröffentlichung gelten die Prüfungen und ausdrücklichen
Freigaben aus [RELEASING.md](../RELEASING.md).

Browser-/Cast-Streaming, Wake-on-LAN, neue
wiederkehrende Timer und Antworten auf Bildschirmnachrichten sind nicht
implementiert. Weitere Sonderfälle stehen in der Entwicklerdokumentation.
