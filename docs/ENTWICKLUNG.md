[Deutsch](ENTWICKLUNG.md) | [English](DEVELOPMENT.en.md)

# Entwicklerdokumentation

Diese Anleitung bündelt die Informationen für Änderungen an Enigma2 Connect.
Für Installation und Bedienung gibt es das [Benutzerhandbuch](BENUTZERHANDBUCH.md);
die [README](../README.md) bleibt der kurze Einstieg für Anwender.

## Inhaltsverzeichnis

- [README-Badges](#readme-badges)
- [Projekt und Voraussetzungen](#projekt-und-voraussetzungen)
- [Entwicklungsumgebung und Prüfungen](#entwicklungsumgebung-und-prüfungen)
- [Lesende Receiver-Abnahme](#lesende-receiver-abnahme)
- [Home-Assistant-Entwicklerblog überwachen](#home-assistant-entwicklerblog-überwachen)
- [Cloudflare-Probelauf](#cloudflare-probelauf)
- [Qualitätsstufen und nächste Schritte](#qualitätsstufen-und-nächste-schritte)
- [Aufbau und Datenfluss](#aufbau-und-datenfluss)
- [Externe Wiedergabe](#externe-wiedergabe)
- [Streaming-Diagnose und Qualität](#streaming-diagnose-und-qualität)
- [Verhaltensregeln für Implementierungen](#verhaltensregeln-für-implementierungen)
- [Dokumentation und Änderungen](#dokumentation-und-änderungen)
- [Identität und Datenverarbeitung](#identität-und-datenverarbeitung)
- [Validierung von Aktionen](#validierung-von-aktionen)
- [Vorgemerkte Ideen](#vorgemerkte-ideen)
- [Dateibestand und lokale Archive](#dateibestand-und-lokale-archive)

## README-Badges

Die gemeinsamen Badges über beiden Sprachfassungen verwenden `flat-square`.
Release zeigt das letzte veröffentlichte GitHub-Release; Tests und Validierung
beziehen sich auf `main`. Validierung umfasst Hassfest und HACS. Die statischen
Mindestversionen für Home Assistant, OpenWebif und Python bei Änderungen der
Voraussetzungen mitpflegen. HACS „Custom“ bezeichnet den Installationsweg,
keine Aufnahme in den Standardkatalog.

Der Test-Workflow liest nach allen bisherigen Prüfungen die kombinierte
Anweisungs-/Zweigabdeckung aus `coverage.json`. Ein separater Job veröffentlicht
den Wert nur nach erfolgreichen `main`-Push-Tests im Originalrepository nach
`badges/coverage.json` (Datei `coverage.json` auf Branch `badges`). Nur dieser Job
erhält `contents: write`; er verwendet den eingebauten `GITHUB_TOKEN`, führt
keinen Repository-Code aus und benötigt weder externe Coverage-Dienste noch
zusätzliche Secrets. Parallelveröffentlichungen werden serialisiert, überholte
`main`-Läufe übersprungen und Branch-Aktualisierungen ohne Force ausgeführt.
Der erste Lauf legt den Datenbranch mit eigener Historie an; weitere Updates
erhalten andere Dateien auf diesem Branch. Repository-Regeln müssen diesen
Bot-Schreibzugriff erlauben. Pushes auf `badges` starten keine Tests/Validierung.

Shields.io liest den Messwert über einen öffentlichen JSON-Endpunkt. Der Badge
verlinkt auf die Daten einschließlich Quellcommit, Testlauf und Messart. Er zeigt
die letzte veröffentlichte erfolgreiche Messung; bei fehlgeschlagenen Tests bleibt
dieser Wert stehen. Der separate Tests-Badge zeigt den aktuellen Teststatus.
Vor dem ersten erfolgreichen `main`-Lauf mit diesem Workflow ist der
Coverage-Endpunkt noch nicht verfügbar; Caches können die Anzeige verzögern.
Der Gesamtwert ersetzt weder die 100-%-Config-Flow-Prüfung noch die Grenze von
über 95 % je Integrationsmodul oder echte Receiver-/Home-Assistant-Prüfungen.

## Projekt und Voraussetzungen

Enigma2 Connect ist eine eigenständige Home-Assistant-Custom-Integration für
Enigma2-Receiver mit OpenWebif-JSON-API. Die Domain und das Komponentenpaket heißen
`enigma2_connect`, Repository und Python-Projekt `enigma2-connect`.
Ziel sind Home Assistant **ab 2026.9** und Python **ab 3.14.2**.
Für die Entwicklung wird Linux beziehungsweise WSL verwendet; Node.js führt die
Tests der optionalen Dashboardkarte aus.

Das Projekt entstand aus der Analyse von `homeassistant-enigma-player` und
`HAVUOpenWebif`. Die Integrationslogik wurde für eine gemeinsame Architektur neu
geschrieben. Der Produktionscode steht unter [Apache-2.0](../LICENSE); beachte
[NOTICE](../NOTICE) und die [Lizenzprüfung](LIZENZEN.md). Lokale Recherchedateien
und Testwerkzeuge unter `.work/` behalten ihre jeweiligen Lizenzen und werden
nicht veröffentlicht. Die Software wurde mit Unterstützung generativer KI entwickelt.

## Entwicklungsumgebung und Prüfungen

Lokal die zur Änderung passenden, gezielten Prüfungen auswählen. Die folgende
Befehlsliste ist eine Referenz für den vollständigen Prüfumfang. Aktuelle erfolgreiche
CI-Ergebnisse müssen nicht vollständig lokal wiederholt werden. Vor dem Merge
gelten die [Qualitätsvorgaben der Release-Anleitung](../RELEASING.md#prüfungen);
betroffene Anforderungen außerhalb der CI sind zusätzlich zu prüfen.

Im Projektverzeichnis unter Linux/WSL mit Python ab 3.14.2:

FFmpeg muss für den Test zur tatsächlichen Aufnahmebild-Extraktion im Suchpfad
liegen (unter Debian/Ubuntu: `sudo apt-get install ffmpeg`). Ohne FFmpeg wird
dieser Test lokal übersprungen und die Silber-Abdeckungsprüfung kann scheitern.
Die CI installiert FFmpeg ausdrücklich und prüft den Aufruf vor dem Testlauf.

Die GitHub-Workflows verwenden `actions/checkout@v7`, `astral-sh/setup-uv@v10.1.0`
und `actions/upload-artifact@v7` mit Node.js 24 als Action-Laufzeit. Die
gehosteten `ubuntu-latest`-Runner unterstützen diese Versionen. Dies ändert
nicht die Python-Anforderungen der Integration. Bestehende Warnungen in alten
Workflow-Läufen bleiben Bestandteil ihrer historischen Protokolle.
Für setup-uv wird der vollständige Release-Tag verwendet; ein Kurz-Tag `v10`
ist im Upstream-Repository nicht vorhanden.

```sh
uv sync --locked --group dev
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
uv run --locked pytest --cov=custom_components.enigma2_connect --cov-branch --cov-report=term-missing --cov-report=json:coverage.json
uv run --locked python scripts/check_config_flow_coverage.py coverage.json --silver
uv run --locked python -m compileall -q custom_components tests scripts
node --test tests/frontend.test.cjs
git diff --check
```

`pyproject.toml` enthält die direkten Entwicklungsabhängigkeiten, `uv.lock` fixiert
deren Auflösung. Nach einer Versionsänderung `uv lock --offline` ausführen und
prüfen, dass nur die erwarteten Projektmetadaten geändert wurden. Keine
Abhängigkeiten nebenbei aktualisieren. Eine frische Umgebung benötigt beim
ersten Synchronisieren Zugriff auf die Paketquellen.

**Befristete Sicherheitsausnahme:** Home Assistant 2026.9.1 und 2026.9.2 binden
`cryptography==48.0.1` und `pyOpenSSL==26.2.0`. Wegen
[CVE-2026-69247](https://github.com/pyca/cryptography/security/advisories/GHSA-g6cj-pr64-35w5)
setzt `[tool.uv].override-dependencies` in der Entwicklungsumgebung stattdessen
`cryptography==50.0.1` und `pyopenssl==26.4.0`. Die zweite Anhebung ist erforderlich,
weil pyOpenSSL 26.2.0 nur cryptography unter 49 erlaubt; 26.4.0 unterstützt 50.
Dies weicht bewusst von Home Assistants Paketmetadaten ab und wird mit unseren
Integrationstests geprüft, nicht als allgemeine HA-Freigabe behauptet. Bei einem
späteren Update des HA-Teststacks die Ausnahme entfernen, sobald dessen Vorgaben
eine reparierte cryptography-Version ab 50 zulassen, und Lockdatei/Tests erneut prüfen.
Die Custom-Integration installiert diese Pakete nicht selbst; ihre Manifest-
Anforderungen bleiben leer. Für eine produktive HA-Installation gelten deren
eigene Paketversionen, die durch diese Repository-Änderung nicht aktualisiert werden.

Die Python-Tests verwenden das echte Home-Assistant-Framework; Receiver-Antworten
und Transporte sind simuliert. Sie prüfen unter anderem Config Flow,
Gerätezuordnung, Plattformen, Fehlerfälle, Kalender, Aufnahmen, Medienquelle und
Übersetzungen. Die JavaScript-Tests prüfen Registrierung, Editor, Tastendrücke,
Wiederholungen und Sprachwechsel der Karte. Sie ersetzen keine visuelle Prüfung.

Die Workflows [tests.yml](../.github/workflows/tests.yml) und
[validate.yml](../.github/workflows/validate.yml) führen Tests, Ruff, Hassfest und
HACS-Prüfungen aus. Lokale Ergebnisse sind kein Nachweis erfolgreicher CI für
einen späteren Commit. Prüfumfang, getestete Versionen und tatsächliche
Receiver-/Oberflächenprüfungen stehen in [VALIDIERUNG.md](VALIDIERUNG.md).
Historische Ergebnisse gelten nur für den dort dokumentierten Stand.

Die vorhandene lokale WSL-Umgebung kann über `.work/run_tests.sh` verwendet
werden; sie ist kein Bestandteil einer frischen Installation. Auf dem
Windows-Mount vermeidet `--capture=sys` bekannte Probleme der pytest-Erfassung.
Weitere lokale Pfade und Berichte stehen im Validierungsdokument.

## Lesende Receiver-Abnahme

Nach Installation der Entwicklungsabhängigkeiten startet
[receiver_acceptance.py](../scripts/receiver_acceptance.py) den aktuellen Code
in einem temporären Home Assistant und liest den ausdrücklich angegebenen Receiver:

```sh
uv run --locked python scripts/receiver_acceptance.py --host RECEIVER --username root
```

Das Passwort wird verdeckt abgefragt. Für automatisierte Aufrufe kann
`--password-env NAME` eine vorhandene Umgebungsvariable lesen. Ohne Anmeldung
`--username` weglassen. `--https` und `--port PORT` wählen Protokoll und Port;
HTTPS prüft das Zertifikat. Der Bericht liegt standardmäßig unter
`.work/receiver-acceptance.json`; `--output PFAD` hält Receiver-Berichte getrennt.

Geprüft werden Einrichtung, alle neun Plattformen, die drei standardmäßig
deaktivierten Signaldiagnosen, verfügbare Entitätszustände, Aktualisierung,
Duplikatschutz und Entladen. Optionale Ausfälle und nicht verfügbare Entitäten
werden als Anzahl beziehungsweise Endpunktnamen ausgewiesen, damit Standby und
unterschiedliche Gerätefunktionen erkennbar bleiben. `passed: true` bestätigt
den technischen Ablauf; diese Angaben trotzdem bei der Geräteabnahme bewerten.

Der Transport lässt ausschließlich die benötigten lesenden API-Aufrufe zu.
Hintergrund-Bilderzeugung wird zurückgestellt. Zugangsdaten und HA-Speicher bleiben
im Arbeitsspeicher; rohe pytest-Protokolle werden nicht ausgegeben. Der JSON-Bericht
enthält Prüfschritt, Exit-Status, Versionen, Quelltext-Hash und technische Summen.
Exit-Status 0 setzt einen vollständig abgeschlossenen Ablauf voraus; Fehler oder
ein übersprungener Ablauf sind kein erfolgreicher Nachweis.

Das ist ein echtes HA-Backend mit Test-Fixtures, kein bereits installiertes
HA-System. UI, Bild/Ton, Bonjour und physischer DHCP-Wechsel gehören weiterhin
zur separaten Abnahme unten. Normale pytest-/CI-Läufe kontaktieren keine Receiver;
direkter Aufruf der Hardware-Testdatei ohne Prüfkonfiguration wird übersprungen.

## Home-Assistant-Entwicklerblog überwachen

Der [Workflow](../.github/workflows/ha-developer-blog.yml) prüft montags um
**07:23 UTC** neue oder geänderte Beiträge im offiziellen
[Blog-Repository](https://github.com/home-assistant/developers.home-assistant/tree/master/blog).
Das entspricht 09:23 Uhr MESZ bzw. 08:23 Uhr MEZ. Pro Lauf werden höchstens
**fünf Beiträge einzeln und nacheinander mit Junie** analysiert. Weitere neue
Beiträge bleiben bis zum nächsten Wochenlauf zurückgestellt. Ohne fällige
Beiträge wird kein KI-Auftrag gestartet.

### Inhalt und Bericht

Jeder Beitrag wird getrennt auf **notwendige Anpassungen** und **sinnvolle
Ergänzungen oder Verbesserungen** geprüft, etwa Bedienbarkeit, neue Fähigkeiten,
Zuverlässigkeit und Wartbarkeit. Ein verpflichtender Umbau ist kein zusätzlicher
Verbesserungsvorschlag. Junie soll auf Deutsch begründen, konkrete nächste
Schritte nennen und sämtliche angekündigten Verfügbarkeits-, Deprecation- und
Entfernungsfristen übernehmen. Neue Möglichkeiten werden auch dann geprüft,
wenn die betreffende API noch nicht im Code vorkommt.

Bewertungen mit konkreter Auswirkung oder empfohlenem Zusatznutzen müssen
bestehende Quellzeilen als Ansatzpunkt belegen. Ein eigener, vertrauenswürdiger
Schritt prüft Beitrags-ID, Ergebnisstruktur, Dateipfade, Zeilennummern und wörtliche
Belege gegen den vor der Analyse gesicherten Quellstand. Eine KI-Einschätzung
ersetzt keine ausgeführten Kompatibilitätstests und kann inhaltlich falsch sein.

Ein GitHub-Issue enthält nur Beiträge mit notwendigen Anpassungen, empfohlenen
Ergänzungen oder noch unklarem Prüfbedarf. Wenn alle Bewertungen zugleich
`no-impact` und `none` ergeben, wird kein Issue erstellt. Auch in gemischten
Läufen bleiben solche unauffälligen Beiträge aus dem Issue heraus.

Erfolgreich geprüfte Inhalts-IDs werden mit Prüfdatum im Statusbranch gespeichert,
auch ohne Issue. Inhaltsbasierte Marker in bestehenden und geschlossenen Issues
zählen weiterhin; Marker aus der Gemini-Zeit bleiben kompatibel. Geänderte
Blogtexte werden neu geprüft, Quelländerungen allein lösen keine erneute Prüfung
aus. Strukturierte Ergebnisse und Kosten bleiben zur technischen Nachvollziehbarkeit
30 Tage als Artefakt `ha-developer-blog-report` erhalten.

### Wiederholung und Berechtigungen

Der [Junie-Monitor](../scripts/ha_blog_junie_monitor.py) verwendet die bewährte
[Status- und Wiederholungslogik](../scripts/ha_blog_scheduler.py). Bei einem ersten
Fehler wird ausschließlich der betroffene Beitrag für den Folgetag vorgemerkt;
der Lauf bleibt erfolgreich. An den übrigen Wochentagen um 07:23 UTC werden nur
fällige gespeicherte Beiträge erneut versucht. Erst der zweite Fehler desselben
Beitrags führt zu einem fehlgeschlagenen Lauf. Verpasste Wiederholungen werden
nachgeholt. Danach sind weitere Versuche nur ausdrücklich manuell möglich.

Der Branch `ha-blog-monitor-state` enthält unter `.github/ha-blog-state.json`
Beitragsinhalt, ursprünglichen Blog-Commit, Versuchsanzahl, Fälligkeit und einen
bereinigten Fehlerhinweis sowie unter `reviewed` die erfolgreich geprüften
Inhalts-IDs mit Prüfdatum. Vorhandene Statusdateien ohne `reviewed` bleiben gültig. Versuche werden vor dem KI-Auftrag reserviert, damit
abgebrochene Läufe nicht unbemerkt mehrfach Credits verbrauchen. Erfolgreiche
Teilberichte bleiben erhalten. Unsichere Zustandsspeicherung ist ein
Infrastrukturfehler und wird unmittelbar gemeldet.

Planung, Analyse und Veröffentlichung laufen in getrennten Jobs. Nur Planung
und Veröffentlichung besitzen Schreibrechte für den Statusbranch bzw. Issues.
Junie bekommt **keinen schreibenden GitHub-Token**. Die Veröffentlichung lädt den
ursprünglichen Plan unabhängig vom Agenten, validiert dessen Antworten nochmals
und verweigert das Überschreiben zwischenzeitlich geänderter Zustände. Pushes
und Pull Requests führen nur Offline-Tests aus. Veröffentlichungen sind auf das
Originalrepository und den Standardbranch beschränkt; manuelle Probeläufe sind
auch auf Arbeitsbranches möglich. Parallele Workflow-Läufe werden serialisiert.

### Zugang, Kosten und Bedienung

1. Einen CLI-Token im [Junie-Konto](https://junie.jetbrains.com/tokens) erstellen
   und als Repository-Secret **JUNIE_API_KEY** speichern. Den Token nicht in
   Code, Issues oder Chats eintragen. Vorhandenes JetBrains-Guthaben bereithalten.
2. Unter **Actions → Home Assistant developer blog → Run workflow** für einen
   Probelauf **Run Junie without publishing issues or changing retry state**
   aktiviert lassen. Probeläufe benötigen Credits, ändern aber weder Issues
   noch Versuchszähler. Für reguläre manuelle Veröffentlichung den Schalter
   deaktivieren und den Standardbranch wählen.
3. **Retry exhausted entries only** versucht ausschließlich bereits endgültig
   fehlgeschlagene Beiträge erneut. Dies ist auch als Probelauf möglich.
4. Im Bericht die Bewertung und die **von Junie gemeldeten Modellkosten** prüfen.
   Die Summe stammt aus `llmUsage[].cost`, die Modellnamen aus `llmUsage[].model`.
   Fehlende Verbrauchsdaten werden als unbekannt ausgewiesen. Diese USD-Werte
   sind keine bestätigte Abbuchung der Credits im JetBrains-Konto.

Der produktive Ablauf nutzt direkt **Junie CLI 3110.6**, dieselbe Version wie der
geprüfte offizielle Action-Probelauf. Dadurch lassen sich einzelne Aufträge,
Ergebnisartefakte und Fehlerbehandlung unabhängig steuern. Das Standardmodell
wird von JetBrains bestimmt und kann sich ändern; im ersten Test war es Gemini
3.7 Flash mit kleineren Hilfsmodellen. Ein Agentenauftrag kann mehrere
Modellaufrufe enthalten. Jeder Beitrag hat ein Prozesslimit von fünf Minuten;
das ist **keine feste Credit-Obergrenze**. Es gibt keine unmittelbare Wiederholung,
keinen automatischen Wechsel zu Google/Cloudflare und keinen Guthabenkauf.

An Junie gehen die öffentlichen Blogtexte und dieselbe feste Quellauswahl:
Integrations-Pythondateien, Manifest, Übersetzungen, Dienste, Qualitätscheckliste,
Frontend-Karte und Projektmetadaten. Die Analyse erfolgt auf einem GitHub-Runner
mit dem öffentlichen Repository. Plan- und Ergebnisartefakte werden sieben Tage
aufbewahrt; rohe Junie-Sitzungsprotokolle werden im produktiven Ablauf nicht
hochgeladen. Das bestehende heuristische Skript bleibt eine separate lokale
Hilfe; es filtert keine Beiträge vor der KI aus.

Lokale Offline-Prüfung: `python -m unittest discover -s scripts/tests -v`.
Google- und Cloudflare-Zugangsdaten werden für den produktiven Monitor nicht mehr
benötigt. Historische Vergleichstests stehen in der [Prüfübersicht](VALIDIERUNG.md).

## Cloudflare-Probelauf

Mit `cloudflare_individual=true` wird jeder gespeicherte Beitrag getrennt mit
derselben vollständigen Codeauswahl analysiert. `cloudflare_post` begrenzt den
Test auf einen exakten gespeicherten Dateinamen. Höchstens fünf Anfragen laufen
seriell; bei Fehlern stoppt der Test, bereits erfolgreiche Ergebnisse und der
bisherige Verbrauch bleiben im Artefakt. Die getrennten Aufrufe vervielfachen
den Eingabeverbrauch; das tägliche Free-Tier-Limit gilt weiterhin.

**Teststand 16.09.2026:** Gestern erfolgreiche API-Aufrufe, heute HTTP 429/4006
trotz Dashboard-Anzeige 0/10.000. Die Batchanalyse vertauschte Begründungen; die
einzeln geprüfte Modbus-Bewertung ließ eine Frist aus. Weitere Einzeltests wurden
wegen der API-Sperre gestoppt. Noch nicht für den automatischen Betrieb freigegeben. Ergebnisse: [Prüfübersicht](VALIDIERUNG.md).

Der manuelle Workflow-Eingang `cloudflare_test=true` testet gespeicherte Beiträge
mit `@cf/openai/gpt-oss-120b`. Voraussetzung sind das Secret `CLOUDFLARE_API_TOKEN`
(Workers AI Read/Edit für genau ein Konto) und die Actions-Variable
`CLOUDFLARE_ACCOUNT_ID`. Den Workers-Free-Tarif ohne kostenpflichtiges Upgrade verwenden.
Der Test liest den Statusbranch, sendet dieselbe freigegebene Codeauswahl und
prüft Antworten mit der bestehenden Belegvalidierung. Er schreibt ausschließlich
das Artefakt `ha-blog-cloudflare-test`, keine Issues und keinen Wiederholungsstatus.
Im Batchmodus gibt es eine Anfrage, im Einzelmodus eine je Beitrag;
kein automatischer Anbieterwechsel.
`cloudflare_smoke=true` beschränkt den Test auf eine kleine Verbindungsprüfung.
Das Artefakt enthält auch die Anbieterantwort für eine erneute Offline-Auswertung;
Request-Header und Token werden nicht gespeichert. Der geplante
Junie-Monitor ist davon unabhängig; Cloudflare bleibt ein optionaler Vergleichstest.


## Qualitätsstufen und nächste Schritte

Enigma2 Connect bleibt eine **Custom-Integration ohne offizielle Qualitätsstufe**.
Die [HA-Qualitätsskala](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
dient als Entwicklungsmaßstab. Die vollständige
[Regelcheckliste](../custom_components/enigma2_connect/quality_scale.yaml) führt
Implementierung und offene Nachweise getrennt auf. `done` ist eine interne
Bewertung; eine offizielle Stufe setzt die Prüfung durch Home Assistant voraus.
Ausnahmen nur verwenden, wenn die jeweilige Regel sie erlaubt und die Begründung
belegt ist. Ein nicht untersuchter Punkt bleibt `todo`.

Die erste Etappe ergänzt Dialoghilfen und Tests für Einrichtung, Neuanmeldung,
Neukonfiguration und Optionen. Tests prüfen insbesondere Fehlerkorrektur im selben
Dialog, Duplikate nach Host/MAC, falsche Geräte und Receiver ohne MAC-Identität.
Zusätzliche Laufzeittests prüfen die Aktionsregistrierung ohne Eintrag und die
einmalige Protokollierung von Ausfall und Wiederverbindung. Die CI misst jetzt
Anweisungs- **und Zweigabdeckung** und verlangt für `config_flow.py` jeweils 100 %.
Diese kombinierte Abdeckung darf nicht mit früherer reiner Statement-Coverage
verglichen werden. Aktuelle Ergebnisse stehen in [VALIDIERUNG.md](VALIDIERUNG.md).

Die zweite Etappe erweitert die reguläre Suite um Transport-, Bedienungs-,
Kalender-, Bildanbieter- und Snapshot-Fehlerfälle. Bisher nur lokal vorhandene
Tests zu schnellen Senderwechseln und abgebrochenen Screenshot-Abrufen laufen
jetzt ebenfalls in CI. **Listen aktualisieren** wartet auf einen unmittelbaren
Abruf statt eines eventuell nur vorgemerkten Updates und meldet dessen Fehler.
Die CI verlangt zusätzlich **über 95 % kombinierte Anweisungs-/Zweigabdeckung in
jedem der 23 Integrationsmodule**; ein fehlendes Modul oder genau 95 % führt zum
Fehler. Konfigurationsflüsse bleiben bei 100 % beider Messgrößen.

Die dritte Etappe ergänzt Erkennung, sichere DHCP-Adressübernahme, robuste
Diagnosen, Gerätelebenszyklus-Prüfungen, übersetzte Reparaturhinweise und Icons.
Die 23 Produktionsmodule verwenden vollständige Funktionssignaturen und den
typisierten `EnigmaConfigEntry`. `uv run --locked mypy` erzwingt `strict = true`;
keine Module sind ausgenommen und fehlende Importtypen werden nicht pauschal
ignoriert. `follow_imports = "silent"` unterdrückt Meldungen aus fremden Paketen,
behält deren Typinformationen aber bei. `JsonObject` enthält flexible, von
OpenWebif-Version und Image abhängige Metadaten; feste Zustände und Sender sind
Dataclasses. Überladungen unterscheiden Bildbytes, JSON-Objekte und optionale
Listen. Das mitgelieferte Paket trägt `py.typed`.

Der Netzwerkclient verwendet eine von HA übergebene `aiohttp`-Session. Die
Aufnahmebild-Verwaltung führt Dateioperationen, FFmpeg-Pfadsuche und Pillow-Arbeit
über `async_add_executor_job` aus. FFmpeg läuft als asynchroner Unterprozess;
Downloadgrenzen, Zeitlimits, Prozessende und Relay-Bereinigung sind getestet.
Die Konvertierung kleiner, bereits begrenzter JSON-Antworten bleibt lokale
Speicherarbeit; keine synchrone Netz-/Dateiabfrage findet dort statt.

**Korrektur der früheren Brands-Einschätzung:** Seit HA 2026.3 sind lokale
`brand/`-Dateien für Custom-Integrationen offiziell vorgesehen. Die acht
mitgelieferten PNGs erfüllen diesen Weg; ein separater Brands-PR ist dafür nicht
erforderlich. Quellen: [HA-Ankündigung][quality-local-brands] und
[Brands-Repository][quality-brand-requirements]. Das ist eine interne Bewertung
der aktuellen Custom-Integration, keine Anerkennung durch ein Core-Review.

| Stufe | Lokaler Stand und verbleibender Nachweis |
| --- | --- |
| Bronze | Alle 20 Kriterien intern umgesetzt, einschließlich lokaler Brands. Dialoge müssen weiterhin 100 % Anweisungs- und Zweigabdeckung erreichen. |
| Silber | Alle 10 zusätzlichen Kriterien intern umgesetzt; jede der 23 Python-Dateien muss über 95 % kombinierte Abdeckung behalten. |
| Gold | Alle 21 zusätzlichen Kriterien intern umgesetzt. Ein echter DHCP-Adresswechsel ist mit gezielt ausgelöstem HA-Verarbeitungsschritt geprüft; echte Bonjour-Ankündigungen und der automatische DHCP-Empfang in laufendem HA bleiben offen. |
| Platin | Alle drei zusätzlichen Kriterien intern umgesetzt: asynchroner Client, injizierte Session und strikte Typprüfung in CI. Die CI-Nachweise gelten für die im Prüfbericht genannten Commits; für Veröffentlichungen wird der endgültige Commit erneut geprüft. |

### Erkennung und Geräte-Lebenszyklus

OpenWebif registriert HTTP-/HTTPS-Dienste über Bonjour beziehungsweise Avahi;
siehe [Upstream-Implementierung][quality-openwebif]. Unser Manifest begrenzt neue
Funde auf Bonjour-Namen `openwebif*` unter `_http._tcp.local.` und
`_https._tcp.local.`. Avahi-Ankündigungen ohne diesen Namen sind kein Beleg für
OpenWebif und lösen keine allgemeine Webserver-Erkennung aus. Einrichtung bleibt
manuell möglich. Für bestehende Geräte beobachtet DHCP ausschließlich registrierte
MAC-Adressen. Erst eine erfolgreiche `about`-Abfrage mit der gespeicherten
Identität erlaubt die Übernahme einer IP. Fehlgeschlagene Anmeldung, fehlende MAC
oder abweichendes Gerät ändern nichts; Port, TLS und Zugangsdaten bleiben erhalten.
Die Konfigurationsflüsse sind bestätigt, echte Netzankündigungen noch nicht.

Jeder Eintrag gehört genau einem Receiver; Sender und Aufnahmen sind keine
weiteren Geräte. Ein zusätzlich eingerichteter Receiver erhält seine Entitäten
ohne Neustart. Ein unerreichbarer Receiver bleibt registriert. Dauerhaft entfernt
wird er durch Löschen seines Integrationseintrags: HA entfernt die zugehörigen
Geräte-/Entitätszuordnungen, die Integration ihren Reparaturhinweis. Andere Receiver
bleiben erhalten. Dies ist der geprüfte Löschweg bei dieser Ein-Gerät-Architektur;
ein Hub-Abgleich oder automatisches Löschen nach Ausfall wäre hier falsch.

Verbindung und Listenaktualisierung sind Diagnosen; ebenso Signalqualität, SNR und
BER, die bei neuen Entitäten zunächst deaktiviert sind. Vorhandene Nutzerentscheidungen
werden nicht überschrieben. Die Verbindung verwendet `CONNECTIVITY`. Prozentqualität,
Signal-Rausch-Verhältnis und unnormierte BER besitzen keine fachlich passende
zusätzliche Geräteklasse: SNR ist keine RSSI-Leistung, BER keine erfundene Prozentgröße.
Standby, Aufnahme und Streaming nutzen ihre eigenen Zustände und Icons. Symbole
mit Geräteklassen-Vorgabe werden nicht überschrieben. Alle nutzersichtbaren
Aktionsfehler besitzen Übersetzungsschlüssel; interne Parserfehler werden an der
HA-Grenze übersetzt, nicht ungefiltert angezeigt.

Ein fehlendes FFmpeg bei gewählter Snapshot-Quelle erzeugt einen eigenen Hinweis
je Receiver. Installation beziehungsweise Pfadkorrektur und Neuladen oder Abwahl
der Quelle beheben ihn. Ein gewöhnlicher Receiver-Ausfall erzeugt keinen zusätzlichen
Reparaturhinweis. Anmeldung läuft über den vorhandenen HA-Reauth-Mechanismus.

[quality-local-brands]: https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/
[quality-brand-requirements]: https://github.com/home-assistant/brands/blob/master/README.md
[quality-openwebif]: https://github.com/E2OpenPlugins/e2openplugin-OpenWebif/blob/master/plugin/httpserver.py

Jede Stufe setzt alle vorherigen voraus. Für jede abgeschlossene Etappe Version,
Lockdatei, beide Changelogs und Dokumentation gemäß Projektvorgaben aktualisieren;
Tests, Ruff, Syntax und Hassfest erneut prüfen. Empfang, Bild und Ton sowie neue
Erkennungsabläufe zusätzlich an realen Receivern prüfen und den genauen Umfang
festhalten. Automatisierte Tests verwenden simulierte Receiver-Antworten.

Eine Core-Aufnahme ist ein gesondertes Vorhaben: API-Bibliotheksarchitektur,
Abhängigkeiten, HA-Brands, offizielle Benutzerdokumentation und Core-Review vorher
klären. Für die Entwicklung wird im Manifest keine offizielle Stufe behauptet.
Merge und Veröffentlichung bleiben an die Freigaben aus
[RELEASING.md](../RELEASING.md) gebunden.

Vor der Hardware-/Veröffentlichungsfreigabe bleibt folgende Abnahme offen:

- [x] Aktuellen Integrationscode im isolierten HA-Testbackend mit echtem Octagon
  geprüft; Versionen und Umfang in der [Prüfübersicht](VALIDIERUNG.md#aktuelle-lesende-octagon-abnahme).
  Einrichtung, neun Plattformen, Aktualisierung, Duplikatschutz und Entladen bestanden;
  keine Sichtprüfung einer installierten HA-Oberfläche.
- [x] HTTPS-Leseablauf am Octagon sowie Ablehnung seines nicht vertrauenswürdigen
  Zertifikats geprüft; die Ausnahme blieb auf den Test begrenzt.
- [x] Bild und Audio eines kurzen Live-Stream-Ausschnitts technisch dekodiert,
  ohne Senderwechsel oder gespeicherte Inhalte; subjektive Wiedergabeprüfung offen.
- [ ] Einen echten Bonjour-Fund einschließlich Name, HTTP/HTTPS und Port prüfen;
  Einrichtung bestätigen, wiederholte Ankündigungen und manuelle Einrichtung prüfen.
- [x] Echten DHCP-Adresswechsel mit gezielt ausgelöstem HA-Verarbeitungsschritt
  geprüft: nach GUI-Neustart gleiche MAC, erhaltene Kennungen, Anmeldung und TLS.
  Fehlende MAC sperrte vorher korrekt die Übernahme; falsche Identität und
  Adresskonflikte sind zusätzlich simuliert geprüft; siehe [Prüfbericht](VALIDIERUNG.md#physischer-dhcp-adresswechsel-fehlende-identitätsdaten).
- [ ] Automatischen Empfang und Weiterverarbeitung einer echten DHCP-Meldung
  in einer durchgehend laufenden HA-Installation nachweisen.
- [x] Neue Symbole, deaktivierte Signaldiagnosen, Optionsdialoge und FFmpeg-Reparatur
  in der echten Testoberfläche geprüft; Texte und Abhilfe auf Deutsch und Englisch.
- [x] Aufnahmebild aus einer vorhandenen Datei erzeugt und dekodiert; Lautstärke,
  Stummschaltung, Meldungsaufruf und eigener temporärer Timer geprüft.
  Ursprünglicher Zustand und vorhandene Timer/Aufnahmen nachweislich erhalten.
- [x] GitHub-CI für `ffdf007` bestanden: Tests einschließlich FFmpeg und
  Coverage-Sperre, Frontend, Hassfest und HACS; Nachweise in der
  [Prüfübersicht](VALIDIERUNG.md#github-ci-und-ffmpeg-voraussetzung).
  PR-/Merge- und Release-Freigaben bleiben gemäß Release-Anleitung gesondert.

## Aufbau und Datenfluss

| Bereich | Aufgabe |
| --- | --- |
| `custom_components/enigma2_connect/__init__.py` | Config Entry aufbauen, Plattformen laden und entladen |
| `api.py` | OpenWebif-Zugriff, Authentifizierung, TLS, Antwortprüfung und serialisierte Befehle |
| `models.py` | Datenmodelle, Normalisierung, Geräteidentität und Timerberechnung |
| `coordinator.py` | Gemeinsame Zustandsabfragen, Kataloge, Timer und Aufnahmen |
| `config_flow.py` | Einrichtung, erneute Anmeldung, Neukonfiguration und Optionen |
| `entity.py` und Plattformmodule | Gemeinsame Gerätezuordnung und Home-Assistant-Entitäten |
| `services.py` / `services.yaml` | Validierung und Beschreibung der Geräteaktionen |
| `recordings.py` / `media_source.py` | Aufnahmeordner, Titel und gemeinsame Medienkachel |
| `channel_media.py` | Optionale Senderordner, Receiver-Zuordnung und authentifizierte Picons |
| `media_stream.py` / `stream_codec.py` / `stream_receiver.py` | Externe Wiedergabe, Codec-Prüfung und begrenzte Receiver-Stream-Weitergabe |
| `recording_images.py` / `recording_snapshot.py` | Vorschaubilder, Bildanbieter, privater Cache und begrenzte FFmpeg-Bildgewinnung |
| `diagnostics.py` | Diagnoseexport mit erlaubten technischen Feldern |
| `strings.json` / `translations/` | Texte, Fehler und deutsche/englische Übersetzungen |
| `www/enigma2-connect-remote-card.js` | Separat installierbare Dashboardkarte |
| `tests/` | Python- und JavaScript-Regressionstests |

Ein Config Entry repräsentiert einen Receiver. Sein typisiertes `runtime_data`
enthält den `EnigmaCoordinator`. Dieser verwendet den OpenWebif-Client mit einer
gemeinsamen Home-Assistant-HTTP-Session und stellt Snapshots für neun Plattformen
bereit: `media_player`, `remote`, `notify`, `select`, `sensor`, `binary_sensor`,
`camera`, `calendar` und `button`. Das Manifest deklariert `device` und
`local_polling`. Es sind keine zusätzlichen Laufzeitpakete deklariert.

Status, Signal und EPG teilen den einstellbaren Abfragezyklus (standardmäßig
15 Sekunden). Timer und Aufnahmen haben 120 Sekunden, Senderkataloge 300 Sekunden
als reguläre Frist. Listenaktionen können früher aktualisieren. Screenshots
werden auf Anforderung geladen und fünf Sekunden zwischengespeichert.

Die Dashboardkarte ruft ausschließlich `remote.send_command` in Home Assistant
auf und verwendet keine Receiver-Zugangsdaten. Installation und Update der Karte
beschreibt das [Benutzerhandbuch](BENUTZERHANDBUCH.md#fernbedienung-im-dashboard).

## Externe Wiedergabe

Die Option `external_playback` schaltet die generische Medienauflösung für
`recording/…` und `channel/…` frei. Katalogzuordnung und vorhandene Receiver-
Wiedergabe bleiben erhalten. TS-Aufnahmen verwenden `/file?action=download&file=…`;
Live-TV verwendet die gespeicherte Receiver-Adresse mit `stream_port` (8001) und
`stream_https` (false). `stream_mode` ist standardmäßig `auto`; `compatible`
erzwingt die bisherige vollständige Umwandlung. `stream.m3u` und `streamnew.m3u`
werden wegen möglicher `zapstream`-Nebenwirkungen nicht aufgerufen. Stattdessen
werden `/web/streamhls.m3u` ohne `zap` und `/web/video.m3u?device=phone` verwendet.
Es werden weder beliebige Benutzer-URLs noch neue Receiver-Dateipfade akzeptiert.

Die Medienauflösung meldet exakt `application/x-mpegURL`. Home Assistants
[Medien-Dialog](https://github.com/home-assistant/frontend/blob/dev/src/panels/media-browser/hui-dialog-web-browser-play-media.ts)
aktiviert nur dafür `ha-hls-player`; `application/vnd.apple.mpegurl` wird an dieser
Stelle trotz gültigem HLS-Stream als nicht unterstützter Medientyp abgewiesen.
Der eingebaute HLS-Player verwendet hls.js beziehungsweise native HLS-Wiedergabe.

`stream_receiver.py` prüft für Live-TV einen optionalen Receiver-HLS-Ausgang.
Nur dessen erwartete 307-Antwort wird ausgewertet; sie wird nicht automatisch
verfolgt. Adressen müssen HTTP(S) auf dem gespeicherten Receiver-Host verwenden.
Eingebettete Zugangsdaten werden entfernt; verwendet wird die gespeicherte Anmeldung.
Separate HLS-Zugangsdaten werden derzeit nicht unterstützt. Bei aktiviertem
HTTPS für Live-TV werden HTTP-Kandidaten verworfen. Unterstützt werden
unverschlüsselte MPEG-TS-Medienplaylists mit höchstens 64 Segmenten und einer
Zieldauer bis 30 Sekunden. Masterplaylists, fMP4, Schlüssel, Byte-Ranges und unbekannte
Tags führen zum lokalen Rückfall. Playlists sind auf 256 KiB, Segmente auf 32 MiB
begrenzt; maximal 128 Segmentadressen bleiben für laufende Abrufe bekannt. Alle
Segmentadressen müssen denselben Ursprung wie die Receiver-HLS-Playlist haben.
Sie werden in token-geschützte HA-Adressen umgeschrieben. Dabei entsteht kein
lokales HLS-Verzeichnis und kein dauerhafter FFmpeg-Prozess.

`stream_codec.py` prüft die erste Video-/Audiospur mit einem kurzlebigen ffprobe-
Prozess über ein privates Loopback-Relay. Timeout sechs Sekunden, Ausgabe maximal
64 KiB, Eingang ausschließlich MPEG-TS über HTTP/TCP. ffprobe wird neben dem
konfigurierten FFmpeg-Programm oder im Suchpfad gesucht. Konservativ unverändert
bleiben progressives H.264 mit 8-Bit-YUV420, Baseline/Main/High bis Level 4.2 sowie
AAC-LC mit höchstens zwei Kanälen und 44,1/48 kHz. Fehlende oder unklare Angaben
führen zur Umwandlung. Bei ungeeignetem Live-TV wird vorher ein separater
Receiver-Transcoding-Ausgang geprüft und nur bei kompatiblem Video übernommen.
Aufnahmen verwenden den Original-Dateizugang. Zuerst wird spulbares VOD versucht;
nur dessen Fallback verwendet die oben beschriebene Codec-Prüfung.

`MediaStream` in `media_stream.py` verwaltet einen Pool unabhängiger
`StreamSession`-Objekte pro Receiver. `stream_limit` ist standardmäßig 5; 0 bedeutet
unbegrenzt. Die Zulassungsprüfung reserviert Plätze unter einem Lock, bevor
asynchrone Starts parallel beginnen. Auch laufende Startversuche zählen. Bei
erreichter Grenze folgt `stream_limit_reached` mit der eingestellten Anzahl;
vorhandene Streams werden nicht verdrängt. Geschlossene, abgelaufene oder
fehlgeschlagene Sitzungen werden vor der Zulassung aufgeräumt.

Live-TV mit identischer Quell-URL nutzt dieselbe Sitzung und dieselbe Capability,
auch bei gleichzeitig eintreffenden Auflösungen. Aufnahmen werden nicht geteilt,
sondern starten separat am Anfang. Ein abgebrochener Auflösungsaufruf beendet
keinen von weiteren Zuschauern erwarteten gemeinsamen Start (`asyncio.shield`).
Ein verwaister Start bleibt durch Start- und Inaktivitätsfristen begrenzt.
Der HTTP-Endpunkt ordnet jeden Abruf anhand des Tokens seiner Sitzung zu.
Entladen und HA-Stopp brechen alle ausstehenden Starts ab und schließen alle
Sitzungen. Das Speichern von Optionen verwendet weiterhin HA-Neuladen und
beendet deshalb die laufenden Streams dieses Receivers.

Jede `StreamSession` startet höchstens einen dauerhaften FFmpeg-Prozess. Nur das
Relay kennt Receiver-Adresse und Anmeldung; TLS-Prüfung, Redirect-Verbot und
einzelne validierte Byte-Ranges bleiben erhalten. Geeignete Spuren verwenden
`-c:v copy` beziehungsweise `-c:a copy`. Nur die Video-Umwandlung setzt H.264 Main,
maximal 720p/25 fps, zwei Encoder-Threads und begrenzte Bitrate; die Ton-Umwandlung
liefert AAC Stereo. Nur der Aufnahme-Fallback wird in Echtzeit gelesen (`-re`). Dessen
HLS behält acht Segmente mit Zieldauer zwei Sekunden; kopierte Schlüsselbildabstände
können diese verlängern. Dateien werden atomar veröffentlicht und alte Segmente
gelöscht. Bei optimiertem Startfehler erfolgt ein weiterer Start mit vollständiger
Umwandlung; beide Versuche sind jeweils auf 30 Sekunden begrenzt. Laufende
Browser-Decodierfehler lassen sich über den Kompatibilitätsmodus umgehen.
Debug-Logging meldet Formate und Verarbeitung ohne Receiver-Adressen; Details folgen unten.

Der HA-Endpunkt verwendet zufällige 256-Bit-Capabilities statt Receiver-Anmeldung.
Jeder Playlist-/Segmentabruf prüft Token, geladenen Eintrag, Option und Ablaufzeit.
Die Dateinamens-Allowlist lässt keine Pfade zu. Tokens laufen nach 120 Sekunden
ohne gültigen Abruf, nach sechs Stunden und beim Entladen ab. Eine neue Auswahl
eines anderen Streams verändert bestehende Tokens nicht.
Ein Hintergrundlauf räumt spätestens 15 Sekunden nach Ablauf auf; HA-Stopp beendet
auch den Prozess. Im Browser und auf Cast-Geräten stehen ausschließlich HA-URLs.
Diese URLs sind bis zum Ablauf vertraulich zu behandeln.

Automatisierte Prüfungen verwenden simulierte Receiver. Echte FFmpeg-Tests
prüfen synthetisches MPEG-2/MP2 mit vollständiger Umwandlung, H.264/AAC mit Kopie
beider Spuren sowie H.264/MP2 mit alleiniger Tonumwandlung und decodieren die
HLS-Ausgabe. Ein synthetischer Receiver-HLS-Test prüft die Weitergabe ohne Encoder.
Das ersetzt keine Browser-/Cast-Abnahme. Mehrfachstreams, gemeinsames Live-TV,
separate Aufnahmen, Reservierung der Obergrenze, Abbruch und Aufräumen werden mit
simulierten Receivern geprüft. VOD wird zusätzlich mit synthetischen Farbszenen
und einem echten FFmpeg-HLS-Client geprüft; die Browser-/Cast-Abnahme bleibt offen.
Audio-only-Streams sind weiterhin nicht enthalten. Bedienung steht im [Benutzerhandbuch](BENUTZERHANDBUCH.md#auf-anderen-geräten-abspielen).

Quellen: [OpenWebif-Controller](https://github.com/oe-alliance/OpenWebif/blob/main/plugin/controllers/web.py),
[FFmpeg HLS](https://ffmpeg.org/ffmpeg-formats.html#hls-2).

## Streaming-Diagnose und Qualität

Die Debugprotokollierung der Integration enthält Meldungen der Module
`media_stream`, `stream_codec` und `stream_vod`. Die unabhängige Kennung `[stream=…]` ordnet
Start, Codec-Prüfung, Verarbeitungsweg, gemeinsame Live-Nutzung und Aufräumen
derselben Sitzung zu. Neue parallele Sitzungen erhalten eigene Kennungen.
Eine volle Stream-Grenze wird mit aktueller Belegung und Grenze protokolliert.
Es werden keine Sender-/Aufnahmetitel, Receiver-Adressen, Zugangsdaten oder
geheimen Wiedergabe-URLs in diesen Diagnosemeldungen ausgegeben.

`Input original`, `Input receiver_transcoding` und `Input receiver_hls` unterscheiden
die untersuchten Quellen. Die Prüfung liest MPEG-TS; bei HLS wird ein TS-Segment
untersucht. Erfasst werden die erste Video-/Audiospur mit Codec, Profil,
Pixelformat, Halbbildreihenfolge, Level, Auflösung, Bildrate, Bitrate, Kanalzahl und
Abtastrate, soweit ffprobe Werte liefert. `unknown` bedeutet unbekannt,
`track=absent` keine erkannte Spur. Das sind Eingangsparameter, keine Messung der
tatsächlich zum Browser übertragenen Bitrate. Im linearen Kompatibilitätsmodus
wird die Prüfung übersprungen (`not_probed`). VOD benötigt auch dort seine
Laufzeitprüfung; `Input recording_vod` meldet deren Ergebnisse.

`Started: processing=…` meldet den tatsächlich gestarteten Weg:
`copy_video`/`copy_audio` übernehmen Spuren, `encode_video`/`encode_audio` kodieren
sie in HA neu. `copy_audio` kann auch eine fehlende Audiospur bedeuten.
Das Präfix `receiver_transcoding+` bezeichnet den ausgewählten separaten
Transcoding-Endpunkt; `receiver_hls` reicht Receiver-HLS ohne HA-Kodierung weiter.
Ob und wie der Receiver intern kodiert, kann HA dabei nicht beweisen.
`recording_vod+copy_video+copy_audio` beziehungsweise
`recording_vod+copy_video+encode_audio` kennzeichnen spulbare Aufnahmen mit
Originalvideo; `recording_vod+encode_video+encode_audio` kennzeichnet vollständige
Umwandlung. `VOD remux`/`VOD render` zeigen angeforderte Zeitabschnitte;
`VOD remux unavailable` erklärt den Rückfall zur VOD-Kodierung. `VOD unavailable` erklärt den
Rückfall auf das begrenzte Fenster. `HA output` beziehungsweise `HA VOD output`
nennt die gewählten Ausgabevorgaben. Fehler enthalten sichere lokale
Validierungsgründe bzw. den Ausnahmetyp, keine ungefilterten Fehlermeldungen.
Codec-Unverträglichkeit, fehlende Verbesserung durch Receiver-Transcoding,
Probe-Fehler und Rückfall auf den Kompatibilitätsmodus werden sichtbar.

Aktuell wird eine HLS-Qualitätsstufe angeboten (`variants=1`), keine adaptive
Bitratenumschaltung. Durchgereichte Spuren behalten ihre Quellqualität.
Bei Receiver-Transcoding gelten dessen Einstellungen; HA-Videokodierung verwendet
H.264 Main/Level 3.1 innerhalb von 1280 × 720 bei 25 Bildern/s, Zielbitrate
2 Mbit/s und Maxrate 2,5 Mbit/s. Neu kodierter Ton ist AAC, Stereo, 48 kHz,
128 kbit/s. Diese Vorgaben sind derzeit nicht als Qualitätsoptionen einstellbar.
Für adaptive HLS-Wiedergabe müsste der Anbieter mehrere Qualitätsvarianten
bereitstellen; der Player wählt daraus anhand von Durchsatz und Puffer.

### HLS-Laufzeit und Spulen

`RecordingVOD` in `stream_vod.py` bietet abgeschlossene TS-Aufnahmen als feste
HLS-VOD-Playlist an. `#EXTINF` gibt die Segmentdauer an, `#EXT-X-PLAYLIST-TYPE:VOD`
kennzeichnet die unveränderliche Liste und `#EXT-X-ENDLIST` deren Ende. Die Summe
der Segmentdauern entspricht der ermittelten Laufzeit. Die Playlist referenziert
alle Abschnitte, obwohl diese erst auf Anforderung erzeugt werden. Grundlage:
[RFC 8216](https://www.rfc-editor.org/rfc/rfc8216.html).

Vor dem Start werden Byte-Ranges durch `bytes=0-0`, HTTP 206, passende
`Content-Range`/`Content-Length` und eine gleichbleibende Dateigröße geprüft.
ffprobe ermittelt die Video-Laufzeit, ersatzweise die Container-Laufzeit; zulässig
sind endliche positive Werte bis 24 Stunden. Ein Audio-Nachlauf kleiner als ein
Ausgabebild wird an einer Segmentgrenze abgeschnitten, damit keine leere letzte
Videosequenz angekündigt wird. Der erste Abschnitt wird vor der Freigabe der
Zeitleiste tatsächlich erzeugt. Die VOD-Vorbereitung ist insgesamt auf 20 Sekunden
begrenzt. Bei fehlenden Voraussetzungen folgt das bisherige Streaming-Fenster.
Die unveränderte Dateigröße wird vor jeder neuen Abschnittserzeugung erneut geprüft;
eine später wachsende/veränderte Aufnahme kann deshalb zu einem Wiedergabefehler führen.

**Originalvideo übernehmen:** Im automatischen Modus prüft `copy_codecs` die
vorhandenen Spuren. Bei geeignetem progressivem H.264 liest `RecordingRemux`
(`stream_remux.py`) den zugehörigen `.ts.ap`-Index über einen ausschließlich
lokalen Relay-Endpunkt. Zugangsdaten bleiben im Backend. Das Enigma2-Datenformat
besteht aus Big-Endian-Paaren von 64-Bit-Dateioffset und 90-kHz-Zeitstempel;
Formatreferenz: [Enigma2-Aufnahmeindex](https://github.com/openatv/enigma2/blob/master/lib/dvb/pvrparse.cpp).
Es wird kein fremder Implementierungscode übernommen.

Der Index ist auf 4 MiB begrenzt. Paketgrenzen, streng steigende Offsets und
Zeitstempel, Dateigröße, Anfang/Ende und maximale Schlüsselbildabstände werden
geprüft. Zeitstempelüberläufe, Sprünge und unpassende Indizes führen zum Rückfall.
Die unveränderliche Playlist gruppiert vorhandene Schlüsselbilder mit mindestens
6,4 Sekunden Abstand; ihre `EXTINF`-Werte und `TARGETDURATION` folgen den realen
Grenzen. Ein Schlussrest unter einer Sekunde bleibt beim vorherigen Abschnitt.
Die Zeitleiste beginnt am ersten indizierten Schlüsselbild.

FFmpeg erhält `-c:v copy`; kompatibler AAC-Ton erhält `-c:a copy`, anderer Ton
wird zu AAC gewandelt. Es gibt weder Skalierung noch Bildratenbegrenzung für
kopiertes Video. `-copyts` und ein gemeinsamer Ausgabeversatz erhalten die
Zeitbasis. Der Bitstreamfilter `noise=amount=0:drop=...` entfernt ausschließlich
Pakete außerhalb der Abschnittsgrenzen; `amount=0` verändert keine Nutzdaten.
Seine `drop`-Funktion wird vorab geprüft (lokal mit FFmpeg 8.1 getestet; FFmpeg 4.4
besitzt sie nicht). Ein fehlender Filter löst einen erklärten Rückfall aus.
Der Lesevorlauf entspricht dem größten Indexabstand plus einer Sekunde, mindestens
zwei Sekunden. Damit werden nur kurze Dateibereiche gelesen, ohne Videodekodierung.
Audiokodierung trimmt anhand derselben absoluten Zeitbasis.

**Vollständige Umwandlung als Rückfall:** Bei ungeeignetem Video, fehlendem Index,
nicht unterstützten Zeitstempeln oder explizitem Kompatibilitätsmodus bleibt der
vorhandene VOD-Encoder verfügbar. Abschnitte dauern 6,4 Sekunden, der letzte entsprechend kürzer. Das entspricht
160 Videobildern bei 25 fps und 300 AAC-Paketen bei 48 kHz; begrenzte
Bild-/Paketanzahlen verhindern Überlappungen an den Abschnittsgrenzen. Bei verfügbarem
Paketfilter begrenzt dieser zusätzlich die Ausgabe: Neuere FFmpeg-Versionen können
nach der vorgegebenen Anzahl Encoder-Eingabebilder noch ein AAC-Paket ausgeben. FFmpeg springt
mit eingabeseitigem `-ss` über das private HTTP-Relay bis zu zehn Sekunden vor
die gewünschte Zeit. Bild und Ton werden anhand derselben Zeitbasis exakt auf
den gewünschten Abschnitt getrimmt; nur dieser Abschnitt wird kodiert. `-output_ts_offset` ordnet die Ausgabe der absoluten
Aufnahmezeit zu; so funktioniert das Spulen über die vollständige Zeitleiste.
Jeder Abschnitt beginnt mit einem neuen Schlüsselbild. H.264 Main/Level 3.1,
720p/25 fps und AAC Stereo verwenden dieselben Qualitätsvorgaben wie die
bisherige HA-Kodierung (`encoding_args` in `stream_codec.py`). Dieser Rückfall kodiert beide
Spuren; der automatische Remux-Weg erhält geeignete Originalspuren.
Siehe [FFmpeg-Seeking](https://ffmpeg.org/ffmpeg.html) und
[Zeitstempeloptionen](https://ffmpeg.org/ffmpeg-formats.html).

Pro Aufnahme-Sitzung laufen höchstens ein Encoder und vier ausstehende
Abschnittsaufträge. Gleiche Anfragen teilen einen Auftrag; das Abbrechen eines
HTTP-Aufrufs beendet keine gemeinsam erwartete Erzeugung. Der LRU-Cache umfasst
höchstens acht Abschnitte und insgesamt maximal 32 MiB pro Sitzung.
Ein kodierter Abschnitt ist auf 4 MiB, ein Remux-Abschnitt auf 16 MiB begrenzt.
Die höhere Einzelgrenze erlaubt die ursprüngliche Video-Bitrate; bei Erreichen
der Gesamtgrenze werden ältere Abschnitte verdrängt.
Verdrängte Abschnitte können erneut erzeugt werden. Jeder Encoderlauf ist auf
20 Sekunden begrenzt. Entladen oder Sitzungsablauf brechen auch wartende Aufträge
ab, beenden Prozesse und leeren den Cache. Ein kompletter Download oder eine
vollständige Vorab-Konvertierung der Aufnahme ist nicht nötig.

Live-TV und der Aufnahme-Fallback behalten ihr bisheriges Sliding Window:
acht Segmente mit zwei Sekunden Zieldauer, gegebenenfalls länger bei kopierten
Schlüsselbildabständen. Receiver-HLS verwendet dessen Fenster. Eine bekannte
Gesamtlänge allein würde dort kein vollständiges Spulen ermöglichen.
Browser-Puffer sind unabhängig davon; lange Pausen und gespeicherte
Fortsetzungspositionen sind weiterhin nicht implementiert.

### Zeitbasis im HLS-Spultest

Der synthetische Farbtest prüft den Video-Start jedes erzeugten Segments auf
`1 + Segmentindex × 6,4` Sekunden (Genauigkeit eines 90-kHz-Ticks). AAC kann wegen
des Encoder-Vorlaufs früher beginnen: gemessen 0,978667 statt 1,000000 Sekunden.
FFmpegs relatives Eingabe-`-ss` bezieht sich auf den Containerstart. Deshalb nutzt
die Bildprüfung beim Farbwechsel die absolute Videozeit `-seek_timestamp 1 -ss 13.8`.
Der erwartete grüne Frame, der Abruf des dritten Segments und das vollständige
Dekodieren über Segmentgrenzen bleiben verpflichtende Prüfungen. Das ändert weder
die produktive Zeitleiste noch die Stream-Kodierung.

## Verhaltensregeln für Implementierungen

Die Optionsaktion zur Bild-Neugenerierung speichert pro Receiver einen
zufälligen Generationswert in `recording_image_generation`. Dieser fließt
in Bild-URLs und Cache-Schlüssel ein. `OptionsFlowWithReload` beendet die
alten Aufträge und startet die begrenzte Vorbereitung neu. Alte Dateien
bleiben unter der bestehenden Cache-Obergrenze; andere Receiver bleiben
unberührt. Normales Speichern erhält den Generationswert.

Bouquet-Optionen verwenden eine feste Namensauswahl (`custom_value=False`),
damit HA auch den ausgewählten Wert als Bezeichnung darstellt. Gespeichert
wird weiterhin die Service-Referenz. Fehlende gespeicherte Einträge werden
mit ihrem Bouquet-Dateinamen ergänzt; die leere Auswahl bleibt möglich.

### Aufnahmebilder

Einzelbilder benötigen ein in der HA-Laufzeit ausführbares FFmpeg; das Programm
wird nicht von Enigma2 Connect installiert. Ist die HA-FFmpeg-Integration geladen,
wird deren `binary` verwendet, sonst `ffmpeg` aus dem Suchpfad des HA-Prozesses.
Ein eigener Programmpfad lässt sich über `ffmpeg_bin` in der HA-FFmpeg-Konfiguration
setzen. Er muss innerhalb der tatsächlichen Laufzeit erreichbar sein, bei einer
Container-Installation also im Container. Nach einer Änderung der HA-Konfiguration
HA neu starten. Das ist eine Einstellung der FFmpeg-Integration, keine YAML-
Einrichtung von Enigma2 Connect. Bei Fehlern zusätzlich Lesbarkeit der Datei über
OpenWebif und den gewählten Snapshot-Zeitpunkt prüfen.

Die Medienbrowser erhalten eine relative, authentifizierte HA-Bildadresse mit
Receiver-ID, Hash der Aufnahme-Referenz und Einstellungs-Hash. Der HTTP-Endpunkt
prüft die Aufnahme gegen den aktuellen Katalog. Zugangsdaten und Dateipfade
stehen weder in der Bildadresse noch in den FFmpeg-Argumenten.

`recording_images.py` ruft nur ausgewählte Anbieter auf. Externe Bilder werden
auf fünf MiB begrenzt und als JPEG mit maximal 640 × 640 Pixeln gespeichert.
HTML, externe SVGs und HTTP-Weiterleitungen werden nicht übernommen. Der Cache
unter `.storage/enigma2_connect_thumbnails/<entry_id>/` enthält höchstens 128
Bilder je Receiver mit sieben Tagen Gültigkeit. Parallele Anfragen derselben
Aufnahme teilen einen Auftrag; pro Receiver läuft eine Bildgewinnung gleichzeitig.

Nach dem Plattform-Setup startet eine Hintergrundwarteschlange. Sie wird mit den
ohnehin vorhandenen Katalogabfragen abgeglichen, auch wenn sich die Listen nicht
geändert haben. Das prüft zugleich Fehlerfristen und Cache-Ablauf. Neuere Aufnahmen
stehen vor älteren; die Vorauswahl ist auf die 128 neuesten Einträge begrenzt.
Zwischen Aufträgen liegen fünf Sekunden, ausstehende Bildanfragen haben Vorrang.
Gelöschte Einträge entfallen aus der Warteschlange; Entladen beendet Worker und
Bildaufträge. Es gibt keine zusätzliche Receiver-Pollschleife.

Laufende Aufnahmen werden anhand des Timer-Dateinamens und Status erkannt, bei
fehlender Zuordnung vorsichtig anhand von Receiverstatus, Dateialter und Dauer.
Ein Snapshot wartet auf die gewählte Position; eine kurze beendete Aufnahme nutzt
die Mitte. `tests/test_recording_preparation.py` prüft Start, Katalogaktualisierung,
Priorität, laufende Aufnahmen, Cache-Wiederverwendung und -Ablauf, Fehlerwiederholung,
begrenzte Archivvorbereitung sowie Entladen mit simulierten Receiver-/Bildantworten.

`recording_snapshot.py` stellt FFmpeg einen vorübergehenden Loopback-Endpunkt zur
Verfügung. Dieser liest ausschließlich die gewählte Datei über OpenWebif
`/file?action=download&file=…`, einschließlich HTTP-Range-Anfragen. Die Ausführung
ist auf 45 Sekunden und insgesamt 64 MiB Videodaten begrenzt. Ein Timeout, eine
nicht lesbare Datei oder fehlendes FFmpeg führt zum nächsten gewählten Anbieter
beziehungsweise zum neutralen Ersatzbild. Entladen beendet ausstehende Aufträge.

`tests/test_recording_images.py` prüft Optionen, Abschalten, Anbieter-Fallback,
Cache, Größenlimits, Authentifizierung und Abbruch. Der FFmpeg-Test erzeugt eine
synthetische MPEG-TS-Datei mit Farbwechsel und prüft echte Bilder nach zwei und
zehn Minuten über einen lokalen HTTP-Dateiserver mit Range-Unterstützung. Ohne
FFmpeg wird dieser einzelne Test übersprungen. TMDB-/OMDb-Antworten und Receiver
sind simuliert; dies ist kein Nachweis einer Prüfung mit echten API-Schlüsseln
oder einer Aufnahmedatei auf einem Hardware-Receiver.

### Allgemeine Regeln

Die optionale Senderliste verwendet `Snapshot.media_channels`. Ein explizites
Medien-Bouquet wird mit den regulären Senderkatalog-Abfragen geladen, ohne das
Bouquet unter Quelle umzuschalten. Ohne explizite Auswahl wird dessen Katalog
wiederverwendet. Eine fehlgeschlagene zusätzliche Bouquet-Abfrage macht die
normale Receiver-Steuerung nicht unverfügbar.

Sender-IDs enthalten Receiver-ID und Hash der Service-Referenz. Wiedergabe und
Picon-Endpunkt prüfen aktivierte Senderanzeige, aktuellen Katalog und Receiver-
Zuordnung. Picons nutzen den bestehenden lokalen Referenz-/Namens-Fallback;
der Browser erhält nur die HA-Bildadresse. Der Speicher-Cache hält bis zu 256
Bilder, 15 Minuten bei Erfolg beziehungsweise zwei Minuten für Ersatzsymbole;
höchstens vier Picon-Aufrufe laufen gleichzeitig. `tests/test_channel_media.py`
prüft Optionen, separate Bouquets, beide Medienansichten, Wiedergabe über HA,
Receiver-Zuordnung, Authentifizierung, Cache und fehlende Picons mit simulierten
Receiver-Antworten. Die Senderbilder werden nicht im Voraus abgefragt.

- Statusabfragen über den Coordinator bündeln; keine eigenen Pollschleifen pro
  Entität. Mutationen und vollständige Tastenfolgen serialisieren, damit parallele
  Automationen keine Tasten vermischen.
- Für normale Steuerung vorhandene HA-Aktionen nutzen (`media_player.*`,
  `remote.send_command`, `notify.send_message`, `select.select_option`,
  `button.press`, `camera.snapshot`). Eigene Geräteaktionen benötigen ausdrücklich
  `device_id`; keine stillschweigende Auswahl des ersten Receivers.
- Fehlende optionale Daten von leeren Listen unterscheiden. Verbindungsprobleme
  dürfen nicht als Standby erscheinen; Authentifizierungsfehler führen zur
  erneuten Anmeldung. Neustart und Tiefschlaf bei unklarer Antwort nicht erneut senden.
- Zugangsdaten in Request-Headern halten. Keine Zugangsdaten, Rohantworten oder
  Nachrichteninhalte protokollieren. Diagnoseexporte verwenden eine Allowlist.
- Die Aufnahmekachel ist für alle Receiver gemeinsam. Ihre Darstellungsoption
  wird bei allen Einträgen gespeichert. Wiedergabe muss den Receiver prüfen, dem
  die Aufnahme gehört. Generische HLS-Auflösung benötigt die explizite Option
  `external_playback`; Zugangsdaten bleiben im Relay.
- Die Firmware liefert keinen verlässlichen Pausezustand. Den angenommenen
  Wiedergabestatus nicht als bestätigte Pause-/Timeshift-Rückmeldung darstellen.
- Backend-Texte und Übersetzungsschlüssel gemeinsam pflegen. Die Karte nutzt die
  Profilsprache, Aufnahmetitel und automatische Entitätsnamen die HA-Systemsprache.
  Bei nicht unterstützten Sprachen Englisch verwenden; Receiver-Texte unverändert lassen.

### Wiederkehrende Timer und Zeitumstellungen

Vom Receiver gelieferte Zeitstempel haben Vorrang. Weitere Wochenwiederholungen
werden in der Receiver-Zeitzone berechnet. Nicht existierende Start-/Endzeiten
im Frühjahr werden ausgelassen; bei einer doppelten Uhrzeit im Herbst wird für
hochgerechnete Termine die erste verwendet. Hat ein Timer durch die Rückstellung
keine positive Dauer nach lokaler Uhrzeit, wird für weitere Wiederholungen seine
tatsächlich verstrichene Dauer verwendet. Diese Kalenderberechnung verändert
keine Receiver-Timer und muss für Sonderfälle mit der konkreten Firmware
verglichen werden. Löschen/Umschalten benötigt die Originalwerte des Timers,
nicht die Werte einer expandierten Kalenderinstanz.

## Dokumentation und Änderungen

Vor Änderungen bestehenden Code und Verhalten nachvollziehen und einen kurzen
Implementierungsplan erstellen. Vorhandene fremde Änderungen erhalten. Danach
Tests, Syntax und lokal mögliche HA-Kompatibilität prüfen und die betroffene
Dokumentation in beiden Sprachen aktualisieren.

Die Dokumentation hat drei Einstiege:

- `README.md`: gemeinsamer kurzer Überblick für Anwender mit Voraussetzungen,
  ersten Schritten und weiterführenden Links; Deutsch zuerst, danach Englisch.
- `docs/BENUTZERHANDBUCH.md` / `docs/USER_GUIDE.en.md`: vollständige Anleitung für
  Einrichtung, Alltag, Optionen, Automationen und Fehlersuche.
- Dieses Dokument / `docs/DEVELOPMENT.en.md`: Entwicklerwissen und Verweise auf
  technische Vertiefungen und Prüfberichte.

Die README bietet Sprunglinks zu beiden Sprachen; die getrennten Sprachfassungen
der übrigen Dokumente verlinken sich gegenseitig. Versionshistorie gehört ausschließlich
in beide Changelogs. Die verbindlichen [Projektvorgaben](../AGENTS.md) regeln die
automatische Versionsanhebung; Manifest, `pyproject.toml`, lokaler Paketeintrag
in `uv.lock` und beide Changelogs müssen synchron bleiben.

Auf `develop` oder einem Arbeitsbranch arbeiten. Eine Übernahme nach `main`
erfolgt nur nach ausdrücklicher Nutzerfreigabe per Pull Request. Vor dem PR ist
der aktuelle Remote-/Tag-/Release-Abgleich erforderlich. Ein Release benötigt
einen eigenen ausdrücklichen Auftrag. Den vollständigen Ablauf beschreibt die
[Release-Anleitung](../RELEASING.md). Keine ZIP-Dateien ohne ausdrücklichen Auftrag erzeugen.


## Identität und Datenverarbeitung

Die Geräteidentität basiert auf einer normalisierten brauchbaren MAC-Adresse;
ohne sie dient der normalisierte Host als Fallback. Ein Adresswechsel erfolgt
über Reconfigure. Für MAC-basierte Einträge wird dabei die Identität geprüft;
ein Host-Fallback kann einen Gerätetausch hinter derselben Adresse nicht erkennen.

Der erste erfolgreiche Coordinator-Refresh erfolgt vor dem Plattformaufbau.
`OptionsFlowWithReload` übernimmt Optionsänderungen. Der Coordinator verwendet
`always_update=False`; fehlende optionale Listen werden als `None` behandelt,
nicht als leere Liste. Der Verbindungs-Binary-Sensor bleibt als Abrufstatus verfügbar.
Optionale Endpunkte werden erneut versucht; Authentifizierungsfehler bleiben sichtbar.
Bouquetwechsel und Polls verwenden einen gemeinsamen Daten-Lock. Neue Senderlisten
werden erst nach erfolgreichem Abruf veröffentlicht.

Die Aufnahmeabfrage verwendet `movielist` mit `recursive=1`; die Navigation bildet
die zurückgelieferten Dateipfade ab. Das ist keine eigenständige Durchsuchung von
Netzlaufwerken. Aufnahmedaten und -zeiten werden in der HA-Zeitzone dargestellt.
Der aktuelle Senderzustand stammt aus der Receiver-Abfrage, nicht aus einer
optimistischen lokalen Auswahl. Im Screenshot-Modus liegt nach einem erkannten
Senderwechsel mindestens eine Sekunde vor dem ersten Bildabruf; das garantiert
kein fertiges Bild für jede Firmware.

Signalwerte werden normalisiert. Ein ganzzahliger Prozent-Ersatzwert im dB-Feld
wird nicht als echter dB-Wert veröffentlicht; BER bleibt ohne erfundene Einheit.
Temperatur, freier RAM/Plattenspeicher und Uptime sind nicht implementiert.
Wake-on-LAN und neue wiederkehrende Timer gehören nicht zum aktuellen Umfang.
Die externe HLS-Wiedergabe hat die oben beschriebenen Grenzen.

## Validierung von Aktionen

Aktionsnamen und Anwendungsbeispiele stehen im
[Benutzerhandbuch](BENUTZERHANDBUCH.md#aktionen-und-beispiele).

Eigene Geräteaktionen haben kein implizites Standardgerät. Ihre Validierung
steht in `services.py` und `services.yaml`. Die Notify-Entität verwendet die
Nachrichtenoptionen des Receivers; `enigma2_connect.message` verwendet dagegen
eigene Aktionswerte (Standard: Typ 1, Dauer 10 Sekunden).

Die Zielprüfung vergleicht `DeviceEntry.config_entry_id` mit den Einträgen der
Integration und verlangt den Zustand `LOADED`. Unbekannte Geräte, Geräte anderer
Integrationen und nicht geladene Einträge ergeben den übersetzten Fehler
`invalid_target`. Die veraltete Eigenschaft `config_entries` wird nicht verwendet.
Der direkte Vergleich erhält die eindeutige Zuordnung; der HA-Helfer
`async_get_device_and_config_entry_for_domain` kann bei alten zusammengesetzten
Geräte-IDs mit mehreren passenden Aufteilungen einen beliebigen Treffer liefern.

Timeraktionen akzeptieren Unix-Zeitstempel oder ISO-Datumsangaben mit
Zeitzonenoffset. Löschen und Umschalten verwenden die ursprünglichen
Receiver-Zeitstempel; nach erfolgreichen Timeraktionen werden Listen invalidiert.

Bei der Fernbedienung sind benannte Tasten aus `const.py` und numerische Linux-
Keycodes von 0 bis `0x2FF` erlaubt. `hold_secs > 0` sendet den OpenWebif-Tastentyp
`long`; die Firmware bestimmt die tatsächliche Haltezeit. Eine Sendernummer sendet
Ziffern und OK. Service-Referenzen lassen sich in OpenWebif ermitteln,
Bouquetreferenzen über `/api/bouquets`. Die aktuelle Optionsoberfläche bietet
eine feste Namensauswahl; frühere gespeicherte eigene Referenzen bleiben erhalten.

## Vorgemerkte Ideen

Diese Ideen sind unverbindlich; Prioritäten sind eine Einschätzung, keine Zusage
für die nächste Version. Bereits vorhandene Teilfunktionen sind unten benannt.

### Erweiterungen aus der OpenWebif-Recherche

Die Recherche vom 13. September 2026 zu
[oe-alliance/OpenWebif](https://github.com/oe-alliance/OpenWebif) liefert folgende
Erweiterungsmöglichkeiten. Die Schnittstellen wurden anhand von Dokumentation und
Quellcode untersucht; ihre zusätzliche Funktionalität ist damit nicht auf den
beiden Testreceivern oder in einer echten HA-Installation geprüft. Unterstützung
und Rückgabeformate vor einer Umsetzung je OpenWebif-Version und Image prüfen.

| Nr. | Priorität | Idee | Nutzen, Schnittstelle und Grenzen |
| --- | --- | --- | --- |
| 1 | Hoch | EPG durchsuchen und direkt aufnehmen | Sendungen nach Titel finden, Wiederholungstermine suchen und Treffer ohne manuelle Zeitangaben aufnehmen. Grundlage: `epgsearch`, `epgsimilar`, `timeraddbyeventid`. Die laufende/nächste Sendung wird bereits angezeigt; ergänzt würden Suche und Aufnahme aus einem Treffer. [EPG-API][ideas-api] |
| 2 | Hoch | Timer bearbeiten und Wochenserien anlegen | Vorhandene Timer verlängern, Wochentage, Aufnahmeordner und Tags festlegen. Anlegen, Löschen, Aktivieren/Deaktivieren und lesende Kalenderwiederholungen sind vorhanden. Ergänzung über `timerchange` und `repeated`; einzelne Kalenderinstanzen nicht mit dem gesamten Receiver-Timer verwechseln. [Timerimplementierung][ideas-timers] |
| 3 | Hoch | Aufnahmekonflikte gezielt auswerten | Kollidierende Sendungen mit Zeiten anzeigen und Automationen zugänglich machen. Beim Anlegen/Bearbeiten liefert OpenWebif strukturierte `conflicts`. Das wäre eine Erweiterung der bisherigen Fehlerauswertung, keine belegte separate Konfliktvorhersage. [Timerimplementierung][ideas-timers] |
| 4 | Hoch | Sofortaufnahme als eigene Aktion | Dashboard-Button oder Sprachaktion „Aktuelle Sendung aufnehmen“ über `recordnow`. Der Ereignismodus benötigt EPG; der alternativ „unendlich“ genannte Modus ist im untersuchten Code auf zehn Stunden begrenzt. [Timerimplementierung][ideas-timers] |
| 5 | Hoch | Aufnahmebibliothek erweitern | Aufnahmeordner und HA-Medienquelle sind inzwischen vorhanden. Weitere Ausbaustufen: Tags/Filter, zusätzliche Metadaten wie Dateigröße und bisheriger Wiedergabefortschritt sowie Umbenennen, Verschieben und Löschen. OpenWebif bietet `movielist`, `fullmovielist` und Verwaltungsaktionen. Lösch-/Papierkorbverhalten je Image berücksichtigen. [Aufnahmeverwaltung][ideas-movies] |
| 6 | Mittel | Festplattenspeicher und Systemdiagnose | Freien Aufnahmeplatz überwachen; RAM und Uptime als optionale Diagnosesensoren ergänzen. `about` liefert die Grundlagen. Einheiten normalisieren und langsam abfragen; als frei gemeldeter RAM enthält im untersuchten Code auch Buffer und Cache. [Informationsmodell][ideas-info] |
| 7 | Mittel | Tonspur auswählen | Originalton, alternative Sprache oder Audiodeskription per dynamischer `select`-Entität wählen. Grundlage: `getaudiotracks` und `selectaudiotrack`; Auswahl nach Senderwechsel aktualisieren. [Audio-API][ideas-api] |
| 8 | Mittel | Timeshift gezielt steuern und anzeigen | Start-/Stopp-Aktionen und „Timeshift aktiv“ über `tsstart`, `tsstop`, `tsstate`. `timeshiftEnabled` ist kein verlässlicher Pausezustand; der untersuchte Stopp-Pfad unterdrückt die Speicherrückfrage. [Controller][ideas-controller] |
| 9 | Mittel | Wiedergabeposition bei Aufnahmen | Fortschritt und Restzeit im Medienplayer anzeigen. Das bereits abgefragte `getcurrent` liefert für bestimmte lokale Aufnahmen eine Position in Sekunden. Diese allein erlaubt keine sichere Pauseerkennung. [Controller][ideas-controller] |
| 10 | Mittel | Receiver-Sleeptimer | „In 30 Minuten Standby“ mit Statusanzeige über den geräteeigenen `sleeptimer`. Verfügbare Felder und Verhalten unterscheiden sich nach Image. [Timerimplementierung][ideas-timers] |
| 11 | Optional | Einschalten ohne Mitwecken des Fernsehers | Für Radio oder Hintergrundautomationen: `supports_powerup_without_waking_tv` und `set_powerup_without_waking_tv` sind dokumentiert. Image-Unterstützung prüfen; die Funktion ersetzt kein Aufwecken aus Tiefschlaf. [Steuerungs-API][ideas-api] |
| 12 | Optional | Text an Eingabefelder senden | Suchbegriffe direkt eingeben, statt einzelne Fernbedienungstasten zu senden. `remotecontrol` besitzt einen `text`-Parameter; das aktive Eingabefeld am Receiver bleibt entscheidend. [Controller][ideas-controller] |
| 13 | Größeres Projekt | Live-TV und Aufnahmen auf anderen Geräten abspielen | Erste Ausbaustufe als optionale [HLS-Wiedergabe](#externe-wiedergabe) umgesetzt; VOD-Spulen für geeignete TS-Aufnahmen ist umgesetzt. Die konkrete Browser-/Cast-Abnahme bleibt offen. OpenWebif bietet Stream-/Playlist-Endpunkte einschließlich eines HLS-Einstiegs. Codec-Unterstützung, Authentifizierung und gegebenenfalls Transcoding separat lösen; ein API-Endpunkt belegt keine funktionierende Wiedergabe auf jedem Zielgerät. [Streaming-Endpunkte][ideas-controller] |

Als mögliche erste Ausbaustufe bietet sich **Sofortaufnahme → Timerbearbeitung
mit Konfliktdetails → EPG-Suche mit Aufnahmeaktion** an. Das ist eine vorgeschlagene
Reihenfolge, kein Umsetzungsauftrag.

[ideas-api]: https://github.com/oe-alliance/OpenWebif/wiki/OpenWebif-API-documentation
[ideas-timers]: https://github.com/oe-alliance/OpenWebif/blob/main/plugin/controllers/models/timers.py
[ideas-movies]: https://github.com/oe-alliance/OpenWebif/blob/main/plugin/controllers/models/movies.py
[ideas-info]: https://github.com/oe-alliance/OpenWebif/blob/main/plugin/controllers/models/info.py
[ideas-controller]: https://github.com/oe-alliance/OpenWebif/blob/main/plugin/controllers/web.py

### Weitere vorgemerkte Ideen

**Snapshots auf dem Receiver erzeugen:** Ein optionaler Dienst oder ein Enigma2-
Plugin könnte mit dort verfügbarem FFmpeg ein Einzelbild liefern. Zeitpunkt je
Receiver beibehalten; keine Wiedergabe starten. Vorher Decoder, Rechenleistung,
Installation/Updates, Authentifizierung, begrenzte Dateizugriffe, Cache, laufende
Aufnahmen und Standby prüfen. Der normale Bildschirmfoto-Endpunkt ersetzt keine
Bildgewinnung aus einer beliebigen Aufnahmedatei.

**Interaktive Nachrichten:** Antworten auf Ja/Nein-Fragen sind noch nicht in HA
verfügbar. Eine spätere Erweiterung könnte `messageanswer` nutzen. Konfigurierbare
Vorauswahl, eigene Antworten wie „Jetzt/Später/Abbrechen“ und eindeutig erkannte
Zeitabläufe benötigen eine passende Receiver-Schnittstelle. Vorher die Zuordnung
von Fragen/Antworten, parallele Dialoge und Firmware-Unterschiede prüfen; die letzte
Antwort allein belegt keine manuelle Bestätigung. Ausgangspunkte:
[OpenWebif-Nachrichtenmodell](https://github.com/E2OpenPlugins/e2openplugin-OpenWebif/blob/master/plugin/controllers/models/message.py)
und [Enigma2-Dialog](https://github.com/openatv/enigma2/blob/master/lib/python/Screens/MessageBox.py).

## Dateibestand und lokale Archive

`docs/` enthält das Benutzerhandbuch und diese Entwicklerdokumentation jeweils
auf Deutsch und Englisch, die zweisprachige [Prüfübersicht](VALIDIERUNG.md) sowie
den erhaltenen [Lizenznachweis mit Quellständen](LIZENZEN.md). Die deutsche
Lizenzbewertung ist ein datierter Herkunftsnachweis, keine neue Rechtsberatung.

Die aktiven Logoquellen, die benötigte Schrift samt OFL-Lizenz und das Exportskript
liegen unter [assets/branding](../assets/branding/README.md). Die acht fertigen
Laufzeit-PNGs bleiben im Komponentenordner `brand/`. Versionshistorie und
Release-Ablauf bleiben in den Changelogs und Release-Anleitungen im Projektstamm.

Frühere Analysen, Funktionsvergleiche, ausführliche historische Prüfberichte,
Quelleninventare und Logoentwürfe liegen nur im lokalen Ordner `.local-archive/`.
Der Stand vor der Bereinigung wurde vollständig erhalten und per SHA-256 geprüft;
jedes Archiv enthält ein `inventory.json`. `.gitignore` schließt diesen Ordner aus.
Er ist daher nicht in einem frischen Clone verfügbar und muss bei Bedarf separat
gesichert werden. Bereits vorhandene Git-Historie wird dadurch nicht umgeschrieben.

In Veröffentlichungen nur `custom_components/enigma2_connect` als Integration
ausliefern; die optionale Karte unter `www/` separat bereitstellen. `.work/`,
`.local-archive/`, lokale Testumgebungen und Caches nicht verteilen. Aktuelle
Dokumentation darf keine benötigten Schritte ausschließlich im lokalen Archiv
beschreiben. Vor dem PR auch neue Dateien und die entfernten alten Pfade prüfen;
`git diff --check` allein prüft keine unversionierten Dateien oder Dokumentationslinks.

## Manueller Junie-Test

Der Dispatch-Eingang `junie_test=true` prüft genau den gespeicherten Modbus-Beitrag
vom 02.09.2026 mit dem Repository-Secret `JUNIE_API_KEY`. Die offizielle Action
v1.7.9 ist auf einen Commit fixiert und nutzt `silent_mode`, Junie CLI 3110.6
und das Standardmodell. GitHub-Rechte sind ausschließlich lesend.

Der bestehende Status wird nur gelesen. Ein Analyseauftrag prüft Pflichtanpassungen
und optionale Verbesserungen auf Deutsch. Ergebnisstruktur und Quellbelege werden
anschließend lokal validiert; die inhaltliche Richtigkeit bleibt manuell zu prüfen.
Das Artefakt `ha-blog-junie-test` bleibt sieben Tage erhalten. Der Junie-Schritt
ist auf sechs Minuten begrenzt. Das ist keine feste Credit-Obergrenze; ein
Agentenauftrag kann mehrere Modellaufrufe benötigen. Keine automatische Wiederholung,
kein Anbieterwechsel und keine Aktivierung im Wochenplan. Der Test nutzt
vorhandenes Guthaben; er kauft keine Credits und ändert keinen Tarif.

Teststand 16.09.2026: Der Modbus-Einzeltest war erfolgreich und nannte alle
Fristen. Junie meldete rund 0,048 USD Modellkosten; das Standardmodell war
Gemini 3.7 Flash. Die Top-up-Abbuchung ist noch nicht bestätigt. Der produktive Ablauf und weitere Relevanzfälle werden getrennt validiert.
Siehe [Prüfübersicht](VALIDIERUNG.md).
