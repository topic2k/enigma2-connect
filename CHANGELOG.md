[Deutsch](CHANGELOG.md) | [English](CHANGELOG.en.md)

# Changelog

## Inhaltsverzeichnis

- [1.2.0-dev.10](#120-dev10)
- [1.1.3](#113)
- [1.1.2](#112)
- [1.1.1](#111)
- [1.1.0](#110)
- [1.0.2](#102)
- [1.0.1](#101)
- [1.0.0](#100)

## 1.2.0-dev.10

Unveröffentlichte Entwicklerversion.

- HLS-Spultest auf explizite Videozeitstempel umgestellt: AAC-Vorlauf darf das
  Sprungziel an Farb-/Segmentgrenzen nicht verschieben. Startzeitpunkte sämtlicher
  Testsegmente werden zusätzlich geprüft; Streaming-Verarbeitung unverändert.

- Aufnahme-Streaming und mehrfache Vor-/Rücksprünge im realen Home Assistant
  durch Nutzerprüfung und Debuglog bestätigt. Originalvideo bleibt erhalten,
  nur MP2-Ton wird zu AAC umgewandelt; Feature zur Übernahme nach `develop` freigegeben.

- Aufnahme-Streaming optimiert: geeignete H.264-Originalspuren samt Bildrate und
  Qualität erhalten, passenden AAC-Ton kopieren und sonst nur Ton umwandeln.
  Vorhandene Enigma2-Aufnahmeindizes erlauben schlüsselbildgenaues HLS-Spulen ohne
  Vollscan. Index-/FFmpeg-Prüfung, klar protokollierter Rückfall und insgesamt
  32 MiB Abschnitts-Cache je Sitzung. Kompatibilitätsmodus bleibt verfügbar.

- Spulen in abgeschlossenen TS-Aufnahmen: vollständige HLS-VOD-Zeitleiste und
  bedarfsgesteuerte Erzeugung angeforderter Abschnitte mit durchgehenden
  Zeitstempeln. Begrenzter Cache, unabhängige Wiedergaben und automatische
  Rückkehr zur bisherigen Wiedergabe bei fehlender Eignung des Receivers.
  Der VOD-Rückfall verwendet HA-Kodierung zu H.264/AAC mit den bestehenden Qualitätsvorgaben.

- Medienquelle in allen Sprachen einheitlich „Enigma2 Connect“ benannt.
  Bedienhinweise angepasst und HLS-Laufzeit sowie Grenzen beim Spulen in der
  Entwicklerdokumentation erläutert; Qualitätsvorgaben bleiben dokumentiert.

- Streaming-Debugmeldungen mit unabhängiger Sitzungskennung, erkannten Codecs,
  Bild-/Tonparametern, Verarbeitungsweg, Rückfallgründen und Pool-Ereignissen.
  Zugangsdaten und Wiedergabe-URLs werden dabei nicht protokolliert.

- Mehrere externe Streams pro Receiver: einstellbare Grenze mit Standard 5 und
  0 für unbegrenzt. Zusätzliche Starts beenden keine bestehenden Streams.
  Derselbe Live-Sender wird zwischen Zuschauern geteilt, Aufnahmen starten separat.
  Auch gleichzeitige Startanfragen berücksichtigen die Grenze; bei voller Belegung
  wird nur der zusätzliche Start mit einer übersetzten Meldung abgelehnt.

- Automatische Stream-Verarbeitung: geeignetes Receiver-HLS weiterreichen,
  passende Video-/Audiospuren unverändert übernehmen und Receiver-Transcoding
  vor Software-Umwandlung prüfen. Nur ungeeignete Spuren werden neu kodiert.
  Ein Kompatibilitätsmodus erzwingt bei Bedarf die bisherige vollständige Umwandlung.

- Browser-Wiedergabe repariert: HLS wird mit dem von Home Assistants Medien-
  Dialog erwarteten MIME-Typ `application/x-mpegURL` übergeben. Damit wird der
  eingebaute HLS-Player statt der Meldung über einen nicht unterstützten
  Medientyp ausgewählt. Die exakte Schreibweise ist durch einen Regressionstest abgesichert.

- Idee Nr. 13: optionale externe Wiedergabe von Live-TV und TS-Aufnahmen über
  die HA-Medienquelle. Software-Video-Umwandlung liefert H.264 bis 720p/25 fps;
  geeignete Originalspuren behalten ihre Qualität.
- Receiver-Anmeldung bleibt im Backend; zufällige Wiedergabe-URLs verfallen bei
  Inaktivität, Entladen oder spätestens nach sechs Stunden. Mehrere Streams
  pro Receiver haben unabhängige Ressourcen und Lebenszeiten. Geeignete Aufnahmen
  erhalten eine vollständige Zeitleiste; der Aufnahme-Fallback nutzt ein begrenztes Fenster.
- Live-TV-Port und HTTPS getrennt vom OpenWebif-Zugang einstellbar. Deutsche und
  englische Bedienhinweise sowie simulierte und lokale FFmpeg-Tests ergänzt.
  Browser-/Cast-Geräteabnahme bleibt gesondert auszuweisen.
- Neue Projekt-Worktrees liegen verbindlich unter `V:\enigma2-connect-worktrees`.
- GitHub-Social-Preview in 1280 × 640 Pixeln ergänzt: Gerätesymbol mittig über
  der Wortmarke auf weißem Hintergrund, mit PNG, SVG-Quelle und `-SocialOnly`-Export.
- Aufgaben auf eigenen Branches bearbeiten, umfangreichere Aufgaben zusätzlich
  in eigenen Worktrees. Fertige Änderungen geprüft nach `develop` übernehmen
  und pushen. PR-Vorbereitung und PR nach `main` erst nach Nutzerfreigabe;
  Merge und Release erfordern ebenfalls die jeweils ausdrückliche Freigabe.
- Aktuellen `main` mit Junie-Blog-Monitor und stillen Prüfvermerken nach
  `develop` übernommen; Social-Preview und Branch-Regeln bleiben erhalten.

## 1.1.3

Unveröffentlicht.

- Blog-Monitor veröffentlicht nur noch Beiträge mit Anpassungs-, Verbesserungs-
  oder Prüfbedarf. Unauffällige Ergebnisse werden ohne Issue dauerhaft als geprüft
  gespeichert; unveränderte Beiträge verbrauchen dadurch keine erneuten KI-Credits.

## 1.1.2

Unveröffentlicht.

- Blog-Monitor auf Junie-Einzelanalysen umgestellt: wöchentlich neue Beiträge,
  Wiederholung fehlgeschlagener Beiträge am Folgetag, getrennte Prüfung und
  Veröffentlichung sowie nachvollziehbare Modellkosten im Bericht.

- Junie-Probelauf erfolgreich: deutsche Bewertung mit vollständigen Modbus-Fristen;
  gemeldete Modellkosten rund 0,048 USD, tatsächliche Top-up-Abbuchung noch offen.

- Manueller Junie-Einzeltest mit rein lesenden GitHub-Rechten, einem Blogbeitrag
  und anschließender Prüfung der Ergebnisstruktur und Quellbelege.

- Fortsetzung des Cloudflare-Tests dokumentiert: API lehnt erste Anfrage trotz
  zurückgesetzter Dashboard-Anzeige mit HTTP 429/4006 ab; weitere Tests gestoppt.

- Cloudflare-Einzelprüfung mit einer Anfrage je Beitrag, gezielter Dateiauswahl,
  Verbrauchssummen und Erhalt bereits erfolgreicher Teilberichte bei späteren Fehlern.

- Manueller Cloudflare-Probelauf mit gpt-oss-120b für gespeicherte Blogbeiträge;
  gleiche Codebeleg-Prüfung, nur Berichtsartefakte, keine Issues oder Statusänderungen.

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
