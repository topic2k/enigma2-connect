# Enigma2 Connect

> **Mit KI entwickelt.** Diese Software wurde mit Unterstützung generativer KI entwickelt.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="custom_components/enigma2_connect/brand/dark_logo@2x.png">
  <img src="custom_components/enigma2_connect/brand/logo@2x.png" alt="Enigma2 Connect" width="720">
</picture>

Eigenständige Home-Assistant-Integration für Enigma2-Receiver mit OpenWebif.
Entstanden aus der Analyse von `homeassistant-enigma-player` und `HAVUOpenWebif`;
die Integrationslogik wurde für eine gemeinsame Architektur neu geschrieben.

**Projektname:** Enigma2 Connect · Repository: `enigma2-connect` ·
Integrationsdomain: `enigma2_connect`.
Für vorhandene Installationen der vorherigen lokalen Fassung gilt die
[Anleitung zur Umstellung](docs/UMSTELLUNG.md).
Als [Branding](docs/branding/README.md) ist „Integriert“ ausgewählt: Receiver und Fernbedienung bilden ein gemeinsames Symbol.

**Entwicklungsstand 0.1.0:** lokale Erstfassung für Home Assistant **2026.9 oder neuer**.
Automatisierte Prüfungen laufen gegen **2026.9.1 / Python 3.14.7** mit simulierten
Receiver-Antworten. Ergänzend wurde die Integration mit einem Octagon SF8008 4K
Supreme sowie einer Vu+ Solo² auf zwei unterschiedlichen OpenWebif-Versionen geprüft.

Die ausführliche [Repository-Analyse](docs/ANALYSE.md) erklärt Aufbau, Funktionen,
Schnittmengen und Entscheidungen. Der [Vergleich mit HA Core](docs/CORE-VERGLEICH.md)
und die [Lizenzprüfung](docs/LIZENZEN.md) ergänzen die Vorlagenanalyse.
[Architektur und HA-Vorgaben](docs/ARCHITEKTUR.md)
sowie [Prüfstatus und nächste Schritte](docs/VALIDIERUNG.md) ergänzen sie.

## Funktionen

| Plattform | Verhalten |
| --- | --- |
| `media_player` | Standby/Tiefschlafoption, Lautstärke, Stummzustand, Wiedergabetasten, Kanalwechsel, EPG mit Beschreibung/Zeiten, TV-/Radioquellen und Medienbilder |
| Medienbrowser | Aufnahmen mit navigierbarer Unterordnerstruktur. Titel enthalten Aufnahmedatum, Uhrzeit (HA-Zeitzone), Sender und Länge in Stunden/Minuten, soweit verfügbar; Wiedergabe **auf dem Receiver**. Senderauswahl über „Quelle“. |
| `remote` | Benannte Linux-Tasten oder numerische Keycodes, Sequenzen, Wiederholungen und lange Tastendrücke |
| `notify` | Bildschirmnachrichten über `notify.send_message`, optional mit Titel |
| `select` | Bouquet und Sender mit gemeinsamem Katalog; doppelte Namen bleiben eindeutig |
| `sensor` | Sender, laufende/nächste Sendung, Signalqualität, SNR, gemeldete BER, Aufnahme- und Timeranzahl |
| `binary_sensor` | Standby, Aufnahme, Streaming, Verbindung |
| `camera` | Authentifiziert geladenes Bildschirmfoto mit fünf Sekunden Cache |
| `calendar` | Aufnahme-/Umschalt-Timer, einschließlich wöchentlicher Wiederholungen |
| `button` | Listen aktualisieren; einzelne Fernbedienungstasten sind standardmäßig deaktiviert |

Geräteaktionen: Bildschirmnachrichten mit eigenen Parametern, Neustart, GUI-Neustart,
Tiefschlaf sowie Timer anlegen, löschen und aktivieren/deaktivieren.
Alle Geräteaktionen benötigen ausdrücklich eine `device_id`.

## Installation

1. OpenWebif auf dem Receiver aktivieren. Hostname/IP, HTTP(S)-Port und Zugangsdaten bereithalten.
2. `custom_components/enigma2_connect` nach `/config/custom_components/enigma2_connect` kopieren.
3. Home Assistant neu starten.
4. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Enigma2 Connect**.
5. Adresse ohne `http://` oder Pfad eingeben; ein leerer Port verwendet 80 bzw. bei HTTPS 443.

Jeden Receiver separat hinzufügen. Die Domain heißt `enigma2_connect`; es gibt keine
YAML-Konfiguration, Alias-Domains oder Migration alter Entitäten/Automationen.
Die Integration darf neben den alten Integrationen installiert werden; für den
normalen Betrieb empfiehlt sich eine einzige zuständige Integration pro Receiver.

Die Repository-Struktur enthält HACS-Metadaten. Nach der Veröffentlichung kann
`https://github.com/topic2k/enigma2-connect` in HACS als benutzerdefiniertes
Repository der Kategorie **Integration** hinzugefügt werden. Die Aufnahme in den
HACS-Standardkatalog ist für die erste Veröffentlichung nicht vorgesehen.

## Konfiguration und Optionen

Host, Port, Benutzername, Passwort und TLS-Einstellungen lassen sich über
**Neu konfigurieren** ändern. Abgelehnte Zugangsdaten starten den HA-Dialog zur
erneuten Anmeldung. HTTPS prüft Zertifikate standardmäßig; bei einem eigenen,
nicht vertrauten Zertifikat kann die Prüfung in der Einrichtung deaktiviert werden.

| Option | Standard | Bedeutung |
| --- | --- | --- |
| Abfrageintervall | 15 s | Zustand, Signal und EPG; einstellbar 5–300 s |
| Standard-Bouquet | leer | Benannte TV-/Radioauswahl oder eigene Referenz; sonst erstes geliefertes Bouquet |
| Medienbild | `picon` | Alternativ `screenshot` oder `none`; aktuelle Bildschirmfotos zusätzlich über Kamera |
| Ausschaltmodus | `standby` | `deep_standby` fährt den Receiver beim Ausschalten des Medienplayers herunter |
| Nachrichtentyp | 1 | OpenWebif-Typ 0–3; Interpretation gemäß Receiver-Image |
| Anzeigedauer | 10 s | 1–120 Sekunden |
| Receiver-Zeitzone | HA-Zeitzone | IANA-Name, z. B. `Europe/Berlin`; für wiederkehrende Timer |

Im Medienbild-Modus `screenshot` erfolgt der erste Bildabruf frühestens eine Sekunde
nach einem erkannten Senderwechsel, damit der Receiver das neue Bild aufbauen kann.
Beim Zurückschalten wird ein neues Bild angefordert. Benötigt der Receiver länger,
kann trotz dieser Wartezeit noch ein schwarzes Übergangsbild entstehen.

Bouquetreferenzen stehen in OpenWebif unter `/api/bouquets`.
Die Bouquetauswahl zur Laufzeit gilt bis zum Neuladen; ein gewünschter Startwert
wird über die Option gespeichert. Sender werden nach Auswahl nicht nur lokal
als aktiv markiert: der angezeigte Zustand stammt aus der Receiver-Abfrage.

Timer und Aufnahmeverzeichnis werden alle 120 Sekunden aktualisiert, Senderkataloge
alle 300 Sekunden. Der Listen-Button und erfolgreiche Timeraktionen aktualisieren
diese Daten vorzeitig. Bildschirmfotos werden ausschließlich auf Anforderung geladen.
Im Standby entfallen Signal-/EPG-Abfragen. Der Standard-Aufnahmeordner des Receivers
wird gelesen; eine rekursive Medienbibliothek ist nicht enthalten.

## Beispiele

Die Beispiel-Entitäten und Geräte-IDs durch die Werte der eigenen Installation ersetzen.

```yaml
action: remote.send_command
target:
  entity_id: remote.test_receiver_remote
data:
  command: [menu, down, down, ok]
  delay_secs: 0.3
  num_repeats: 1
```

`hold_secs > 0` wird als OpenWebif-Tastentyp `long` übertragen. Die genaue Haltezeit
bestimmt die Receiver-Firmware. Nicht im Standardumfang enthaltene Tasten können
als numerischer Linux-Keycode gesendet werden.

```yaml
action: media_player.play_media
target:
  entity_id: media_player.test_receiver
data:
  media_content_type: channel
  media_content_id: "105"
```

Das sendet die Ziffern und OK an den Receiver. Alternativ nimmt `enigma2_reference`
eine Service-Referenz entgegen; `enigma2_recording` spielt eine Aufnahme-Referenz ab.
Direkter Videostream im HA-Browser und Weiterleitung an Cast-Geräte sind nicht enthalten.

**Medien durchsuchen** zeigt ausschließlich Aufnahmen. Unterordner mit Aufnahmen
lassen sich öffnen; Ordner stehen vor den Aufnahmen der jeweiligen Ebene.
Der Standard-Medienbrowser bietet keine zusätzlichen Detailspalten oder einen
vollständig aufgeklappten Baum. Die verfügbaren Angaben stehen deshalb im Titel,
zum Beispiel `Tatort · 13.09.2026 20:15 · Das Erste HD · 1 h 30 min`.
Datum und Uhrzeit verwenden die HA-Zeitzone; fehlende Angaben werden ausgelassen.
Fernsehsender sind weiterhin über **Quelle** erreichbar.

OpenWebif meldet über die verwendeten Statusendpunkte keinen verlässlichen
Pausezustand. Während der Receiver eingeschaltet ist, kennzeichnet der Medienplayer
seinen Wiedergabestatus deshalb als angenommen (`assumed_state`). HA kann damit
separate Play-/Pause-Tasten anzeigen. Die Anzeige „Wiedergabe“ beweist nicht, dass
eine laufende Timeshift- oder Aufnahmewiedergabe gerade unpausiert ist.
Stop ist als `media_player.media_stop` verfügbar, wird aber nicht von jeder
Standardkarte als eigene Taste eingeblendet. Für ständig sichtbare Bedienelemente
können Dashboard-Buttons die Aktionen `media_player.media_play`,
`media_player.media_pause` und `media_player.media_stop` direkt aufrufen.

Die Entität „Receiver-Steuerung“ gehört zur Plattform `remote`: Ihr Ein-/Aus-Schalter
steuert den normalen Standby; `remote.send_command` sendet Fernbedienungstasten.
In einer reinen Schalterkachel bietet sich der Anzeigename „Receiver ein/aus“ an.

Unter **Entwicklerwerkzeuge → Aktionen** wird für Nachrichten `notify.send_message`
gewählt und die Entität „Bildschirmnachricht“ als Ziel gesetzt. Es gibt keine
separate Legacy-Aktion `notify.<receivername>`. Vor der ersten Nachricht kann der
Zustand der Notify-Entität „Unbekannt“ sein; er ist kein Erreichbarkeitssensor.

```yaml
action: notify.send_message
target:
  entity_id: notify.test_receiver_screen_message
data:
  title: Türklingel
  message: Es hat geklingelt.
```

```yaml
action: enigma2_connect.timer_add
data:
  device_id: DEINE_RECEIVER_GERAETE_ID
  service_reference: "1:0:1:6DD2:44D:1:C00000:0:0:0:"
  begin: "2026-10-10T20:15:00+02:00"
  end: "2026-10-10T21:45:00+02:00"
  name: Film
  description: Aufnahme aus Home Assistant
  justplay: false
  afterevent: 3
```

`timer_delete` und `timer_toggle` benötigen `device_id`, `service_reference`,
`begin` und `end` des vorhandenen Timers. Bei einer Wiederholung sind dies die
ursprünglichen Werte des Receiver-Timers, nicht eine expandierte Kalenderinstanz.
Die Aktionen wirken auf den gesamten Receiver-Timer. Der Kalender ist lesend;
neue wiederkehrende Timer und das Bearbeiten einzelner Wiederholungen sind noch
nicht über die Integration möglich.

Bei Zeitumstellungen haben die vom Receiver gelieferten Zeitstempel Vorrang.
Weitere Wochenwiederholungen werden in der Receiver-Zeitzone berechnet:
Nicht existierende Start-/Endzeiten im Frühjahr werden ausgelassen; bei einer
doppelten Uhrzeit im Herbst wird für hochgerechnete Termine die erste verwendet.
Hat ein Timer durch die Rückstellung keine positive Dauer nach lokaler Uhrzeit,
wird für weitere Wiederholungen seine tatsächlich verstrichene Dauer verwendet.
Diese Kalenderberechnung verändert keine Receiver-Timer; das Verhalten einer
konkreten Firmware bei solchen Serien muss am Gerät verglichen werden.

Die Geräte-ID lässt sich im Aktionseditor auswählen. Alle eigenen Aktionen sind
mit Selektoren und deutschen/englischen Übersetzungen versehen.

## Optionale Fernbedienungskarte

`www/enigma2-connect-remote-card.js` separat nach
`/config/www/enigma2-connect-remote-card.js` kopieren und die Dashboard-Ressource
`/local/enigma2-connect-remote-card.js` als **JavaScript-Modul** hinzufügen.
Die Integration installiert die Karte nicht automatisch.

Danach im Dashboard **Karte hinzufügen → Nach Karte** nach **Enigma2** suchen
und **Enigma2 Connect Fernbedienung** auswählen. Die Kartenauswahl zeigt eine gerenderte
Vorschau der Fernbedienung. Im grafischen Editor die Receiver-Steuerung und optional
einen eigenen Namen auswählen. Der Entitätsfilter
zeigt ausschließlich Remote-Entitäten dieser Integration. Unter **Nach Entität**
wird die Karte auch für eine passende Receiver-Steuerung vorgeschlagen.

Nach dem Ersetzen einer älteren JS-Datei die vorhandene Ressource beispielsweise
auf `/local/enigma2-connect-remote-card.js?v=2` ändern und den Browser vollständig neu
laden. Den vorhandenen Ressourceneintrag aktualisieren, keinen zweiten anlegen.
Ein HA-Neustart ist für dieses Kartenupdate nicht erforderlich.

Alternativ bleibt die manuelle Konfiguration möglich:

```yaml
type: custom:enigma2-connect-remote-card
entity: remote.test_receiver_remote
name: Wohnzimmer
```

Pfeile, Lautstärke, Kanal und Spultasten unterstützen Gedrückthalten.
Fehler werden in der Karte angezeigt. Die Karte spricht ausschließlich die
HA-Fernbedienungsaktion an; sie benötigt keine Receiver-Zugangsdaten.

## Grenzen und Fehlersuche

- Unterstützt wird OpenWebif mit JSON-API. Alte reine XML-Webinterfaces sind kein Ziel.
- Ein nicht erreichbarer Receiver wird `unavailable`; das ist kein Standby-Zustand.
- Tiefschlaf beendet regelmäßig die Erreichbarkeit. Aufwecken daraus ist hardwareabhängig;
  Wake-on-LAN ist in dieser Version nicht implementiert. `turn_on` beendet normalen Standby.
- Neustart, GUI-Neustart und Tiefschlaf werden bei einem Verbindungsabbruch nicht automatisch
  erneut gesendet. Fehlt die vollständige Antwort, meldet HA eine unbestätigte Ausführung:
  Der Receiver kann den Befehl bereits ausgeführt haben. Vor erneutem Senden den Zustand prüfen.
  Eine positive Antwort bestätigt die Annahme des Befehls; eine Rückfrage am Fernseher
  kann den Neustart trotzdem noch verhindern. Das gilt auch für den Tiefschlaf über den Medienplayer.
- Signal/BER variieren nach Tuner und Image. Fehlende Werte bleiben unbekannt.
  Liefert OpenWebif im dB-Feld denselben ganzzahligen Prozentwert wie bei der
  Signalqualität, wird dieser Ersatzwert als unbekannt behandelt. Signalwerte
  allein belegen keinen tatsächlichen Empfang.
  BER wird als vom Receiver gemeldeter Wert ohne erfundene Einheit dargestellt.
- Temperatur, freier RAM/Festplattenspeicher und Uptime sind bewusst noch nicht als Sensoren umgesetzt;
  ihre Quellen und Einheiten waren im Vorgänger uneindeutig.
- Picons benötigen passende Receiver-Dateien. Neben DVB-Referenzen werden lokale Hinweise
  und normalisierte Sendernamen versucht; für Aufnahmen zusätzlich das übliche Dateinamenmuster.
  Der Medienplayer stellt kein präzises Pause-/Timeshift-Feedback bereit, da `statusinfo` dies nicht zuverlässig meldet.
- Keine automatische SSDP-/Zeroconf-Erkennung in 0.1.0. Einrichtung erfolgt über die UI.
- Eine fehlgeschlagene optionale Listenabfrage ist keine leere Liste. Kalender wird unavailable,
  Zähler unbekannt; ein späterer Abfragezyklus versucht die Funktion erneut.

Bei Problemen zunächst OpenWebif im Browser prüfen, danach **Neu konfigurieren**
für Host/Port/TLS verwenden. Diagnoseexport unter Geräte & Dienste enthält nur
Abfrageerfolg, fehlerhafte Endpunkte und Anzahlen. Er enthält keine Zugangsdaten,
Sendernamen, Aufnahme-Titel oder Netzwerkadressen.

Zum Entfernen den Integrationseintrag in Home Assistant löschen. Optional anschließend
den Komponentenordner und die separat eingebundene Dashboard-Ressource entfernen.
Aufnahmen und Receiver-Timer werden dadurch nicht gelöscht.

## Entwicklung

Unverbindlich vorgemerkte Erweiterungen stehen in [IDEEN.md](docs/IDEEN.md),
darunter interaktive Bildschirmnachrichten mit Antwortauswertung in Home Assistant.

Unter Linux/WSL, Python 3.14.2 oder neuer:

```sh
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov=custom_components.enigma2_connect --cov-report=term-missing
node --test tests/frontend.test.cjs
```

Eine CI-Konfiguration ist enthalten. Details zu Testumfang, noch offenen
Hardwareprüfungen und Veröffentlichung stehen in [VALIDIERUNG.md](docs/VALIDIERUNG.md).

## Lizenz

Der neue Produktionscode steht unter **Apache-2.0**, siehe [LICENSE](LICENSE),
[NOTICE](NOTICE) und [Lizenzentscheidung](docs/LIZENZEN.md). Lokale Recherchedateien
und Testwerkzeuge unter `.work/` behalten ihre Fremdlizenzen und werden nicht veröffentlicht.


