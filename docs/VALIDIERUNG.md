[Deutsch](VALIDIERUNG.md) | [English](VALIDATION.en.md)

# Prüfübersicht

Prüfdatum: **13.09.2026**. Geprüfter Release-Kandidat: **1.0.0**.
Dies ist ein technischer Prüfbericht, keine Release- oder Hardwarefreigabe.
Versionshistorie: [Changelog](../CHANGELOG.md). Reproduktionsbefehle:
[Entwicklerdokumentation](ENTWICKLUNG.md#entwicklungsumgebung-und-prüfungen).

## API-Korrektur 1.0.2

Der erste [Live-Probelauf](https://github.com/topic2k/enigma2-connect/actions/runs/34765832835)
erreichte Google mit dem Repository-Secret, erhielt für Gemini 2.5 Flash aber
HTTP 404. Deshalb verwendet der Workflow Gemini 3.8 Flash und `thinkingLevel: low`
ohne den alten Temperaturparameter. Google führt Ein- und Ausgabe für dieses
Modell im [Free Tier](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.8-flash).
Die 28 Offline-Tests prüfen auch Modellpfad und Anfrageparameter. Der tatsächliche
API-Erfolg wird erneut im GitHub-Actions-Probelauf geprüft.

## Blog-Workflow 1.0.1

Am 13.09.2026 wurde der isolierte Workflow-Stand auf Basis von `main` / `1.0.0`
geprüft: 28 Offline-Tests bestanden unter WSL/Python 3.14.7. Sie decken beide
Bewertungen (Kompatibilität und Verbesserungspotenzial), Quellenbelege,
Duplikatschutz, Anfragegrenzen und Fehlerfälle ohne Issue-Veröffentlichung ab.
Ruff, Formatierung, Python-Syntax und Offline-Lockprüfung bestanden; die Lockdatei
ändert ausschließlich die lokale Projektversion auf `1.0.1` (154 Pakete).
Vier vorhandene September-Beiträge passen zusammen mit dem Quellstand in
230.009 UTF-8-Eingabebytes. Das ist keine gemessene Tokenzahl.

Gemini-Antworten und GitHub-Schreibzugriffe sind in diesen Tests simuliert.
`GEMINI_API_KEY` ist als Repository-Secret hinterlegt. Ein echter Probelauf wird
nach dem Merge über GitHub Actions ausgeführt; dessen Laufbericht ist der Nachweis
für die Live-Anbindung. Die Wochenprüfung schlägt Änderungen vor und ändert den
Integrationscode nicht. Keine neue Receiver-/Oberflächenabnahme durch diese Prüfung.

## Aktuelle lokale Prüfungen

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

Browser-/Cast-Streaming, Wake-on-LAN, automatische Receiver-Erkennung, neue
wiederkehrende Timer und Antworten auf Bildschirmnachrichten sind nicht
implementiert. Weitere Sonderfälle stehen in der Entwicklerdokumentation.
