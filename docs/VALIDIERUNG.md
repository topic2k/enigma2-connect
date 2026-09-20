[Deutsch](VALIDIERUNG.md) | [English](VALIDATION.en.md)

# Prüfübersicht

## Aufnahme-Workflows: 1.3.0-dev.3, Abschnitt 1b

Stand **20.09.2026**. Datenmodelle, optionale Antworten bestehender Timeraktionen
und Schutz vor automatischer Wiederholung unklarer Timerbefehle implementiert.
Plan und Grenzen in [ENTWICKLUNG.md](ENTWICKLUNG.md#abschnitt-1b-datenmodelle-aktionsantworten-und-unklare-ergebnisse),
Praxisschritte im [Benutzerhandbuch](BENUTZERHANDBUCH.md#abschnitt-1b-auf-dem-receiver-prüfen).

**Lokale Prüfung bestanden:** Python **3.14.7**, Home Assistant **2026.9.1**,
pytest-homeassistant-custom-component **0.13.364**. **201 unterschiedliche
Tests** sind im jeweils letzten Lauf bestanden. Der erste Lauf hatte 186
bestandene Fälle; sechs lokale HTTP-Fälle scheiterten an der fehlenden
`socket_enabled`-Fixture, einschließlich ihrer Folgefehler beim Aufräumen.
Nach Korrektur der Testeinrichtung bestanden alle 40 Fälle des gezielten
Nachlaufs (Workflow-Aktionen und betroffene Kanalkataloge), einschließlich
eines zusätzlichen Tests für fehlschlagendes Nachlesen. Produktionscode musste
für diese Testkorrektur nicht geändert werden.

Umfang: `test_workflow_models`, `test_workflow_actions`, `test_api`,
`test_integration`, `test_silver_controls`, `test_translations`, `test_models`,
`test_gold_lifecycle`, `test_regressions`, `test_channel_media`. Echte lokale
aiohttp-Verbindungen mit simuliertem Receiver belegen genau einen Schreibaufruf
bei verlorener Antwort für alle sechs geschützten Timerendpunkte, einschließlich
anschließender Erreichbarkeit. HA-Tests prüfen optionale Antworten, bisherige
Aufrufe, übersetzte Fehler, Reauth, Abbruch und Listenabgleich bei Fehlern.
Modelltests unterscheiden leere/unbekannte/ungültige Daten und erhalten Kennungen.

Kombinierte Statement-/Branch-Coverage der betroffenen Module: `api.py`
**96,99 %**, `coordinator.py` **99,38 %**, `services.py` **97,50 %** und
`workflow_models.py` **100 %**. Alle liegen über der unveränderten 95-%-Grenze.
Ruff, Formatierung, Syntax und mypy strict für alle **29** Produktionsmodule
bestanden; Versionskonsistenz, lokale Dokumentationslinkziele und
`uv lock --check --offline` ebenfalls. Die Lockdatei ändert nur die Projektversion.
Berichte im ursprünglichen Arbeitsverzeichnis `V:\enigma2-connect` unter
`.work/recording-workflows-checks/`: `section1b-tests.xml`,
`section1b-recheck.xml`, zugehörige `.log`-Dateien und `section1b-coverage.json`.
Die Coverage vereinigt beide Läufe bei unverändertem Produktionscode.

Betroffene Qualitätsregeln geprüft: `action-setup`, `action-exceptions`,
`common-modules`, `parallel-updates`, `test-coverage`, `strict-typing`,
`exception-translations`, `docs-actions`, `docs-data-update`,
`docs-known-limitations`. Keine Statusabsenkung oder neue Ausnahme.
Unveränderte Module behalten ihre bisherigen Nachweise; kein vollständiger
neuer CI-Lauf und keine neue offizielle HA-Qualitätsstufe behauptet.

**Praxisabnahme bestanden:** Am **20.09.2026** bestätigt der Nutzer alle
Prüfschritte der Anleitung für **1.3.0-dev.3** auf den beiden angefragten
Testreceivern: Octagon SF8008 4K Supreme / OpenATV / OpenWebif 2.4.0 und
Vu+ Solo² / VTi / OpenWebif 1.4.4. Dazu gehören Anlegen, Deaktivieren,
Aktivieren und Löschen mit Antwortdaten, automatische Leerzeichenbereinigung,
die erwartete Ablehnung einer erneuten Löschung, die anschließende Nachricht
sowie bisherige Aufrufe ohne Antwortvariable. Die Bedienfolge überschneidet
sich mit 1a; die genannten Antwort- und Eingabeeigenschaften sind die neuen
Prüfpunkte. Eine neue HA-Version oder einzelne Antwortprotokolle wurden
nicht mitgeteilt. Antwortverlust und Wiederholungsschutz sind ausschließlich
durch die lokalen HTTP-Tests belegt; vollständige EPG-/Aufnahmeformate und
Konfliktverhalten je Image bleiben Gegenstand der Folgeabschnitte.
Nutzer und Codex bestätigen Abschnitt **1b** als fertig. Zugeordneter
Abschlusscommit: `feat: add recording workflow foundations`.
Kein Merge und kein Release.

## Vu+-Timerkennung und Eingabekorrektur: 1.3.0-dev.2

Nutzerbericht vom **20.09.2026**, getesteter Laufzeitstand **1.3.0-dev.1**:
**Vu+ Solo²**, **VTi-Team Image 15.0.0 (2025-06-23-vti-master (4ef8eb3a9))**,
**OpenWebif 1.4.4**. Nachricht und Timer anlegen bestanden. Aktivieren/Deaktivieren
und das erste Löschen meldeten „Die Receiver-Anfrage ist fehlgeschlagen oder
wurde abgelehnt.“ Erneutes Löschen meldete denselben Fehler; mangels bestätigter
vorheriger Löschung ist dies **kein bestandener Ablehnungstest**. Die Nachricht
nach der Ablehnung funktionierte; keine weiteren Auffälligkeiten gemeldet.

Der erste Timerdurchlauf war **nicht bestanden**. Der anschließende Vergleich
der Nutzerangaben belegt eine abweichende Timerkennung im Aufruf:

- `timer_toggle` enthält ein führendes Leerzeichen vor
  `1:0:19:283D:3FB:1:C00000:0:0:0:`, der gespeicherte Timer keines.
- Die angefragten Zeiten 20.09.2026, 12:00–12:02 mit Offset `+02:00` entsprechen
  exakt den gespeicherten Werten `begin=1789898400`, `end=1789898520`.
- Der Timer ist laut Nutzer noch vorhanden; gemeldet sind `justplay=1`,
  `disabled=0`, `state=0`.

Der bisherige Code übergibt die abweichende Kennung unverändert als `sRef`.
**Nutzer-Gegencheck am 20.09.2026 bestanden:** Nach manuellem Entfernen des
Leerzeichens funktionieren Deaktivieren, Aktivieren und Löschen des Timers.
Damit ist die abweichende Eingabe als Ursache bestätigt; aus diesem Befund ergibt
sich keine VTi-/OpenWebif-Inkompatibilität. Dieser Gegencheck betrifft weiterhin
den gemeldeten Stand **1.3.0-dev.1** mit bereinigter Eingabe, nicht die automatische
Bereinigung in dev.2. Erneutes Löschen nach der erfolgreichen Löschung wurde
nicht erneut berichtet. In Abschnitt 1a wurden Timerparameter und Zeitumrechnung
nicht geändert.

**Korrektur in 1.3.0-dev.2:** Das gemeinsame Schema von `timer_add`, `timer_toggle`
und `timer_delete` entfernt äußere Leerzeichen und weist danach leere Kennungen
vor einem Receiver-Aufruf ab. Interne Leerzeichen, Groß-/Kleinschreibung und
Zeitangaben bleiben unverändert. **12 gezielte Tests bestanden** mit dem echten
HA-Testframework und simuliertem Receiver, darunter neun neue parametrisierte
Regressionen für alle drei Aktionen. Umfang: `tests/test_integration.py` mit
`-k 'timer or service_target or actions_registered or action_rejection'`.
Ruff, Formatierung, strenge Typprüfung und Syntaxprüfung bestanden; außerdem
Versions-/Dokumentationskonsistenz und Offline-Lockprüfung. Keine vollständige
neue Coverage-Messung und keine Absenkung bestehender Prüfgrenzen.
Prüfberichte: `.work/recording-workflows-checks/timer-tests.xml` und
`timer-tests.log` im ursprünglichen Arbeitsverzeichnis `V:\enigma2-connect`.

**Praxisstatus:** Vu+-Timeraktionen mit bereinigter Eingabe sind nutzerbestätigt;
die automatische Bereinigung in dev.2 ist durch die lokalen Regressionen geprüft.
Octagon-Nachweis und Commit `e1dce95` behalten ihren ursprünglichen
Umfang. Betroffen sind `action-exceptions`, `test-coverage`, `strict-typing`,
`docs-actions`, `docs-known-limitations` und `docs-supported-devices`.
Die Nachbesserung wurde am 20.09.2026 von Nutzer und Codex als fertig bestätigt.
Zugeordneter Abschlusscommit: `fix: trim whitespace in timer service references`.
Keine neue CI oder Abnahme anderer Geräte/Funktionen behauptet.

## Aufnahme-Workflows: 1.3.0-dev.1, Abschnitt 1a

Stand **19.09.2026**, Basis `origin/main` auf `1afa705`. Plan in der
[Entwicklerdokumentation](ENTWICKLUNG.md#umsetzungsplan-aufnahme-workflows).
Strukturierte API-Ergebnisse und interne Ablehnungsdetails implementiert.
Gezielte Prüfung mit Python **3.14.7**, Home Assistant **2026.9.1** und
`pytest-homeassistant-custom-component 0.13.364`: **88 Tests bestanden**,
keine Fehler oder übersprungenen Tests. Umfang: `test_api.py`,
`test_integration.py`, `test_regressions.py`, `test_silver_controls.py`.
Das geänderte Modul `api.py` erreicht **96,35 % kombinierte Anweisungs-/
Zweigabdeckung**; dies ist keine neue Abdeckungsmessung der gesamten Integration.
Transport und Receiver sind simuliert, die HA-Regressionstests verwenden das
echte Framework. Geprüft: erfolgreiche/abgelehnte Rückgaben, alter Rückgabevertrag,
gemeinsame Befehlssperre, Abbruch/Transportfehler und übersetzte HA-Fehler ohne
rohe Metadaten in Fehlermeldungen oder Logs.

Ruff, Formatierung, strenge mypy-Prüfung der Integration und Syntaxprüfung der
drei geänderten Python-Dateien bestanden. `uv lock --offline` sowie
`uv lock --check --offline` bestanden; ausschließlich die lokale Projektversion
änderte sich in der Lockdatei. Versionsstellen und lokale Dokumentationslinkziele
geprüft. Lokaler Lauf gegen den Worktree; JUnit- und API-Coverage-Bericht liegen
unter `V:\enigma2-connect\.work\recording-workflows-checks`.
**Praxisnachweis aus Nutzerbericht vom 20.09.2026:** Octagon SF8008 4K Supreme,
OpenATV **7.6.0.20260831 (2026-08-30)**, OpenWebif **2.4.0**, Teststand
**1.3.0-dev.1**. Bildschirmnachricht, Timer anlegen, deaktivieren/aktivieren
und löschen jeweils **OK**. Erneutes Löschen des entfernten Testtimers meldete
wie erwartet: „Die Receiver-Anfrage ist fehlgeschlagen oder wurde abgelehnt.“
Die anschließend gesendete Bildschirmnachricht funktionierte ebenfalls;
keine weiteren Auffälligkeiten gemeldet. Dies ist ein vom Nutzer durchgeführter
Test über Home Assistant mit einem echten Receiver, getrennt von den Simulationen
oben. Die HA-Version der Nutzerinstallation wurde nicht mitgeteilt.

Der Nachweis bestätigt die bestehenden Bedienabläufe, die sichtbare Ablehnung
und die Weiterbenutzung danach auf diesem Gerät/Image. Interne strukturierte
Antwortdaten, Parallelität und Abbruch sind weiterhin nur automatisiert geprüft.
Keine neuen Receiver-Aktionen oder aktuelle CI für diesen Arbeitsstand.
Die Abnahme erweitert sich nicht auf andere Receiver, Images oder Abschnitte.

Betroffene Qualitätskriterien: `action-exceptions`, `parallel-updates`,
`test-coverage`, `strict-typing`. Bestehende übersetzte HA-Fehler und Serialisierung
bleiben erhalten; Testgrenzen werden nicht abgesenkt. Rückgabedetails sind intern
und dürfen nicht vollständig in Logs oder Diagnosen gelangen. Die übrige
Grundlage und Feature-Abschnitte 2–5 sind offen. Abschnitt **1a** ist mit der
vorherigen Codex-Bestätigung und der vollständigen OK-Rückmeldung des Nutzers
am 20.09.2026 beidseitig abgeschlossen. Die Praxisdokumentation vervollständigt
denselben Abschnitt und behält dessen geprüfte Version **1.3.0-dev.1** bei;
Laufzeitcode und Tests bleiben gegenüber dem erfolgreichen lokalen Lauf unverändert.
Dokumentationslinks, Versionskonsistenz und `git diff --check` beim Abschluss
erneut prüfen; kein Anlass für einen erneuten vollständigen Testlauf.
Frühere Nachweise unten gelten nur für ihre Stände.

## Veröffentlichung 1.2.0

Am **16.09.2026** ausdrücklich zur Veröffentlichung beauftragt. Die Release-Pflege
ändert nur die beiden Changelogs und Prüfübersichten. Integrationscode, Tests,
Abhängigkeiten, Qualitätscheckliste und Prüfgrenzen bleiben gegenüber `97ebd0f`
unverändert. Dessen [PR-Tests](https://github.com/topic2k/enigma2-connect/actions/runs/35136701709),
[Hassfest/HACS](https://github.com/topic2k/enigma2-connect/actions/runs/35136701707)
und CodeQL sind erfolgreich. Nach dieser Dokumentationsänderung werden die
aktuellen PR-Prüfungen und nach dem Merge die Prüfungen des tatsächlichen
Release-Commits vor Tag und Veröffentlichung erneut kontrolliert; die endgültigen
CI-Links werden im [Release 1.2.0](https://github.com/topic2k/enigma2-connect/releases/tag/v1.2.0)
festgehalten.

Die Hardware-Nachweise behalten ihren dokumentierten Umfang. Reale HA-Aufnahme-
wiedergabe und wiederholte Sprünge sind durch Nutzerprüfung und Log belegt;
Cast, Dauerlauf, reale parallele Zuschauer und die übrigen genannten Praxisgrenzen
bleiben offen. Diese Veröffentlichung erweitert keine Geräteabnahme.

## PR-Vorbereitung: 1.2.0

Am **16.09.2026** Remote-Branches, Tags und veröffentlichte Releases abgeglichen:
`main` steht auf `271444a` (1.1.3), das letzte stabile Release ist `v1.1.0`.
Die rückwärtskompatible Streaming-Erweiterung ergibt die Zielversion **1.2.0**;
Manifest, Projektmetadaten, Lockdatei und beide Changelogs verwenden diese
Versionskennung ohne Entwicklungssuffix. Die Version bleibt unveröffentlicht.

Offene lokale Dokumentationsänderungen sind mit `develop` zusammengeführt.
Aktuelle Streaming-Beschreibung, nummerierte Ideenliste, Branding und bestehende
CI-Nachweise bleiben erhalten. Die Qualitätsregeln vor der Übernahme nach `main`
sind in beiden Sprachen ergänzt. Integrationscode, Tests, Abdeckungsgrenzen und
Qualitätscheckliste bleiben gegenüber `b1feaae` unverändert.

Der [Testlauf auf `b1feaae`](https://github.com/topic2k/enigma2-connect/actions/runs/35135760298)
und [Hassfest/HACS](https://github.com/topic2k/enigma2-connect/actions/runs/35135760314)
sind erfolgreich. Für den neuen PR-Stand sind vor dem Merge erneut erfolgreiche
CI-Ergebnisse erforderlich. Die dokumentierten Receiver-/HA-Nutzerprüfungen
behalten ihren jeweiligen Umfang; Cast, Dauerlauf, reale parallele Zuschauer
und weitere dort genannte Praxisgrenzen sind damit nicht zusätzlich abgenommen.
Der Coverage-Datenbranch wird erst nach erfolgreichem `main`-Testlauf veröffentlicht.

Lokale Abschlussprüfung bestanden: 122 lokale Dateiverweise, 56 Python-Syntaxprüfungen, Versionskonsistenz, erhaltene Changelog-Historie und unveränderte Abhängigkeiten. `uv lock --offline`, `uv lock --check --offline` und `git diff --check` bestanden.

## CI-Spultest: Korrektur 1.2.0-dev.10

Der [CI-Lauf zu dev.9](https://github.com/topic2k/enigma2-connect/actions/runs/35132768651)
bestand 413 Tests; zwei Varianten des HLS-Farbtests scheiterten mit FFmpeg 6.1.1.
Die einzelnen Segmente enthielten die erwarteten Farben. Der relative Sprung
um 12,8 Sekunden lag durch den AAC-Vorlauf vor dem gewünschten Videobild:
Containerstart 0,978667, Videostart 1,000000 Sekunden. Die korrigierte Prüfung
verwendet die absolute Videozeit 13,8 Sekunden und kontrolliert zusätzlich jeden
Segmentstart auf einen 90-kHz-Tick genau. Keine gelockerten Farbprüfungen,
Überspringungen, abgesenkten Abdeckungsgrenzen oder Änderungen am Integrationscode.
Die Qualitätscheckliste bleibt unverändert. Der [Korrekturlauf](https://github.com/topic2k/enigma2-connect/actions/runs/35134405193)
mit FFmpeg 6.1.1 besteht sämtliche Python- und Frontend-Tests, die unveränderten
Abdeckungsgrenzen, Ruff, Formatierung und mypy. [Hassfest und HACS](https://github.com/topic2k/enigma2-connect/actions/runs/35134405186)
sind ebenfalls grün. Beide betroffenen Tests bestanden zusätzlich lokal mit
FFmpeg 8.1; Python-Syntax und Offline-Lockprüfung bestanden. Der dokumentierte
HA-Praxistest bleibt erhalten; die Testkorrektur enthält keine neue Geräteabnahme.

## HA-Aufnahmewiedergabe und Sprünge: Nutzerabnahme 1.2.0-dev.9

Am **16.09.2026** hat der Nutzer eine Aufnahme im realen Home Assistant gestreamt,
mehrfach vor- und zurückgesprungen und das Feature vorbehaltlich unauffälliger
Logprüfung zur Übernahme nach `develop` freigegeben. Der geprüfte Ausschnitt
19:57:48–19:58:21 enthält keine Streamingfehler, keine Remux-Rückfälle und keine
Enigma2-Connect-Warnungen. Die allgemeine HA-Warnung zu Custom-Integrationen
beim Start ist kein Streamingfehler; der ESPHome-Traceback beim Umschalten des
Loglevels betrifft eine nicht verbundene ESPHome-Fernbedienung.

Belegt: automatischer Aufnahme-Modus; H.264 High 1280 × 720 bei 50 fps unverändert
übernommen; MP2 Stereo 48 kHz/256 kbit/s zu AAC Stereo 48 kHz/128 kbit/s umgewandelt;
Ausgabe HLS/MPEG-TS mit einer Qualitätsstufe. Vom Startauftrag bis `Started`
vergehen 3,949 Sekunden. 14 Remux-Aufträge umfassen Sprünge auf 580,980 Sekunden
(9:41), 1705,600 (28:26), 2029,840 (33:50) und zurück auf 957,920 (15:58), gefolgt
von jeweils weiteren Abschnitten. Unterschiedliche Segmentdauern um 6,6–7,1
Sekunden entsprechen den vorhandenen Schlüsselbildern. Der Pool meldet zwei
belegte Plätze bei konfigurierter Grenze vier; das ist kein Beleg für zwei
gleichzeitig aktiv schauende Personen. Alle protokollierten Koordinatorabrufe
enden erfolgreich, einer dauert 5,234 Sekunden.

Der konkrete Browser und dessen Version sind nicht angegeben. Diese Abnahme
ersetzt keine gesonderte Cast-, Dauerlauf-, Ablauf-/Aufräum- oder subjektive
Bild-/Tonsynchronitätsprüfung. Der Ausschnitt endet während laufender Wiedergabe.
Das Feature gilt für den vom Nutzer geprüften Umfang vorerst als abgeschlossen.

Beleg: lokal bereitgestelltes `home-assistant_enigma2_connect_2026-09-16T17-58-29.053Z.log`,
SHA-256 `e6960bfa8ad13e4fa744ca61f6c305175ca27c9280f7d9362ce3b3da80015d0a`. Das vollständige HA-Log bleibt wegen der enthaltenen
projektfremden Betriebsdaten außerhalb des Repositorys.
Diese Abnahme ändert keinen Python- oder Testcode; SHA-256-Abgleich mit dem
bestandenen dev.8-Nachweis bestätigt den Stand. Für die Übernahme werden nur
Dokumentation, Versionskonsistenz und die Zusammenführung mit `develop` geprüft;
die ausführlichen Streamingtests sind unten dokumentiert. Aktuelle CI und der
Qualitätsabgleich bleiben vor einer späteren Übernahme nach `main` erforderlich.

## Originalspuren und spulbares Remux: 1.2.0-dev.8

Geprüft am **15.09.2026**, Python 3.14.7 / HA 2026.9.1 / FFmpeg 8.1.
Im größeren Streaminglauf bestanden **158 von 160 Tests**; zwei Medientests
überschritten unter paralleler Prüf-/Receiverlast ihre Zeitgrenzen. Die gezielte
MP2-Wiederholung bestand. Nach abschließender Sicherung kurzer Originalvideo-
Schlussabschnitte bestanden **52 VOD-/Remux-Tests** ohne parallele Last mit
lokal kopiertem FFmpeg. Diese Gruppe enthält beide betroffenen Fälle und
überschneidet sich mit dem breiten Lauf. Die übrigen 110 Streamingtests bestanden
im breiten Lauf; dessen unveränderte Module sind per SHA-256 abgeglichen.

Die Medientests vergleichen SHA-256-Prüfsummen aller ursprünglichen H.264-Pakete
mit den remuxten Abschnitten: Video und 50 fps bleiben erhalten. Bei AAC werden
auch Audio-Pakete verglichen; MP2 wird zu AAC umgewandelt. Vor-/Rücksprünge,
vollständige HLS-Decodierung, kurze Schlussabschnitte, Indexgrenzen, veraltete/
inkonsistente Indizes, FFmpeg-Funktionsausfall, Kompatibilitätsmodus und die
32-MiB-Gesamtgrenze sind abgedeckt. FFmpeg 8.1 deckte zuvor ein zusätzliches AAC-
Ausgabepaket im alten VOD-Encoder auf; eine Paketbegrenzung korrigiert dies.

**Echter Receiver:** Die freigegebene Aufnahme „Böhmi brutzelt“ am SF8008 liefert
HTTP-Byte-Ranges und einen 55.696-Byte-Index mit 3.481 Einträgen. Erkannt wurden
H.264 High, 1280 × 720, 50 fps und MP2 als erste Tonspur. Vier kurze Abschnitte
am Anfang/in der Mitte sowie ein echter FFmpeg-HLS-Sprung auf ca. 18:52 Minuten
decodierten fehlerfrei; Verarbeitung `recording_vod+copy_video+encode_audio`.
Beim verkürzten Lesevorlauf dauerte die Vorbereitung lokal rund 4,2 Sekunden,
neue Abschnitte rund 2,0 Sekunden (Momentaufnahme, keine Geschwindigkeitsgarantie
für den HA-Host). Kein vollständiger Download. Die letzte Dauer-Randkorrektur
ändert diesen Aufnahmefall nicht; sie ist durch den abschließenden Test abgedeckt.
Browseroberfläche, Cast und subjektive Bild-/Tonübergänge auf HA bleiben offen.

Ruff, Formatierung, mypy (**28 Module**), Syntax, Offline-Lockprüfung und lokales
Hassfest bestanden. Alle 28 Module liegen über 95 % kombinierter Statement-/
Branch-Abdeckung (Minimum 96.25 %). Unveränderte Module behalten ihren
geprüften Nachweis, die vier geänderten/neuen Streamingmodule wurden neu gemessen.
Kein neuer Volltest der gesamten Integration und kein Remote-CI-Lauf.
Lokale Belege: `.work/remux-full-tests.log`, `.work/remux-final-tests.log`,
zugehörige `*-inventory.json`, `.work/remux-verified-coverage.json` und
`.work/remux-checks.log`. Receiver-Prüfbeleg im lokalen Werkzeugordner des
Haupt-Checkouts: `.work/remux-receiver-validation.json`. Zugangsdaten sind nicht
Bestandteil der Nachweise oder des Git-Bestands.

## Spulen in Aufnahmen: 1.2.0-dev.7

Geprüft am **14.09.2026**, Python 3.14.7 / HA 2026.9.1. Im breiten Streaminglauf
bestanden **133 Tests**; eine zusätzliche Cache-Testassertion verglich 2.8 exakt
mit 2.8000000000000007 und wurde auf numerische Toleranz korrigiert. Danach
bestanden **25 gezielte VOD-Tests**, einschließlich dieser Prüfung und des neu
ergänzten verkürzten Schlusssegments. Die Gruppen überschneiden sich.
Die Produktivdateien sind in beiden Läufen identisch; SHA-256 bestätigt den Stand.

Ein echtes FFmpeg-Testvideo mit verschiedenen Farbszenen prüft Vor-/Rücksprünge,
einen HLS-Client-Sprung anhand der vollständigen Playlist sowie vollständiges
Decodieren ohne Zeitstempelfehler. Paketmessungen führten zur gemeinsamen
Zeitbasis, begrenztem Dekodiervorlauf und ausgerichteten Bild-/Audioabschnitten.
Frühere Versuche mit zurückgesetzten oder überlappenden Zeitstempeln wurden
verworfen. Weitere Fälle: Byte-Range-Prüfung, ungültige/instabile Laufzeit,
Dateiänderungen, Cache-Verdrängung und erneute Erzeugung, gemeinsamer Abruf,
begrenzte Warteschlange, Abbruch/Prozessende, HA-URLs und parallele Sitzungen.

Ruff, Formatierung, mypy (**27 Module**), Syntax, Offline-Lockprüfung und lokales
Hassfest bestanden. Alle **27 Module liegen über 95 %** kombinierter Statement-/
Branch-Abdeckung (Minimum 96.25 %); unveränderte Module behalten ihren
geprüften Nachweis, die drei VOD-betroffenen Module wurden vollständig neu gemessen.
Qualitätscheckliste geprüft: keine neue Abhängigkeit, Plattform oder abgesenkte
Prüfgrenze. Lokale Belege: `.work/vod-full-tests.log`, `.work/vod-final-tests.log`,
deren `*-inventory.json`, `.work/vod-verified-coverage.json` und `.work/vod-checks.log`.

Receiver und HA-Browseranfragen sind simuliert; FFmpeg verarbeitet echte synthetische
Mediendaten. Kein neuer Volltest/Remote-CI-Lauf. Spulen und subjektive Bild-/Ton-
Übergänge am realen SF8008 mit Firefox, Edge und Cast bleiben praktisch zu prüfen.

## Name der Medienquelle und HLS-Dokumentation: 1.2.0-dev.6

Geprüft am **14.09.2026**: **9 Medienquellen-/Übersetzungstests** bestanden,
einschließlich der HA-Medienkachel, der deutschen/englischen Beschriftung und
der Fallback-Sprache. Ruff, Formatprüfung, mypy (26 Module), Python-Syntax,
Offline-Lockprüfung und lokales Hassfest (Core 2026.9.1) bestanden.
Versionsstellen und lokale Dokumentationslinks stimmen überein.

Die Python-Änderung beschränkt sich auf zwei Fallback-Beschriftungen;
SHA-256-Abgleich nach Rückersetzung dieser Texte bestätigt ansonsten den
identischen Code aus dev.5. Keine geänderte Streaming-/Seek-Logik und keine
neue Plattform oder Abhängigkeit. Der gezielte Lauf ersetzt nicht den früheren
umfassenderen Abdeckungsnachweis. Kein erneuter Volltest oder realer
Receiver-/Browser-Test. Belege: `.work/source-name-tests.log`,
`.work/source-name-inventory.json` und `.work/source-name-checks.log`.

## Streaming-Diagnose: 1.2.0-dev.5

Geprüft am **14.09.2026**: **110 Streaming-/Medienquellen-/Übersetzungstests**
bestanden. Der erste Lauf hatte 109 bestandene Tests und einen fehlgeschlagenen
Aufräumtest: Eine neue Logmeldung prüfte den Ablauf ein zweites Mal. Entscheidung
und Log verwenden jetzt denselben Prüfwert; der vollständige gezielte Lauf wurde
mit dem korrigierten Stand erfolgreich wiederholt.
Neue Prüfungen sichern die Ausgabe erkannter Formate, Zuordnung paralleler Streams,
Pool-Grenze, gemeinsame Wiedergabe, Rückfallgründe sowie den Ausschluss von
Zugangsdaten, URLs und ungefilterten Ausnahme-/Metadaten aus den Diagnosemeldungen.
Ruff, Formatprüfung, Python-Syntax, mypy (26 Module), Offline-Lockprüfung und
lokales Hassfest (Core 2026.9.1, keine ungültige Integration) bestanden.

Alle **26 Python-Module liegen weiterhin über 95 %** kombinierter Statement-/Branch-
Abdeckung (Minimum 96.25 %); Config Flow unverändert bei **100 %**.
Die Messungen für die zwei geänderten Module wurden vollständig ersetzt;
unveränderte Module übernehmen den SHA-256-geprüften Nachweis aus dev.4.
Lokale Belege: `.work/diagnostics-tests.log`, `.work/diagnostics-final-tests.log`,
die zugehörigen `*-inventory.json`, `.work/diagnostics-verified-coverage.json`
und `.work/diagnostics-checks.log`.

Python 3.14.7 / HA 2026.9.1. Receiver-/Browser-Anfragen sind simuliert; vorhandene
Tests mit synthetischen FFmpeg-Medien bleiben enthalten. Kein neuer Volltest,
Remote-CI- oder realer SF8008-/Browser-Abnahmelauf für diesen Stand.
Qualitätscheckliste geprüft: keine neue Plattform/Abhängigkeit und keine
Absenkung der bisherigen Kriterien; reale Geräteabnahme bleibt offen.

## Mehrere externe Streams: 1.2.0-dev.4

Geprüft am **14.09.2026** im bestehenden Feature-Worktree. **104 Streaming-,
Medienquellen- und Übersetzungstests** sowie **64 Einrichtungs-/Optionstests**
bestanden. Die Gruppen überschneiden sich teilweise. Zusätzlich: Ruff,
Formatierung, mypy (26 Module), Python-Syntax, Offline-Lockprüfung,
**8 Frontend-Tests** und lokales Hassfest auf dem Core-Prüfstand **2026.9.1**.

Neue Fälle prüfen zwei weiterlaufende Browser-URLs für unterschiedliche Sender,
fünf gleichzeitig reservierte Plätze und Ablehnung des sechsten Starts ohne
Verdrängung, konfigurierbare Grenzen und 0 = unbegrenzt, gemeinsames Live-TV
(auch während des Starts), getrennte Aufnahme-Wiedergaben, Freigabe abgelaufener
oder fehlgeschlagener Sitzungen sowie Entladen mit ausstehenden Starts.
Der Abbruch eines Zuschauers beendet keinen gemeinsamen Start für einen anderen.
Die bisherigen Codec-/HLS-Tests mit echten synthetischen Videodaten bestehen weiter.

Config Flow erreicht **100 % Statement-/Branch-Abdeckung**; alle **26 Module
liegen über 95 %** (Minimum 96.25 %). Die Abdeckung der zwei geänderten
Python-Module wurde vollständig neu gemessen und ersetzt ihre bisherigen Werte.
Unveränderte Module behalten die vorherige Evidenz; SHA-256-Prüfungen bestätigen
Dateiidentität und Übereinstimmung der geprüften Linux-Kopien mit dem Worktree.
Kein erneuter Volltest/Remote-CI-/HACS-Lauf. Lokale Belege:
`.work/pool-tests.log`, `.work/pool-config-tests.log`, deren `*-inventory.json`,
`.work/pool-verified-coverage.json` und `.work/pool-hassfest.log`.

Python 3.14.7 / HA 2026.9.1. Receiver und Browser-/Cast-HTTP-Anfragen sind simuliert.
Die reale Anzahl gleichzeitig nutzbarer Tuner/Encoder und das Verhalten mehrerer
Browser am SF8008 wurden für diesen Stand noch nicht praktisch geprüft.

## Automatische Stream-Verarbeitung: 1.2.0-dev.3

Geprüft am **14.09.2026** im bestehenden Feature-Worktree. Im vollständigen Lauf
bestanden **340 Python-Tests**; ein neuer Fehlertest scheiterte an seinem
Test-Dummy, dessen `__aexit__` die erwartete Ausnahme verschluckte. Der Dummy wurde
korrigiert. Danach bestanden **89 gezielte Tests**, einschließlich dieses
Falls, der abschließenden HTTPS-Absicherung und des verbesserten ffprobe-Aufräumens.
Diese letzte Prüfung verwendet eine isolierte Kopie der endgültigen Änderungen;
SHA-256-Vergleiche bestätigen die Übereinstimmung mit dem Worktree. Die Messdaten
der beiden danach geänderten Produktionsmodule wurden vollständig durch die neue
Messung ersetzt. Unveränderte Module behalten den geprüften Volltestnachweis.

Alle **26 Integrationsmodule über 95 %** kombinierte Statement-/Branch-Abdeckung
(Minimum 96.25 %); Config Flow erreicht 100 %. Ruff, Formatierung, mypy,
Python-Syntax, Offline-Lockprüfung, **8 Frontend-Tests** und lokales Hassfest
auf dem Core-Prüfstand **2026.9.1** bestanden. Keine Abhängigkeiten geändert.
Remote-CI und HACS wurden nicht neu ausgeführt.

Die Tests prüfen echte synthetische Videodaten: MPEG-2/MP2 mit vollständiger
Umwandlung, H.264/AAC ohne erneute Kodierung, H.264/MP2 mit alleiniger
Tonumwandlung sowie direkte Receiver-HLS-Weitergabe ohne FFmpeg-Encoder.
Codec-Erkennung läuft mit echtem ffprobe; die erzeugten lokalen HLS-Segmente
werden decodiert. Receiver-Endpunkte sind lokale HTTP-Testserver. Zusätzlich
geprüft: fehlende/ungeeignete Receiver-Ausgänge, externe Playlist-Adressen,
Authentifizierung, Größenlimits, Tokenwechsel während eines Abrufs, HTTPS-Erhalt,
Probe-Abbruch und Kompatibilitäts-Rückfall. Python 3.14.7 / HA 2026.9.1.

Lokale Belege: `.work/optimized-full-tests.log`, `.work/optimized-corrected-tests.log`,
die zugehörigen `*-inventory.json`, `.work/optimized-verified-coverage.json` und
`.work/optimized-hassfest.log`. Keine neuen Tests auf dem echten Receiver;
Hardware-Transcoding, Browser-Bild/Ton und CPU-Last des optimierten Weges bleiben
offen. Die Nutzerrückmeldung zu Firefox und Edge gilt für `dev.2`.

## Browser-MIME-Korrektur: 1.2.0-dev.2

Am **14.09.2026** nach der Nutzerrückmeldung zur Meldung „Medientyp nicht
unterstützt“ in Firefox und Edge korrigiert. Home Assistants Medien-Dialog
wählt seinen HLS-Player nur für exakt `application/x-mpegURL`; die bisherige
Integration meldete `application/vnd.apple.mpegurl`. Das scheiterte bereits
bei der Auswahl des Players, unabhängig von der eigentlichen Decodierung.

**39 gezielte Streaming-, Medienquellen- und Übersetzungstests bestanden**,
einschließlich echter synthetischer FFmpeg-Konvertierung. Ein Regressionstest
prüft jetzt die von HA erwartete MIME-Schreibweise ausdrücklich im
Auflösungsergebnis und im HTTP-Header, statt nur dieselbe Konstante zu vergleichen.
Das Streamingmodul erreicht erneut 100 % Statement-/Branch-Abdeckung.
Ruff, Formatierung, mypy (24 Module), Python-Syntax und Offline-Lockprüfung
bestanden; es wurden keine Abhängigkeiten geändert. Kein neuer Volltest/CI-Lauf.
Der frühere Volltestnachweis unten bleibt an `dev.1` gebunden.

Die Tests liefen unter Python 3.14.7 / HA 2026.9.1 mit einer SHA-256-geprüften
Linux-Kopie. Lokale Belege: `.work/browser-mime-tests.log` und
`.work/browser-mime-inventory.json`. Anschließend bestätigte der Nutzer die
Wiedergabe in Firefox und Edge. Ein zweiter gestarteter Stream beendete den ersten
nach dessen Puffer erwartungsgemäß. Das ist eine Nutzerrückmeldung zur bisherigen
vollständigen Umwandlung; Receiver-HLS, optimierte Verarbeitung, Safari und Cast
sind damit nicht praktisch abgenommen.

## Externe Wiedergabe: 1.2.0-dev.1

Geprüft am **14.09.2026**, auf Branch `feature/external-media-playback` im Worktree
`V:\enigma2-connect-worktrees\external-media-playback`. Unveröffentlichte
Entwicklerversion; keine Release-, CI- oder Gerätefreigabe.

- **291 Python-Tests** im vollständigen Lauf bestanden. Nach Ergänzung von
  CORS und HEAD bestanden **35 gezielte Streaming-/Medienquellentests**.
  Die Messdaten des geänderten Streamingmoduls wurden vor dieser Nachprüfung
  verworfen und vollständig neu erhoben; unveränderte Module behalten den Volltestnachweis.
- **100 % Statement-/Branch-Abdeckung** für Config Flow und das neue
  `media_stream.py`; alle **24 Module über 95 %** (Minimum 96.25 %).
  Die vorhandene Silber-Prüfsperre wurde unverändert bestanden.
- Ruff, Formatierung, mypy (24 Module), Python-Syntax und **8 Frontend-Tests**
  bestanden. Lokales Hassfest auf dem vorhandenen Core-Prüfstand **2026.9.1**:
  eine Integration geprüft, keine ungültige Integration. HACS und Remote-CI
  wurden für diesen unveröffentlichten Stand nicht neu ausgeführt.
- Versionen in Manifest, `pyproject.toml`, beiden Changelogs und `uv.lock`
  stimmen überein. `uv lock --offline` und `uv lock --check --offline` bestanden;
  nur die lokale Projektversion änderte sich in der Lockdatei. Lokale Markdown-
  Linkziele und `git diff --check` wurden geprüft.

Laufzeit: **Python 3.14.7, Home Assistant 2026.9.1,
pytest-homeassistant-custom-component 0.13.364** in der vorhandenen WSL-Umgebung.
Receiver und Cast-HTTP-Anfragen sind simuliert. Der FFmpeg-Test erzeugt dagegen
wirklich MPEG-2/MP2-Testmaterial, wandelt es über das authentifizierte lokale Relay
in H.264/AAC-HLS um und prüft Codec, Auflösung und fehlerfreie Segment-Decodierung.
Tokenprüfung, CORS, HEAD, Verzeichnis-/Dateinamenbeschränkung, Redirect-Ablehnung,
Byte-Ranges, HTTPS-Zielwahl, Startfehler, Zeitablauf, Austausch, HA-Stopp und
Entladen sind automatisiert geprüft. Es wurden keine Receiverbefehle gesendet.

Der langsame erste Volltest direkt auf dem Windows-Mount wurde nach 143
bestandenen Tests abgebrochen und zählt nicht als Volltest. Volltest und
abschließende Medienprüfung liefen mit einer SHA-256-geprüften temporären
Linux-Kopie des Worktrees. Lokale Berichte: `.work/external-linux-tests.log`,
`.work/external-final-tests.log`, `.work/external-final-inventory.json` sowie
`.work/external-hassfest.log`; sie werden nicht ausgeliefert.

**Offene Praxisnachweise:** Bild/Ton auf realen Browsern und Cast-Geräten,
Erreichbarkeit über die jeweilige HA-Adresse/Zertifikatskette, echte Receiver-
Streamingauthentifizierung, freie Tuner/Entschlüsselung sowie längere Wiedergabe
und CPU-Last. Vor einer entsprechenden Gerätefreigabe gesondert abnehmen.
Die früheren Nachweise unten beziehen sich weiterhin auf ihre damaligen Versionen.

## Abgleich von develop mit main – 1.1.4-dev.1

Der aktuelle `main` mit PR #6 und #8 ist in den Entwicklungsstand übernommen.
Die Monitor-Implementierung einschließlich Workflow und Tests entspricht `main`;
Social-Preview und Branch-Regeln aus `develop` sind unverändert erhalten.
Konflikte betrafen ausschließlich Versionsstellen und beide Changelogs; die
Entwicklungsversion ist synchron auf 1.1.4-dev.1 angehoben. Die vorhandenen
Prüfnachweise beider Branches bleiben erhalten. 70 Offline-Blogtests, Python-Syntax,
Versionskonsistenz und Lockdatei wurden nach dem Zusammenführen geprüft.
Integrationscode und Qualitätscheckliste bleiben unverändert; es wurden keine
zusätzlichen Receiver- oder Home-Assistant-Praxisprüfungen ausgeführt.

## Stille Blogprüfungen – 1.1.3

70 Offline-Skripttests bestanden. Neue Fälle prüfen ausschließlich unauffällige
Ergebnisse ohne Issue, gemischte Ergebnisse mit unabhängigem Verbesserungsvorschlag,
weiterhin gemeldete Unsicherheit, fehlgeschlagene Veröffentlichung bei gleichzeitigem
stillem Erfolg, fehlerhafte Statusspeicherung und ungültige Prüfvermerke. Nach
Neuladen des Status bleiben unveränderte Beiträge erledigt; geänderte Inhalte
werden erneut ausgewählt. Python-Syntax und Ruff bestanden.

Die vier gespeicherten echten Junie-Antworten aus
[Lauf 35125959582](https://github.com/topic2k/enigma2-connect/actions/runs/35125959582)
wurden lokal mit der neuen Abschlusslogik abgespielt: vier stille Prüfvermerke,
kein Issue-Aufruf, keine Wiederholung und keine erneute Auswahl am nächsten
Montag. Dabei wurden weder GitHub-Zustände verändert noch KI-Anfragen ausgeführt.
Die Veröffentlichung dieser Filterung auf GitHub ist dadurch noch nicht live belegt.

Die Qualitätscheckliste ist unverändert: Integrationscode (außer Metadatenversion),
Frontend, Integrationstests und Abdeckungsgrenzen bleiben unberührt. Keine neuen
Receiver- oder Home-Assistant-Praxisprüfungen; bisherige offene Nachweise bleiben
bestehen. Vor dem Merge sind aktuelle erfolgreiche CI-Prüfungen erforderlich.

## Automatischer Junie-Monitor – 1.1.2

64 Offline-Skripttests prüfen unter anderem einzelne Beitragspakete, erste und
zweite Fehlschläge, erfolgreiche Teilberichte, Wiederholung am Folgetag,
falsche Beitrags-IDs, erfundene Quellbelege, unabhängige Verbesserungsvorschläge,
Kostenmetadaten und nebenwirkungsfreie Probeläufe. Ruff, Python-Syntax,
Workflow-/Shell-Syntax, Lockdatei sowie Versions-/Dokumentationslinks bestanden.
Die bestehende Retry-Logik wird für die getrennten Jobs wiederverwendet.

Die Qualitätscheckliste wurde auf Auswirkungen geprüft: keine Änderung an
Integrationsverhalten, Abdeckungsanforderungen oder verbleibenden Hardware- und
Home-Assistant-Nachweisen. Der [vollständige Probelauf 35123242339](https://github.com/topic2k/enigma2-connect/actions/runs/35123242339)
auf `57e825a` bestand mit vier separaten Bewertungen. Modbus nennt 2026.9,
2026.10 und 2027.10; Selektoren nennen korrekt keine angekündigte Version;
OAuth2 und Rasenmäher nennen 2026.10. Alle vier deutschen Bewertungen sind
passend zum jeweiligen Beitrag, ohne Auswirkung und ohne konkreten Zusatznutzen
für die vorhandene OpenWebif-Integration. Diese Einordnungen wurden manuell
gegen Blogtexte und Implementierung geprüft. Positive Auswirkungen und konkrete
Verbesserungsvorschläge sind bislang durch simulierte Validierungstests, nicht
durch einen passenden aktuellen Live-Blogfall belegt.

Gemeldete Modellkosten des gesamten Probelaufs: **0,307334 USD** für vier
Beiträge, keine fehlenden Verbrauchswerte. Die bestätigte Top-up-Abbuchung ist
davon zu unterscheiden. Der Statusbranch blieb unverändert auf `fa6aa32`;
der Probelauf erstellte keine Issues. Produktionsnahe Analyse, Sammlung,
Validierung und Berichtserzeugung sind damit live geprüft. Die vollständige
CI zu `57e825a` (Tests, hassfest, HACS und CodeQL) war grün. Danach wurden
nur zwei Offline-Grenzfalltests und Dokumentationsnachweise ergänzt; vor dem
Merge bleiben aktuelle grüne Prüfungen für den endgültigen PR-Stand erforderlich.

## Junie-Einzeltest am 16.09.2026 – 1.1.2-dev.4

Der [Testlauf 35120165171](https://github.com/topic2k/enigma2-connect/actions/runs/35120165171)
auf `a6e4ba7` war erfolgreich: 52 Skripttests und anschließende Live-Analyse eines
Modbus-Beitrags. Der Junie-Job dauerte 1 Minute 50 Sekunden, die eigentliche
CLI-Ausführung rund 69 Sekunden. Der gespeicherte Kontext blieb unverändert.

Die Antwort ist deutsch, korrekt zugeordnet und nennt alle drei Zeitpunkte:
Verfügbarkeit 2026.9, Deprecation 2026.10 und Entfernung 2027.10. Die Bewertung
`no-impact` passt zum bereitgestellten Code: Die Integration nutzt OpenWebif,
keine Modbus-Komponenten oder `modbus-connection`. Die optionale Verbesserung
wurde unabhängig mit `none` bewertet; hierfür wurde kein konkreter Nutzen
gefunden. Leere Beleglisten sind für diese beiden Einstufungen zulässig.
Die automatische Prüfung bestätigte Schema, Beitrags-ID und Belegformat;
Zuordnung, Fristen und Begründung wurden zusätzlich manuell geprüft.

Junies `llmUsage` und `taskCostUsd` melden **0,0483518 USD**. Gemeldete Tokens:
65.759 Eingabe, 145.549 Cache-Eingabe und 6.475 Ausgabe. Hauptmodell war
`gemini-3.7-flash`, Hilfsmodelle `gpt-4.1-mini-2025-04-14`,
`gpt-4.1-2025-04-14` und `gpt-5.4-nano`. Das Standardmodell ist dynamisch;
dieser erfolgreiche JetBrains-Zugang ist daher kein Gemini-unabhängiger Test.
Die Top-up-Anzeige blieb bei der Nachkontrolle auf 3,77 Credits. Das beweist
keinen kostenlosen Aufruf; die tatsächliche Kontobelastung ist dort noch nicht
nachgewiesen. Vier gleich teure Beiträge pro Woche ergäben rechnerisch etwa
0,77 USD für vier Wochen, ohne Garantie für andere Beiträge oder Modelle.

Lokal bestanden Syntaxprüfung, Ruff, Workflow-/Shell-Prüfung, Lock-Prüfung,
Versions-/Dokumentationslinks sowie eine Offline-Prüfung von Vorbereitung,
Berichtserzeugung und Ablehnung einer falschen Beitrags-ID. Die 52 Skripttests
liefen lokal und in GitHub erfolgreich. Diese Prüfungen ersetzen keine
Receiver- oder Home-Assistant-Praxisprüfung. Integrationsfunktionen und
Qualitätskriterien wurden nicht verändert.

Ein einzelner negativer Relevanzfall belegt noch nicht die Qualität bei nötigen
Migrationen oder sinnvollen Ergänzungen. Die übrigen drei Einzelbewertungen
bleiben offen. Keine Issues, Statusschreibzugriffe, produktive Umstellung,
Zusatzkäufe, Tarifänderungen, Merges oder Releases.

## Cloudflare-Fortsetzung am 16.09.2026 – 1.1.2-dev.3

Der autorisierte Folgetagstest wurde um 08:30 Uhr MESZ begonnen. Die frisch
neu geladene Cloudflare-Anzeige meldete vor der Anfrage **0/10.000 Neurons heute**;
im separaten 24-Stunden-Diagramm standen rund 10.020 Neurons vom Vortag.
Das ist keine Bestätigung, dass die serverseitige Zugriffssperre zurückgesetzt war.

Der [Selektor-Einzeltest 35064196248](https://github.com/topic2k/enigma2-connect/actions/runs/35064196248)
auf `fb1b55b` bestand die 52 Skripttests, wurde aber bei der einzigen
Cloudflare-Anfrage mit **HTTP 429 / internem Code 4006** abgelehnt. Eingabe:
267.346 Bytes, keine Modellergebnisse, keine Verbrauchsmetadaten in der Antwort.
Ein unbekannter Verbrauch ist nicht als gemessener Nullverbrauch zu verstehen.

Gemäß der Freigabe bei Quotenfehlern gestoppt: OAuth2- und Rasenmäher-Einzeltests
wurden nicht gestartet; auch kein zusätzlicher Test der fehlenden Modbus-Frist.
Die [offizielle Fehlerliste](https://developers.cloudflare.com/workers-ai/platform/errors/)
nennt 3036 für ein ausgeschöpftes Tageskontingent und 3040 für Kapazitätsengpässe,
führt 4006 jedoch nicht auf. Die genaue Ursache der widersprüchlichen
Dashboard-/API-Anzeige bleibt deshalb ungeklärt.

Der inhaltliche Stand vom 15.09. bleibt bestehen: Die Einzelzuordnung war beim
Modbus-Beitrag besser, aber 2027.10 fehlte. Die drei weiteren Einzelbewertungen
sind nicht nachgewiesen. Kein Wechsel des produktiven Monitors, keine Issues,
Statusschreibzugriffe, neuen Zugangsdaten, Tarifänderungen oder Releases.
Diese Dokumentationsänderung betrifft keine Integrationsfunktionen oder
Qualitätskriterien; fremde lokale Änderungen blieben erhalten.

## Cloudflare-Einzelprüfung – 1.1.2-dev.2

Am 15.09.2026 wurde die getrennte Verarbeitung mit 52 lokalen Skripttests,
Ruff, Python-Syntax, Lockdatei sowie Workflow-/Dokumentationsprüfung geprüft.
Die Tests belegen eine Beitrags-ID je API-Anfrage, Ablehnung fremder IDs und
Erhalt erfolgreicher Teilergebnisse einschließlich Verbrauch bei einem späteren Fehler.
Qualitätscheckliste und Integrationslaufzeit bleiben unverändert.

Der echte [Modbus-Einzeltest 34993573743](https://github.com/topic2k/enigma2-connect/actions/runs/34993573743)
auf `6ab68a7` verarbeitete 70.336 Eingabe- und 541 Ausgabetokens für 2.274,84 Neurons.
Die deutsche Begründung ist dem richtigen Beitrag zugeordnet und die Einstufung
no-impact passt zur fehlenden Modbus-Nutzung. Es gibt keine irrelevanten Codebelege.
Die Entfernungsfrist **2027.10** fehlt weiterhin; nur 2026.10 wird genannt.
Vier ähnlich große Einzelanfragen würden rechnerisch etwa 9.100 Neurons benötigen,
fünf etwa 11.375 und damit mehr als das tägliche kostenlose Kontingent. Dies ist
nur eine Hochrechnung, keine Verbrauchsgarantie für andere Beiträge.

Die Fortsetzung vom 16.09.2026 ist oben dokumentiert; die übrigen drei
Einzelbewertungen bleiben wegen der API-Ablehnung offen.
Kein produktiver Anbieterwechsel, keine Issues, Statusänderungen oder Releases.

## Cloudflare-Probelauf – 1.1.2-dev.2

Am 15.09.2026 wurden Cloudflare Workers AI und `@cf/openai/gpt-oss-120b`
auf einem isolierten Branch mit den vier gespeicherten September-Beiträgen getestet.
50 lokale Skripttests, Python-Syntax, Ruff, Lockdatei und 72 Dokumentationslinks
bestanden. Branch-CI für `b1ff764` und `f771ab5` erfolgreich. Die Qualitätscheckliste
wurde auf Auswirkungen geprüft: Integrationslaufzeit, Kriterien und
Abdeckungsgrenzen bleiben unverändert; keine neuen HA-/Receiver-Praxisnachweise.

- Erstlauf [34991469621](https://github.com/topic2k/enigma2-connect/actions/runs/34991469621):
  erfolgreiche API-Antwort, aber Parserfehler. Der Adapter wurde anhand der echten
  Antwort einer kleinen Diagnoseanfrage korrigiert und offline nachgetestet.
- Vollständiger Lauf [34992280735](https://github.com/topic2k/enigma2-connect/actions/runs/34992280735):
  72.212 Eingabe-, 1.975 Ausgabetokens, 2.432,30 Neurons. Schema und Codezeilenprüfung
  bestanden, aber englische Texte, ausgelassene Fristen und unbrauchbare Lizenzbelege.
- Präzisierte Ausgabevorgaben, Lauf [34992652727](https://github.com/topic2k/enigma2-connect/actions/runs/34992652727):
  72.344 Eingabe-, 1.957 Ausgabetokens, 2.435,27 Neurons. Deutsche Texte und leere
  statt irrelevanter Belege, aber vertauschte Begründungen zwischen Modbus,
  Selektoren und OAuth2. Die Modbus-Entfernungsfrist 2027.10 fehlt weiterhin;
  der Selektor-Beitrag erhält eine dort nicht genannte Versionsangabe.

**Bewertung:** Zugang und Free-Tier-Budget sind für einen gemeinsamen Wochenlauf
belegt. Die formale Antwortprüfung erkennt semantisch vertauschte Begründungen
nicht. Die inhaltliche Qualität dieses Modells im getesteten Batchverfahren reicht
nicht für die Übernahme als automatischer Monitor. Keine Issues veröffentlicht,
keinen Status geändert und keine Umstellung auf main vorgenommen. Die Zustandsreferenz
blieb `fa6aa32eda38a2454d30fd3b11aab0d8198dc972`. Einzelbeitragsanalyse oder ein anderes
Modell benötigen einen gesonderten Qualitäts- und Budgettest. Dauerhafte
Verfügbarkeit und zuverlässige Erkennung tatsächlich relevanter Änderungen sind
mit diesen vier nicht betroffenen Beispielen nicht belegt.

## Wiederholung des Blog-Checks – 1.1.1

Am 14.09.2026: 45 Offline-Tests bestanden, darunter 17 neue Scheduler-/Statustests.
Geprüft wurden erster Fehlschlag ohne Fehlerstatus, zweite Fehlermeldung am
Folgetag, kein doppelter Versuch am selben Tag, spätere Nachholung, Teilerfolge,
unveränderte Originalbeiträge beim Wiederholen, manuelle Wiederaufnahme sowie
GitHub-Statusspeicherung mit Schutz vor überschriebenen Zwischenständen.
Ruff, Formatierung, Python-Syntax und Offline-Lockprüfung (159 Pakete) bestanden.
Die Tests simulieren Google und GitHub sowie mehrere Kalendertage. Sie sind
kein Nachweis eines tatsächlich am Folgetag gelaufenen GitHub-Jobs und keine
zusätzliche Home-Assistant-/Receiverabnahme. Der PR-CI-Lauf prüft den Gesamtstand.

Prüfdatum: **13.09.2026**. Gemeinsamer Entwicklungsstand: **1.1.0-dev.10**.
Dies ist ein technischer Prüfbericht, keine Release- oder Hardwarefreigabe.
Versionshistorie: [Changelog](../CHANGELOG.md). Reproduktionsbefehle:
[Entwicklerdokumentation](ENTWICKLUNG.md#entwicklungsumgebung-und-prüfungen).

Die Veröffentlichung **1.1.0** übernimmt diesen Entwicklungsstand mit stabiler
Versionskennung und aktualisierter Freigabedokumentation. Die folgenden
Hardware-Nachweise bleiben an ihre genannten Versionen und Prüfbedingungen
gebunden; die Veröffentlichung erweitert ihren Umfang nicht. CI-Nachweise zum
endgültigen Commit stehen im [Release 1.1.0](https://github.com/topic2k/enigma2-connect/releases/tag/v1.1.0).
Echte Bonjour-Erkennung, automatischer DHCP-Empfang in laufendem HA und die
subjektive Bild-/Tonprüfung bleiben offen.

## README-Badges: 1.2.0-dev.11

Am **16.09.2026** lokal geprüft: YAML-Struktur und Veröffentlichungsschranken,
unveränderte bisherige CI-Prüfschritte, sechs Fälle für das Auslesen der
Anweisungs-/Zweigabdeckung sowie zehn simulierte GitHub-API-Fälle. Erstveröffentlichung,
Updates mit erhaltener Historie/Dateien, überholte Läufe, Berechtigungsfehler,
fehlende Commits und ungültige Messwerte wurden geprüft. Python-Syntax,
Versionskonsistenz und `uv lock --check --offline` bestanden.
Die neun bereits verfügbaren Badge-URLs liefern HTTP 200 und die erwarteten
Beschriftungen; der Coverage-Endpunkt wartet auf seine Erstveröffentlichung.
Shields wies den Standard-Python-Client mit HTTP 403 ab; der lesende Test mit
benanntem Prüfclient war erfolgreich. Das ist keine Prüfung der Chat-Bildanzeige.

Qualitätscheckliste geprüft: `docs-installation-instructions` betrifft die
aktualisierte HACS-Anleitung; `config-flow-test-coverage` und `test-coverage`
behalten ihre bisherigen Prüfungen und Grenzen. Laufzeitcode und HA-Kompatibilität
werden nicht geändert. GitHub-Release `v1.1.0` und fehlende Listung im
HACS-Standardkatalog wurden lesend bestätigt. Eine tatsächliche HACS-Installation
wurde dabei nicht durchgeführt.

Die API-Prüfungen sind Simulationen, kein erfolgreicher GitHub-Publikationslauf.
Der [Testlauf auf `516424f`](https://github.com/topic2k/enigma2-connect/actions/runs/35135496532)
bestand einschließlich Ruff, Formatierung, mypy, Python-/Frontend-Tests,
Coverage-Sperren und neuem Ausleseschritt. [Hassfest und HACS](https://github.com/topic2k/enigma2-connect/actions/runs/35135496450)
bestanden ebenfalls. Die anschließende Nachweispflege ändert nur diese beiden
Prüfübersichten. Der Veröffentlichungsjob wurde auf `develop` erwartungsgemäß
übersprungen; der erste Schreibzugriff auf den Datenbranch `badges` bleibt offen. Erst nach einem erfolgreichen `main`-Testlauf
mit dem neuen Workflow steht dessen Coverage-Endpunkt bereit. Frühere CI- und
Hardware-Nachweise unten gelten weiterhin nur für ihre angegebenen Stände.

## Dependabot: cryptography und CVE-2026-69247

[Dependabot-Hinweis 1](https://github.com/topic2k/enigma2-connect/security/dependabot/1)
meldet `cryptography 48.0.1` in `uv.lock`. Laut
[Herstellerhinweis](https://github.com/pyca/cryptography/security/advisories/GHSA-g6cj-pr64-35w5)
sind PKCS#7-EnvelopedData-Entschlüsselungsfunktionen ab 44 und vor 50 betroffen;
Version 50 behebt unterscheidbare Fehler und Laufzeiten bei der RSA-Schlüsselentschlüsselung.
Die Suche im Integrationscode fand keinen Aufruf dieser Funktionen. Das ist
keine Aussage über sämtliche Funktionen einer produktiven Home-Assistant-Installation.

Die Abhängigkeit kommt hier über die Entwicklungsgruppe und das HA-Testpaket.
Sowohl HA 2026.9.1 als auch das geprüfte aktuelle 2026.9.2 verlangen weiterhin
cryptography 48.0.1 und pyOpenSSL 26.2.0. Die dokumentierte uv-Ausnahme ersetzt
diese im Teststack durch **cryptography 50.0.1** und **pyOpenSSL 26.4.0**.
Letzteres erlaubt laut Paketmetadaten cryptography ab 49 und unter 51.
Alle übrigen Paketdatensätze bleiben gegenüber `80f9eda` unverändert; nur die
beiden Pakete und die Projektversion wurden in der Lockdatei angepasst.
Die Ausnahme gilt für Entwicklung/CI, nicht als Änderung an einer installierten
HA-Laufzeit. Die Integrationsanforderungen im Manifest bleiben leer.

Die vollständige [CI auf `65be728`](https://github.com/topic2k/enigma2-connect/actions/runs/34772846926)
installierte nachweislich cryptography 50.0.1 und pyOpenSSL 26.4.0. **270 Python-Tests**
bestanden in 8,45 Sekunden, außerdem **8 Frontend-Tests**, Ruff, Formatierung,
mypy und die Coverage-Sperre: Config Flow 100 %, alle 23 Module über 95 %.
[Hassfest und HACS](https://github.com/topic2k/enigma2-connect/actions/runs/34772846924)
bestanden ebenfalls. Lokal wurden Dokumentation, Syntax, Versionen und die
Begrenzung der Paketänderungen geprüft. Der zusätzliche Lauf in der separaten
Umgebung `.work/security-env` wurde nach erfolgreicher CI beendet und wird
nicht als bestandener lokaler Volltest gewertet. Frühere Receiver-Nachweise
beziehen sich weiterhin auf den damaligen Paketstand.
Der Dependabot-Hinweis auf dem Standardbranch bleibt bis zur Übernahme des Fixes
nach `main` offen; er wird nicht manuell als Fehlalarm geschlossen.

## GitHub-CI und FFmpeg-Voraussetzung

**Node.js-24-Umstellung in 1.1.0-dev.9:** Alle direkten Vorkommen von
`checkout@v4`, `setup-uv@v6` und `upload-artifact@v4` wurden durch `v7`, `v10.1.0`
beziehungsweise `v7` ersetzt. Die Action-Metadaten der geprüften Releases
[Checkout 7.0.1](https://github.com/actions/checkout/blob/v7.0.1/action.yml),
[setup-uv 10.1.0](https://github.com/astral-sh/setup-uv/blob/v10.1.0/action.yml)
und [Upload Artifact 7.0.1](https://github.com/actions/upload-artifact/blob/v7.0.1/action.yml)
deklarieren `node24`. Workflow-Trigger, Berechtigungen, Upload-Pfad und
Aufbewahrungsdauer bleiben erhalten. Das ersetzt die veralteten Action-Versionen,
die GitHub zuvor unter Node.js 24 erzwungen ausgeführt hat
([GitHub-Migrationshinweis](https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/)).
Der Blog-Monitor und sein Upload-Schritt bleiben bei Branch-Pushes planmäßig
übersprungen; deren externe API-Ausführung wird durch die CI-Prüfung nicht gestartet.

Der erste Push von `quality-scale`, Commit `0fe1cb2`, bestand
[Hassfest und HACS](https://github.com/topic2k/enigma2-connect/actions/runs/34771537254)
sowie die [Blog-Monitor-Tests](https://github.com/topic2k/enigma2-connect/actions/runs/34771537165).
Im [Testlauf](https://github.com/topic2k/enigma2-connect/actions/runs/34771537046)
bestanden Ruff, Formatierung, mypy und 269 Tests; ein Test wurde wegen fehlendem
FFmpeg übersprungen. Die Silber-Abdeckungsprüfung scheiterte dadurch für
`recording_snapshot.py` mit 92,45 %, während Config Flow 100 % erreichte.
Fassung **1.1.0-dev.8** ergänzt die ausdrückliche Installation und Aufrufprüfung
von FFmpeg im CI-Workflow. Coverage-Schwellen und Integrationsverhalten bleiben unverändert.

**Korrektur auf Commit `ffdf007` bestanden:** Der
[Test-Workflow](https://github.com/topic2k/enigma2-connect/actions/runs/34771754492)
bestand mit **270 Python-Tests ohne übersprungene Tests** in 13,44 Sekunden und
**8 Frontend-Tests**. Ruff, Formatierung und mypy waren grün. Config Flow erreicht
100 % Anweisungs-/Zweigabdeckung, alle 23 Module überschreiten die 95-%-Grenze;
`recording_snapshot.py` erreicht nun 99,06 % kombiniert. Auch
[Hassfest und HACS](https://github.com/topic2k/enigma2-connect/actions/runs/34771754483)
bestanden. Der Blog-Monitor-Testcode blieb gegenüber dem oben verlinkten grünen
Lauf unverändert. Diese Nachweise gelten für den genannten Commit; die
nachfolgende Dokumentation des Ergebnisses ändert den Integrationscode nicht.

## Physischer DHCP-Adresswechsel: fehlende Identitätsdaten

**Ergebnis nach GUI-Neustart: Adressübernahme bestanden.** OpenWebif meldete
danach für `wlan0` wieder die zuvor gesicherte MAC und die neue Adresse. Der
gezielt ausgelöste DHCP-Verarbeitungsschritt übernahm die Adresse und lud den
Eintrag über HTTPS neu. Alle 64 registrierten Entitätskennungen, Gerätezuordnung,
Anmeldung, Port, TLS-Einstellungen und Optionen blieben erhalten; alle neun
Plattformen und 17 aktivierten Entitäten waren verfügbar. Aktualisierung,
wiederholte Meldung ohne weitere Receiver-Abfrage und Entladen bestanden bei
insgesamt 13 lesenden Anfragen. Die bestehende Ausnahme für das nicht
vertrauenswürdige Zertifikat blieb ausschließlich Teil der isolierten Testkonfiguration.

Der Nutzer hat die DHCP-Zuweisung am Router geändert und die Netzwerkschnittstelle
des Octagon neu gestartet. Vorher wurden Geräteidentität, Verbindungseinstellungen
und 64 registrierte Entitäten (17 aktiviert) in einer isolierten HA-Instanz gesichert.
Die neue Adresse antwortete bereits vor dem GUI-Neustart mit OpenWebif; der lokale
ARP-Eintrag bestätigte dieselbe MAC wie vor dem Wechsel. `/api/about` enthielt
jedoch wiederholt nur `wlan0` mit `mac: null` und `ip: 0.0.0.0`.

Die DHCP-Verarbeitung wurde mit der realen neuen Adresse und zuvor gesicherten
MAC in der isolierten HA-Instanz gezielt ausgelöst. Vor dem GUI-Neustart brach
sie mit `wrong_device` ab und übernahm die Adresse nicht; der Schutz vor einer
nicht bestätigten Identität griff korrekt.
Eine echte DHCP-Netzwerkmeldung wurde dabei nicht mitgeschnitten. Registrierungen
wurden aus dem gesicherten Ausgangszustand im Test rekonstruiert; dies ist keine
Abnahme einer durchgehend laufenden produktiven HA-Installation.

OpenWebif bezieht die Adapterdaten aus Enigma2s `iNetwork`; `/api/about` fordert
dabei vollständige Informationen an. Eine veraltete oder unvollständige
Schnittstellenliste in Enigma2 ist deshalb eine plausible Ursache, bislang aber
nicht bestätigt ([OpenWebif-Adapterdaten](https://github.com/E2OpenPlugins/e2openplugin-OpenWebif/blob/master/plugin/controllers/models/info.py),
[About-Endpunkt](https://github.com/E2OpenPlugins/e2openplugin-OpenWebif/blob/master/plugin/controllers/web.py)).
Der anschließend vom Nutzer ausgeführte GUI-Neustart stellte die MAC-Auskunft
in diesem Versuch wieder her. Die zuvor angenommene Bezeichnung als fehlender
LAN-Adapter war unzutreffend; OpenWebif bezeichnet die Schnittstelle als `wlan0`.
Ein Regressionstest bildet die tatsächlich empfangene unvollständige Antwort ab.
Alle **11 Erkennungstests bestanden** unter HA 2026.9.1 / Python 3.14.7.
Die gesonderte Hardware-Prüfung bestätigt außerdem, dass die ursprünglichen
Verbindungsdaten und registrierten Entitätskennungen bei der Ablehnung erhalten bleiben.
Lokale Nachweise: `.work/quality-live/dhcp-baseline.json`, `new-identity.json`,
`dhcp-before-gui-restart.json` und `dhcp-changed.json`. Zugangsdaten bleiben
außerhalb dieser Berichte. Auch die erneute zwölfsekündige Bonjour-Beobachtung
nach dem GUI-Neustart fand keinen passenden Dienst (`octagon-discovery-after-restart-Windows.json`).
Offen bleiben automatischer Empfang einer echten DHCP-Meldung in laufendem HA
und der Bonjour-Einrichtungsnachweis. Die Fassung **1.1.0-dev.7** aktualisiert
Dokumentation und Versionsmetadaten; der geprüfte Integrationscode ist unverändert.

## Erweiterte Hardware- und Integrationsprüfung

Am **13.09.2026** bestand der zusammengeführte Code nach dem Remote-Abgleich mit
`main` bis `640de18` erneut **269 Integrationstests** in **465,79 Sekunden**.
Die Abdeckung beträgt unverändert **99,70 % Anweisungen**, **97,86 % Zweige** und
**99,29 % kombiniert**; Konfigurationsflüsse erreichen 100 % in beiden Messgrößen,
alle 23 Module bestehen die Silber-Sperre. Auch die **28 Blog-Monitor-Tests**
bestanden. Die zusätzlichen UI-Abhängigkeiten der lokalen Testumgebung werden
nicht in die Integrationsanforderungen oder Lockdatei übernommen.

**HTTPS am echten Octagon:** Die strikte Prüfung lehnt das nicht vertrauenswürdige
Zertifikat ab. Ausschließlich im isolierten Test wurde anschließend
`verify_ssl=False` verwendet: HTTP und HTTPS lieferten dieselbe Geräteidentität,
und über HTTPS bestanden Einrichtung, alle neun Plattformen, Aktualisierung,
Duplikatschutz und Entladen mit 16 lesenden Anfragen. Das ist kein Nachweis einer
vertrauenswürdigen Zertifikatskette; produktive TLS-Einstellungen wurden nicht geändert.

**Live-Bild und -Ton:** Ein auf rund 3 MiB begrenzter Ausschnitt des bereits
eingestellten Senders wurde ausschließlich im Arbeitsspeicher geprüft. FFmpeg
dekodierte zwei H.264-Bilder mit 1920 × 1080 Pixeln sowie eine Sekunde AC3-Audio
mit 48 kHz und sechs Kanälen. Der Sender blieb unverändert, keine Inhalte wurden
gespeichert. Das ist ein technischer Dekodiernachweis und keine subjektive
Bild-/Tonprüfung an Fernseher oder Lautsprecher und keine HA-Stream-Wiedergabe.

**Echte HA-Oberfläche:** Mit dem zur HA-Version gehörenden Frontend 20260826.6
wurden die Octagon-Geräteseite, Markenbilder, Symbole und die drei deaktivierten
Signaldiagnosen visuell geprüft. Optionsmenü und Feldbeschreibungen erscheinen
korrekt auf Deutsch und Englisch. Ein absichtlich ungültiger FFmpeg-Pfad in der
temporären HA-Instanz erzeugte den erwarteten Reparaturhinweis mit Abhilfeschritten
in beiden Sprachen. Nach Abwahl der Snapshot-Quelle über den Optionsdialog wurde
der Eintrag neu geladen; die Reparaturliste meldete anschließend keine offenen
Reparaturen. Die Receiver-Zugangsdaten und Testkonfiguration blieben lokal.
Produktive HA-Einstellungen und Receiver-Bedienzustände wurden dabei nicht geändert.
Die Testoberfläche wurde danach beendet. Nachweise: `ui-server.log` und
`ui-repair-server.log` unter `.work/quality-live/` sowie die in dieser Sitzung
geprüften Browseransichten. Der fehlende FFmpeg-Pfad war eine Testbedingung;
Receiver-Abfragen und Frontend waren echt.

**Bonjour:** Auch zwölf Sekunden Beobachtung direkt unter Windows fanden keine
HTTP-/HTTPS-Ankündigung dieses Receivers. Damit liegt weiterhin kein realer
Bonjour-Einrichtungsnachweis vor. Für den physischen DHCP-Test ist ein kontrollierter
Adresswechsel am Router erforderlich; der inzwischen ausgeführte Versuch und
sein Identitätsproblem sind im vorherigen Abschnitt dokumentiert.

**Aufnahmebild und Bedienaktionen:** Der produktive Snapshot-Pfad erzeugte aus
einer vorhandenen Aufnahme ein vollständig dekodierbares JPEG mit 640 × 360
Pixeln (17.007 Bytes nach Normalisierung). Der Abruf war auf 64 MiB begrenzt;
Bilddaten wurden nicht gespeichert, Sender und Standby blieben unverändert.
Anschließend bestanden zwölf Prüfungen mit begrenzten Bedienaktionen:
Lautstärke ändern und zurücksetzen, Stummschaltung einschließlich wiederholtem
gleichen Sollwert, eine dreisekündige Bildschirmmeldung sowie Anlegen,
Aktivieren, Deaktivieren und Entfernen eines eigenen zukünftigen Umschalttimers.
Lautstärke und Stummschaltung wurden wiederhergestellt; die sechs vorhandenen
Timer und sieben Aufnahmen der nicht rekursiven Vergleichsliste blieben unverändert.
Es gab keine Bereinigungsfehler. Das bestätigt die API-Bedienung; die Meldung
wurde nicht am Fernseher visuell bestätigt. Nachweise:
`octagon-recording-image.json` und `controls-results.json` unter `.work/quality-live/`.

Nachweise: `.work/quality-live/integrated-tests.log`, `coverage-integrated.json`,
`octagon-https.json`, `octagon-stream.json` und `octagon-discovery-Windows.json`.
Die Dokumentation und Versionsmetadaten werden als **1.1.0-dev.5** fortgeschrieben.

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
keine Dienste ankündigt; der Bonjour-Nachweis bleibt offen. Die inzwischen
ergänzten HTTPS-, Medien-, Bedienungs- und Oberflächenprüfungen stehen oben.
Automatischer Empfang echter DHCP-Meldungen und subjektive Bild-/Tonprüfung bleiben offen.

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

## Social Preview – 14.09.2026

Für 1.1.2-dev.1 das neue GitHub-Bild in 1280 × 640 Pixeln exportiert und
visuell geprüft. PNG-Abmessungen, vollständig deckender Hintergrund,
SVG-Struktur und reproduzierbarer Export mit `-SocialOnly` geprüft.
Die acht HA-Brand-Dateien und die Integrationslogik bleiben unverändert;
die Qualitätscheckliste ist dadurch nicht betroffen. Kein neuer HA-/Receiver-Test.
Quelle und Exportanleitung: [Branding](../assets/branding/README.md).
