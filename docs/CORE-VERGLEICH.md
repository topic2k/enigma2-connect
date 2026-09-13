# Vergleich mit der offiziellen HA-Integration

Untersucht wurde [home-assistant/core, Domain `enigma2`](https://github.com/home-assistant/core/tree/2f79d1fd2afdd19d28f9d4662a4de21865ea03ca/homeassistant/components/enigma2),
Commit `2f79d1fd2afdd19d28f9d4662a4de21865ea03ca` des angefragten `dev`-Branches.
Abgerufen am 12.09.2026. Der festgehaltene Commit ist maßgeblich, weil `dev` veränderlich ist.

Zusätzlich geprüft: die im Manifest fest gepinnte Bibliothek **openwebifpy 4.3.1**.
Ihr PyPI-Quellarchiv wurde gegen SHA-256
`15aca7253f9b47ade72302c4c178d38f03d7677439fd7fb3a71d204c0dcfaa8f` geprüft.
Referenz: [openwebifpy](https://github.com/autinerd/openwebifpy).

## Aufbau

Die offizielle Integration verwendet Config Flow, typisierte Runtime-Daten und
DataUpdateCoordinator. Sie stellt ausschließlich einen Medienplayer pro Receiver bereit.
HTTP-Zugriffe, Antwortmodelle, Senderlisten und Picon-Suche liegen überwiegend in
`openwebifpy`. Der Coordinator liest Modell/Hersteller/MAC und registriert Geräteverbindungen
anhand der Netzwerkadressen. Optionen umfassen Bouquet, Tiefschlaf beim Ausschalten
und ein Feld für Kanalbilder.

## Funktionsabgleich nach Ergänzung des neuen Projekts

| Offizielle Funktion | Enigma2 Connect | Ergebnis |
| --- | --- | --- |
| UI-Einrichtung, HTTP(S), Auth | vorhanden, zusätzliche Hostvalidierung/Reauth/Reconfigure | ersetzt |
| Modell/Hersteller und MAC-Gerätezuordnung | vorhanden; Netzwerkverbindung jetzt ergänzt | ersetzt |
| Lautstärke und Soll-Mute | vorhanden; Mute liest aktuellen Zustand unter Lock | ersetzt |
| Play/Pause/Stop, Kanal auf/ab | vorhanden | ersetzt |
| Quellenliste eines Bouquets | gemeinsame Quellen-/Select-Liste | ersetzt |
| TV **und Radio** aus `get_all_bouquets` | nun zwei Abfragen nach `stype`, zusammengeführt | zuvor fehlend, ergänzt |
| Bouquet-Option als benannte Auswahl | nun Dropdown mit Labels und Referenzen; eigene Referenzen erlaubt | verbessert |
| EPG-Beschreibung, Beginn, Ende, Aufnahmeflag | Attribute `programme_description`, `programme_start`, `programme_end`, `recording_active` | zuvor teilweise fehlend, ergänzt |
| Picon nach Sendername und Service-Referenz | nun lokale Picon-Hinweise, Service-Referenz und Namensfallback | zuvor eingeschränkt, ergänzt |
| Sendername aus üblichem Aufnahme-Dateinamen für Picon | Namensfallback unterstützt Standardmuster | ergänzt; heuristische Zuordnung |
| Aufnahme-/Live-Unterscheidung in Bibliothek | `recording_playback`, passender Medieninhaltstyp | ergänzt |
| Ausschalten nach Tiefschlaf | `off_mode`, zusätzlich explizite Geräteaktion | nun tatsächlich an den Ausschaltbefehl angebunden |
| Kanalbilder abschaltbar | `artwork: none`, alternativ Picon/Bildschirmfoto | ergänzt |
| Standard-Entity- und Plattform-Lifecycle | erster Refresh, Unload, gemeinsam verwaltete Session | ersetzt |

Der neue Code deckt damit den untersuchten **fachlichen Medienplayer-Umfang** ab und
erweitert ihn um acht weitere Plattformen, Sendernummernwahl, Medienbrowser, Timeraktionen
und die optionale Fernbedienungskarte. Das ist eine Funktionsbewertung anhand des Codes
und automatisierter Tests, keine Behauptung vollständiger Geräte-/Firmwaregleichheit.

Nicht übernommen werden alte Domains, Entity-IDs oder Attributnamen. Bestehende
Automationen werden daher nicht automatisch kompatibel. Das entspricht dem Ziel
eines neuen, eigenständigen Projekts.

## Wichtige Abgrenzungen im offiziellen Stand

**Wake-on-LAN:** Die HA-Methode delegiert an `OpenWebIfDevice.turn_on()`. In Version 4.3.1
steht ein Kommentar mit einem auskommentierten Wake-Aufruf; tatsächlich wird nur
der HTTP-Powerstate-Aufruf gesendet. Es gibt hier keine zusätzliche funktionierende
Wake-on-LAN-Implementierung, die unser Projekt übersehen hätte.

**Tiefschlaf-Option:** Die UI bietet sie an und der Medienplayer prüft
`device.turn_off_to_deep`. Im untersuchten Coordinator wird beim Aufbau von
`OpenWebIfDevice` jedoch nur die Bouquetoption übergeben. Der Bibliotheksstandard
für Tiefschlaf bleibt `False`. Eine dokumentierte Option und ihre tatsächliche
Verdrahtung sind daher getrennt zu beurteilen. Unser `off_mode` ist explizit verdrahtet
und durch einen Test des gesendeten `newstate=1` abgesichert.

**Kanalbild-Option:** Im untersuchten Code existiert das Optionsfeld, aber keine
sichtbare Verwendung im Medienplayer/Coordinator. Unser neuer Wert `none` unterbindet
sowohl Bild-URL als auch Bildabruf.

**Streaming:** Weder der untersuchte offizielle Medienplayer noch die neue Integration
stellen einen Browser-Streaming-Proxy oder Cast-Weiterleitung bereit. Die Bibliothek
kennt zusätzliche Endpunkte; Bibliotheksmethoden allein sind keine von HA angebotenen Funktionen.

**EPG-Zeiten:** Die offizielle Entität gibt u. a. formatierte Uhrzeitstrings weiter.
Die neue Integration verwendet Unix-Sekunden aus OpenWebif für Beginn/Ende, damit Datum
und Zeitbezug nicht verloren gehen. Dies ist eine bewusste neue Schnittstelle.

## Noch notwendige praktische Abnahme

Receiverseitig sind Standard- und Namenspicons, TV-/Radio-Bouquets, Wiedergabetasten,
Bildgrabber und Shutdown-Verhalten zu prüfen. Ein vorzeitig geschlossener HTTP-Kanal
beim Tiefschlaf wird von der neuen Integration nicht pauschal als Erfolg behandelt:
Ohne Bestätigung bleibt das Ergebnis unsicher. Die anschließende Erreichbarkeit wird
durch den normalen Coordinator ermittelt.
