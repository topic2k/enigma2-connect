[Deutsch](ENTWICKLUNG.md) | [English](DEVELOPMENT.en.md)

# Entwicklerdokumentation

Diese Anleitung bündelt die Informationen für Änderungen an Enigma2 Connect.
Für Installation und Bedienung gibt es das [Benutzerhandbuch](BENUTZERHANDBUCH.md);
die [README](../README.md) bleibt der kurze Einstieg für Anwender.

## Inhaltsverzeichnis

- [Projekt und Voraussetzungen](#projekt-und-voraussetzungen)
- [Entwicklungsumgebung und Prüfungen](#entwicklungsumgebung-und-prüfungen)
- [Home-Assistant-Entwicklerblog überwachen](#home-assistant-entwicklerblog-überwachen)
- [Aufbau und Datenfluss](#aufbau-und-datenfluss)
- [Verhaltensregeln für Implementierungen](#verhaltensregeln-für-implementierungen)
- [Dokumentation und Änderungen](#dokumentation-und-änderungen)
- [Identität und Datenverarbeitung](#identität-und-datenverarbeitung)
- [Validierung von Aktionen](#validierung-von-aktionen)
- [Vorgemerkte Ideen](#vorgemerkte-ideen)
- [Dateibestand und lokale Archive](#dateibestand-und-lokale-archive)

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

Im Projektverzeichnis unter Linux/WSL mit Python ab 3.14.2:

```sh
uv sync --locked --group dev
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest --cov=custom_components.enigma2_connect --cov-report=term-missing
uv run --locked python -m compileall -q custom_components tests
node --test tests/frontend.test.cjs
git diff --check
```

`pyproject.toml` enthält die direkten Entwicklungsabhängigkeiten, `uv.lock` fixiert
deren Auflösung. Nach einer Versionsänderung `uv lock --offline` ausführen und
prüfen, dass nur die erwarteten Projektmetadaten geändert wurden. Keine
Abhängigkeiten nebenbei aktualisieren. Eine frische Umgebung benötigt beim
ersten Synchronisieren Zugriff auf die Paketquellen.

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

## Home-Assistant-Entwicklerblog überwachen

Der Workflow [Home Assistant developer blog](../.github/workflows/ha-developer-blog.yml)
prüft **montags um 07:23 UTC** die vollständigen Beiträge im offiziellen
[Blog-Repository](https://github.com/home-assistant/developers.home-assistant/tree/master/blog).
Er berücksichtigt neue und inhaltlich geänderte Beiträge ab **2026-09-01**.
Pro Lauf werden höchstens **fünf Beiträge gemeinsam in einer Gemini-Anfrage**
bewertet. Ohne neue Beiträge erfolgt kein KI-Aufruf. Weitere Beiträge bleiben
für den nächsten Lauf offen; Quelltexte werden nicht stillschweigend gekürzt.

Das [Gemini-Prüfskript](../scripts/ha_blog_gemini.py) verwendet die Google-API
direkt mit `gemini-3.8-flash`. Eine feste Anfrage vermeidet variable Agentenschleifen.
Es gibt keine Werkzeuge, Websuche, automatische Wiederholung oder Umschaltung auf
andere Modelle. Die Grenzen sind 400.000 UTF-8-Eingabebytes und 8.192 Ausgabetokens
einschließlich Denktokens bei Denkstufe `low`. Bei zu großer Eingabe verkleinert
das Skript die Beitragsgruppe. Passt schon ein Beitrag mit dem vollständigen
Code nicht hinein, schlägt der Lauf fehl und verlangt eine manuelle Prüfung.

An Google gehen die Blogtexte und eine feste Auswahl veröffentlichbarer Quellen:
Python-Module der Integration, Manifest, Übersetzungen, Icons, Qualitätscheckliste, Aktionsdefinitionen,
Dashboardkarte sowie Projekt- und HACS-Metadaten. Lokale Archive, `.env`, Receiverdaten
und Testdaten gehören nicht dazu. Jeder neue Beitrag wird analysiert; der frühere
Schlagwortfilter entscheidet nicht über die Auswahl. Das bisherige
[heuristische Skript](../scripts/ha_blog_monitor.py) bleibt als unabhängige lokale
Prüfmöglichkeit verfügbar, wird aber nicht als stille Ersatz-KI verwendet.

Jeder Beitrag erhält zwei unabhängige Bewertungen. Zur Kompatibilität sind die
Ergebnisse `impacted` (konkreter Anpassungsbedarf), `no-impact` (keine
Auswirkung erkennbar) oder `uncertain` (manuelle Klärung erforderlich). Sie enthalten
Begründung, nächste Schritte, HA-Version/Frist soweit angegeben und Code-Verweise.
Dateien, Zeilennummern und wörtliche Quellzeilen werden lokal validiert. Das bestätigt
die Fundstelle, nicht die Schlussfolgerung der KI. Der gesamte Stapel muss gültig
und vollständig sein, bevor ein Issue entsteht. Eine KI-Einschätzung ersetzt keine
Home-Assistant-Kompatibilitätsprüfung.

Zusätzlich prüft Gemini **Ergänzungen und Verbesserungen**: neue Funktionen,
Bedienkomfort, Leistung, Zuverlässigkeit und Wartbarkeit. Das Feld `opportunity`
enthält `recommended` (konkrete Empfehlung), `none` (kein sinnvoller Vorschlag)
oder `uncertain` (noch zu prüfen), jeweils mit Nutzen, Umsetzungsschritten,
Voraussetzungen und möglichen Nachteilen. Empfehlungen benötigen eine überprüfte
Code-Fundstelle als Ansatzpunkt; die neue API muss noch nicht verwendet werden.
Ein `no-impact`-Beitrag kann somit trotzdem eine Verbesserung empfehlen; auch
Anpassungsbedarf und optionale Ergänzung können gemeinsam auftreten. Bereits
umgesetzte Funktionen und reine Pflichtmigrationen gelten nicht als Ergänzung.
Fehlt eine der beiden Bewertungen oder ein erforderlicher Beleg, entsteht kein
Berichts-Issue. Beide Bewertungen erfolgen in derselben wöchentlichen Anfrage.
Der Bericht schlägt Änderungen vor; die Umsetzung wird separat entschieden.

Pro erfolgreichem Lauf mit neuen Beiträgen entsteht **ein zusammengefasstes
Berichts-Issue**, auch wenn alle Beiträge als `no-impact` bewertet wurden. Seine
unsichtbaren Marker speichern die geprüften Beitragsinhalte dauerhaft. Geschlossene
Berichte zählen ebenfalls; sie werden nicht verändert oder erneut geöffnet.
Berichte und Marker daher erhalten. Inhaltliche Änderungen erzeugen einen neuen
Prüfbedarf, reine Änderungen am Integrationscode nicht. Die früheren heuristischen
Issues gelten nicht als KI-Prüfnachweis. Zusammenfassung und JSON-Berichte liegen
zusätzlich 30 Tage als Actions-Artefakt vor.

### Kostenlosen Google-Zugang einrichten

1. In [Google AI Studio](https://aistudio.google.com/api-keys) einen Schlüssel für
   ein eigenes Projekt im **Free Tier ohne aktivierte kostenpflichtige Abrechnung**
   erstellen. Kein Billing-Konto verknüpfen und kein Paid-Tier-Upgrade aktivieren.
2. Die aktiven Modelllimits in AI Studio prüfen. Google nennt auf der
   [Preisseite](https://ai.google.dev/gemini-api/docs/pricing?hl=de#free) kostenlose
   Ein- und Ausgabe für Gemini 3.8 Flash; konkrete Anfrage-/Tokenlimits sind
   [projektabhängig](https://ai.google.dev/gemini-api/docs/rate-limits).
   Eine kleine Anfrage pro Woche dürfte ausreichen, kann ohne echten Probelauf
   mit dem Projekt aber nicht garantiert werden. Der Free Tier schützt vor
   kostenpflichtiger Nutzung; der Workflow kann den Billing-Status eines Schlüssels
   nicht selbst prüfen. Ein Schlüssel aus einem Paid-Tier-Projekt kann Kosten verursachen.
3. Im GitHub-Repository unter **Settings → Secrets and variables → Actions →
   New repository secret** den Schlüssel als **GEMINI_API_KEY** speichern.
   Den Schlüssel nicht in Dateien, Issues oder Chats eintragen.
4. Nach freigegebener Übernahme des Workflows per PR nach `main` unter **Actions →
   Home Assistant developer blog → Run workflow** den Standardbranch auswählen.
   **Run Gemini and generate a report; do not create an issue** für den ersten
   Probelauf aktiviert lassen. Dieser Probelauf nutzt das KI-Kontingent, speichert
   aber keine dauerhaften Prüfmarker. Bericht und `usage` im JSON kontrollieren.
5. Für manuelle Issue-Veröffentlichung den Probelauf-Schalter deaktivieren.
   Geplante Wochenläufe veröffentlichen den zusammengefassten Bericht automatisch.

Gemini verarbeitet diese Quellen nach den Google-Bedingungen für den Free Tier;
die [Preisseite](https://ai.google.dev/gemini-api/docs/pricing?hl=de#free) verweist
auf die Bedingungen zur Verwendung von Inhalten zur Produktverbesserung.
Nur für diese Weitergabe geeignete Repository-Inhalte verwenden.

Bei HTTP 429, anderen API-Fehlern, fehlendem Schlüssel oder ungültiger Antwort
schlägt der Lauf sichtbar fehl. Ohne gespeicherten Bericht bleiben die Beiträge
für den nächsten Lauf offen; es gibt keinen automatischen Paid-Fallback. Bei
unklarem Ausgang einer Issue-Veröffentlichung findet der nächste Lauf einen
eventuell bereits gespeicherten Bericht anhand der Marker.

Der schreibende Job läuft ausschließlich im ursprünglichen Repository auf dem
Standardbranch. Pushes und Pull Requests führen nur Offline-Tests aus, Forks
veröffentlichen keine Berichte. Berechtigungen: `contents: read`, `issues: write`;
GitHub Actions und Issues müssen aktiviert sein. Parallele Läufe werden serialisiert.
GitHub kann Zeitpläne verzögern und deaktiviert geplante Workflows öffentlicher
Repositories nach 60 Tagen ohne Repository-Aktivität
([GitHub-Zeitpläne](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)).

Lokale Vorbereitung ohne Google-Aufruf und ohne GitHub-Schreibzugriff:

```sh
python -m unittest discover -s scripts/tests -v
python scripts/ha_blog_gemini.py --blog-dir /path/to/developers.home-assistant/blog --prepare-only
```

Ohne `--prepare-only` ist `GEMINI_API_KEY` erforderlich und ein echter KI-Aufruf
möglich. GitHub-Schreibzugriffe erfordern zusätzlich ausdrücklich `--publish`.


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
  die Aufnahme gehört; eine aufgelöste Aufnahme ist kein Browser-/Cast-Stream.
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
Browser-/Cast-Streaming, Wake-on-LAN, automatische Receiver-Erkennung und neue
wiederkehrende Timer gehören ebenfalls nicht zum aktuellen Umfang.

## Validierung von Aktionen

Aktionsnamen und Anwendungsbeispiele stehen im
[Benutzerhandbuch](BENUTZERHANDBUCH.md#aktionen-und-beispiele).

Eigene Geräteaktionen haben kein implizites Standardgerät. Ihre Validierung
steht in `services.py` und `services.yaml`. Die Notify-Entität verwendet die
Nachrichtenoptionen des Receivers; `enigma2_connect.message` verwendet dagegen
eigene Aktionswerte (Standard: Typ 1, Dauer 10 Sekunden).

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

| Priorität | Idee | Nutzen, Schnittstelle und Grenzen |
| --- | --- | --- |
| Hoch | EPG durchsuchen und direkt aufnehmen | Sendungen nach Titel finden, Wiederholungstermine suchen und Treffer ohne manuelle Zeitangaben aufnehmen. Grundlage: `epgsearch`, `epgsimilar`, `timeraddbyeventid`. Die laufende/nächste Sendung wird bereits angezeigt; ergänzt würden Suche und Aufnahme aus einem Treffer. [EPG-API][ideas-api] |
| Hoch | Timer bearbeiten und Wochenserien anlegen | Vorhandene Timer verlängern, Wochentage, Aufnahmeordner und Tags festlegen. Anlegen, Löschen, Aktivieren/Deaktivieren und lesende Kalenderwiederholungen sind vorhanden. Ergänzung über `timerchange` und `repeated`; einzelne Kalenderinstanzen nicht mit dem gesamten Receiver-Timer verwechseln. [Timerimplementierung][ideas-timers] |
| Hoch | Aufnahmekonflikte gezielt auswerten | Kollidierende Sendungen mit Zeiten anzeigen und Automationen zugänglich machen. Beim Anlegen/Bearbeiten liefert OpenWebif strukturierte `conflicts`. Das wäre eine Erweiterung der bisherigen Fehlerauswertung, keine belegte separate Konfliktvorhersage. [Timerimplementierung][ideas-timers] |
| Hoch | Sofortaufnahme als eigene Aktion | Dashboard-Button oder Sprachaktion „Aktuelle Sendung aufnehmen“ über `recordnow`. Der Ereignismodus benötigt EPG; der alternativ „unendlich“ genannte Modus ist im untersuchten Code auf zehn Stunden begrenzt. [Timerimplementierung][ideas-timers] |
| Hoch | Aufnahmebibliothek erweitern | Aufnahmeordner und HA-Medienquelle sind inzwischen vorhanden. Weitere Ausbaustufen: Tags/Filter, zusätzliche Metadaten wie Dateigröße und bisheriger Wiedergabefortschritt sowie Umbenennen, Verschieben und Löschen. OpenWebif bietet `movielist`, `fullmovielist` und Verwaltungsaktionen. Lösch-/Papierkorbverhalten je Image berücksichtigen. [Aufnahmeverwaltung][ideas-movies] |
| Mittel | Festplattenspeicher und Systemdiagnose | Freien Aufnahmeplatz überwachen; RAM und Uptime als optionale Diagnosesensoren ergänzen. `about` liefert die Grundlagen. Einheiten normalisieren und langsam abfragen; als frei gemeldeter RAM enthält im untersuchten Code auch Buffer und Cache. [Informationsmodell][ideas-info] |
| Mittel | Tonspur auswählen | Originalton, alternative Sprache oder Audiodeskription per dynamischer `select`-Entität wählen. Grundlage: `getaudiotracks` und `selectaudiotrack`; Auswahl nach Senderwechsel aktualisieren. [Audio-API][ideas-api] |
| Mittel | Timeshift gezielt steuern und anzeigen | Start-/Stopp-Aktionen und „Timeshift aktiv“ über `tsstart`, `tsstop`, `tsstate`. `timeshiftEnabled` ist kein verlässlicher Pausezustand; der untersuchte Stopp-Pfad unterdrückt die Speicherrückfrage. [Controller][ideas-controller] |
| Mittel | Wiedergabeposition bei Aufnahmen | Fortschritt und Restzeit im Medienplayer anzeigen. Das bereits abgefragte `getcurrent` liefert für bestimmte lokale Aufnahmen eine Position in Sekunden. Diese allein erlaubt keine sichere Pauseerkennung. [Controller][ideas-controller] |
| Mittel | Receiver-Sleeptimer | „In 30 Minuten Standby“ mit Statusanzeige über den geräteeigenen `sleeptimer`. Verfügbare Felder und Verhalten unterscheiden sich nach Image. [Timerimplementierung][ideas-timers] |
| Optional | Einschalten ohne Mitwecken des Fernsehers | Für Radio oder Hintergrundautomationen: `supports_powerup_without_waking_tv` und `set_powerup_without_waking_tv` sind dokumentiert. Image-Unterstützung prüfen; die Funktion ersetzt kein Aufwecken aus Tiefschlaf. [Steuerungs-API][ideas-api] |
| Optional | Text an Eingabefelder senden | Suchbegriffe direkt eingeben, statt einzelne Fernbedienungstasten zu senden. `remotecontrol` besitzt einen `text`-Parameter; das aktive Eingabefeld am Receiver bleibt entscheidend. [Controller][ideas-controller] |
| Größeres Projekt | Live-TV und Aufnahmen auf anderen Geräten abspielen | Die vorhandene Aufnahme-Medienquelle um verifizierte Browser-/Cast-Wiedergabe und Live-TV erweitern. OpenWebif bietet Stream-/Playlist-Endpunkte einschließlich eines HLS-Einstiegs. Codec-Unterstützung, Authentifizierung und gegebenenfalls Transcoding separat lösen; ein API-Endpunkt belegt keine funktionierende Wiedergabe auf jedem Zielgerät. [Streaming-Endpunkte][ideas-controller] |

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
