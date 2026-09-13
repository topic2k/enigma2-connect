# Analyse und Zusammenführung

Stand: 12. September 2026. Gegenstand sind die lokalen Verzeichnisstände
`V:\homeassistant-enigma-player` und `V:\HAVUOpenWebif`.
Beide liegen hier ohne `.git`-Verzeichnis vor; Aussagen über Branches, ungespeicherte
Änderungen oder Commit-Historie sind deshalb nicht möglich. Die untersuchten Dateien
sind mit SHA-256 in [QUELLENBESTAND.json](QUELLENBESTAND.json) dokumentiert.

Die Funktionsanalyse basiert auf README **und** Implementierung. Beworbene Funktionen
sind nicht automatisch nachgewiesen. Es wurde keine Verbindung zu einem realen Receiver hergestellt.

Die spätere Ergänzung um die offizielle `enigma2`-Integration einschließlich ihrer
Bibliothek steht in [CORE-VERGLEICH.md](CORE-VERGLEICH.md). Herkunft und Lizenzen aller
Vorlagen wurden zusätzlich online geprüft; die verbindliche Projektentscheidung
in diesem Arbeitsstand steht in [LIZENZEN.md](LIZENZEN.md).

## 1. homeassistant-enigma-player

### Aufbau und Datenfluss

Die Domain `enigma` besteht aus drei Python-Modulen und einem Manifest:

- `__init__.py`: YAML-Schema `enigma.devices`, Erzeugung einer `EnigmaDevice`-Instanz je Receiver,
  Ablage in `hass.data`, Laden der Media-Player-Plattform über die ältere Discovery-Hilfe.
- `media_player.py`: komplette HTTP-Kommunikation, XML-Auswertung und Medienentität in einer Klasse.
- `notify.py`: eigenständige YAML-Notify-Plattform mit separater Host-/Auth-Konfiguration.

Ein Update fragt zunächst `/web/powerstate` ab. Beim Übergang aus Standby werden
Senderquellen aus einem vorgegebenen oder dem ersten Bouquet geladen. Danach folgen
aktueller Service, EPG und Lautstärke. XML wird mit BeautifulSoup verarbeitet.
Die Entität aktualisiert höchstens alle zehn Sekunden über `Throttle`.

### Tatsächlich vorhandene Funktionen

Standby ein/aus, Lautstärke/Stumm/Schritte, Senderwahl über die Media-Player-Quellenliste,
Sendernummern durch simulierte Zifferntasten, laufender EPG-Titel, Picon oder Bildschirmfoto,
HTTP Basic Auth und mehrere Geräte. Nachrichten werden über `/web/message` gesendet;
Typ und Anzeigedauer lassen sich pro Nachricht beeinflussen.

Wertvoll für das neue Projekt sind insbesondere die **direkte Quellenliste im Medienplayer**,
die **Sendernummernwahl** und die **Notify-Anbindung**. Diese fehlen in HAVU teilweise
oder sind dort nur als eigene Services vorhanden.

### Technische Schwächen

1. Netzwerk-, Parser-, Datenmodell- und Entity-Verantwortung sind vermischt.
2. `EnigmaDevice` erzeugt selbst eine `aiohttp.ClientSession`, ohne erkennbaren Unload-/Close-Pfad.
3. `request_call` fängt Fehler pauschal und liefert leeres XML. Ein Verbindungsfehler erscheint dadurch
   häufig als Standby, Folgezugriffe auf fehlende XML-Elemente können jedoch abbrechen.
4. Ein konfigurierbares Timeout existiert, wird bei authentifizierten Aufrufen aber durch den festen Wert 5 ersetzt.
5. Picon-/Screenshot-URLs können Benutzername und Passwort enthalten; diese landen potenziell in
   Zustandsattributen und Debug-Ausgaben (`media_image_url`).
6. Stummschalten ignoriert den gewünschten booleschen Zustand und sendet immer einen Toggle.
7. PLAY und PAUSE werden als Features gemeldet, die Methoden führen aber nur einen Logeintrag aus.
8. `async_turn_on` ruft `async_update()` ohne `await` auf.
9. Sendernamen dienen als Dictionary-Schlüssel; gleichnamige Sender überschreiben einander.
10. Nachrichten ersetzen nur Leerzeichen. Zeichen wie `&` oder `?` werden nicht als Queryparameter sauber kodiert.
11. Es fehlen Config Flow, Geräteeinträge, stabile Entity-IDs, Reauth, Diagnose und automatisierte Tests.

Nachprüfbare Stellen: `custom_components/enigma/__init__.py` (`async_setup`, `EnigmaDevice`),
`media_player.py` (`request_call`, `load_sources`, `async_update`, `async_media_play`,
`async_mute_volume`, `async_turn_on`), `notify.py` (`async_send_message`).

## 2. HAVUOpenWebif

### Aufbau und Datenfluss

Die Domain `havuopenwebif` ist bereits in API-Client, Coordinator, Config Flow und
acht HA-Plattformen aufgeteilt. `__init__.py` baut Client/Coordinator auf, lädt
Bouquets und registriert 15 eigene Aktionen. Laufzeitobjekte liegen in
`hass.data[DOMAIN][entry_id]`. Hinzu kommen DE/EN-Übersetzungen, Serviceschema,
Diagnoseexport und eine separate JavaScript-Fernbedienungskarte.

`openwebif.py` verwendet die JSON-Endpunkte `/api/...` und eine von HA gelieferte
HTTP-Session. Der Coordinator fragt standardmäßig alle 15 Sekunden Status, Signal,
Aufnahmeliste und Timer ab. Die Select-Entitäten besitzen dagegen eigene Senderdaten
und kommunizieren bei Bouquetwechsel über einen Dispatcher.

### Tatsächlich vorhandene Funktionen

- Medienplayer mit Lautstärke, Standby, EPG-Anzeige, Remote-Wiedergabetasten und Zap per Referenz.
- Remote-Sequenzen sowie einzelne Tasten- und Makro-Buttons.
- Sensoren, Status-Binary-Sensoren, Screenshot-Kamera.
- Zwei gekoppelte Auswahlentitäten für Bouquet/Sender.
- Timerkalender und Aktionen zum Anlegen, Löschen und Umschalten von Timern.
- Aufnahmeliste als Zähler; Abspielen einer Aufnahme über Zap.
- HTTP/HTTPS, Basic Auth, UI-Einrichtung, Intervalloption, SSDP-Ansatz, Diagnose.
- Dashboardkarte mit Tastenwiederholung bei Gedrückthalten.

Die breite Plattformabdeckung und die Trennung des API-Clients sind gute Ausgangsideen.
Die README beschreibt vor allem VU+ Uno 4K / VTi / OpenWebif 1.5.2; Modell und Hersteller
sind in mehreren Entity-Klassen fest eingebaut. Das ist keine allgemeine Geräteerkennung.

### Nachgewiesene bzw. aus dem Code erkennbare Schwächen

| Bereich | Befund | Auswirkung |
| --- | --- | --- |
| Aktionsziel | Ungültige oder fehlende `entry_id` fällt auf den ersten Eintrag zurück | Ein Befehl kann den falschen Receiver erreichen |
| Fehlersemantik | JSON-`result: false` wird nicht ausgewertet | Abgelehnte Timer/Befehle können als Erfolg erscheinen |
| Authentifizierung | Coordinator wandelt Authfehler in `UpdateFailed` um | Keine gezielte erneute Anmeldung |
| Standby | Vergleich ausschließlich mit String `"true"` | JSON-Boolean `true` wird falsch interpretiert |
| Aufnahme | Liest `inrecording`; aktuelles OpenWebif liefert `isRecording` | Aufnahmezustand bleibt fälschlich aus |
| Streaming | Leitet Streaming aus einem laufenden Sender ab | TV-Wiedergabe wird mit Netzwerkstream verwechselt |
| Nächste Sendung | Liest `next_title` aus `statusinfo` | Aktuelles OpenWebif liefert diese Information über `getcurrent.next` |
| Signal | Ruft `.replace` direkt auf `snr` auf | Numerische Antworten werden durch pauschales Catch zu unbekannt |
| Ressourcen | `free_memory` mischt freien Plattenplatz und RAM | Unterschiedliche Messgrößen ohne klare Einheit |
| Sicherheit | `stream_url` enthält Auth und wird als Attribut exportiert | Zugangsdaten im HA-Zustand |
| Mute | Ignoriert den Sollzustand | Wiederholtes „mute=true“ kann entstummen |
| Select | Initiales Dispatcher-Ereignis kann vor Anmeldung des Channel-Listeners eintreffen | Leere Senderliste beim Start möglich |
| Select-Zustand | Nach Laden wird der erste Sender als aktuell gesetzt | Anzeige muss nicht dem eingeschalteten Sender entsprechen |
| Polling | Komplette Aufnahmeliste in jedem aktiven Zyklus | Unnötige Receiver-/Datenträgerlast |
| Optionale Fehler | Fehler führen zu leeren Timer-/Aufnahmelisten | Falsche Nullwerte und verschwundene Kalendertermine |
| Kalender | Wiederholungsmaske und deaktivierte Timer werden nicht ausgewertet | Kalender bildet Aufnahmeplanung nicht vollständig ab |
| Kamera | `/api/grab` und nie nutzbar gemachter Screenshot-Service-Cache | Verhalten hängt vom Image ab; Service verwirft das geladene Bild |
| Remote | Meldet ACTIVITY ohne Aktivitätsimplementierung | Unzutreffendes Featureversprechen |
| Optionen | Weist `self.config_entry` selbst zu | Passt nicht zur aktuellen OptionsFlow-Verwaltung |
| Discovery | Generischer SatIP-Matcher und Host-Fallback auf ST | Auch nicht passende Geräte können angeboten werden |
| Diagnose | Redigiert nur einige Top-Level-Konfigurationsfelder | Rohdaten mit Sendern, Titeln und weiteren Adressen bleiben enthalten |
| Karte | Wiederholungs-Timer nur in lokaler Closure; kein Disconnect-Cleanup | Wiederholung kann nach Entfernen der Karte weiterlaufen |
| Paket | Platzhalter `@yourusername`/Repository-URLs; unbeschränktes aiohttp-Requirement | Noch kein sauber veröffentlichbares Paket |

Belege stehen in den entsprechenden Modulen unter `custom_components/havuopenwebif`
und `www/havuopenwebif-remote-card.js`. Zum Abgleich der Antwortfelder wurden die
offiziellen OpenWebif-Implementierungen für [Status und Signal](https://github.com/E2OpenPlugins/e2openplugin-OpenWebif/blob/master/plugin/controllers/models/info.py)
und [HTTP-Endpunkte](https://github.com/E2OpenPlugins/e2openplugin-OpenWebif/blob/master/plugin/controllers/web.py)
am Analysedatum gelesen. Receiver-Images können davon abweichen; das ersetzt keine Hardwareprüfung.

## 3. Schnittmengen und komplementäre Funktionen

| Fähigkeit | enigma | HAVU | Entscheidung für Enigma2 Connect |
| --- | --- | --- | --- |
| OpenWebif, lokales Polling, Auth | XML/HTTP | JSON/HTTP(S) | Ein asynchroner JSON-Client |
| Standby, Lautstärke, Sender, EPG | vorhanden | vorhanden | Ein normalisiertes Zustandsmodell |
| Medienplayer-Quellenliste | vorhanden | fehlt | Über gemeinsamen Katalog wieder aufnehmen |
| Sendernummer | Zifferntasten | beliebige Referenz per Zap | Beide Formen ausdrücklich unterstützen |
| Nachrichten | Notify-Plattform | Domain-Service | Moderne Notify-Entity plus parametrierbare Geräteaktion |
| Picon/Bildschirmfoto | Medienbild | Medienbild/Kamera | Gemeinsamer authentifizierter Bildtransport |
| Remote/Makros | eingeschränkt | vorhanden | Standard-Remote mit atomaren Sequenzen |
| Diagnose/Sensorik | fehlt | vorhanden, teils fehlerhaft | Nur belegbare Werte; Diagnose-Allowlist |
| Bouquetauswahl | feste Konfiguration | Select | Select plus Standard-Bouquetoption |
| Aufnahmen | fehlt | Zähler/Service | Zusätzlich Medienbrowser auf dem Receiver |
| Timer | fehlt | Kalender/Services | Kalender mit Wiederholungen plus validierte Geräteaktionen |
| Einrichtung | YAML | UI/SSDP | Neue UI-Konfiguration ohne Altlasten |
| Dashboardkarte | fehlt | vorhanden | Unabhängige Karte auf `remote.send_command` |

Beide Projekte modellieren denselben Receiver und dieselbe HTTP-Schnittstelle.
Zwei Clients, zwei Geräteeinträge oder eine Brücke zwischen alten Domains hätten keinen
fachlichen Nutzen. Die eigentliche Verschmelzung betrifft **Funktionen und Datenbesitz**.

## 4. Abgewogene Zusammenführungswege

**A – Dateien zusammenkopieren:** schnell, erzeugt aber zwei Konfigurationsmodelle,
doppelte Requests und widersprüchliche Zustände. Verworfen.

**B – HAVU forken und die drei fehlenden Kernfunktionen ergänzen:** weniger Umbau,
würde aber auch Modellfixierung, Lifecycle-, Fehler- und Targeting-Probleme bewahren.
Bei geforderter Rückwärtskompatibilität wäre ein schrittweiser Umbau denkbar.

**C – neue Integration mit klaren Zuständigkeiten:** gewählt. Keine Migration alter
IDs oder Services, ein neues Domain, ein Client je Receiver, gemeinsame Daten,
HA-Standardaktionen als primäre Bedienung. Die APIs und Nutzerfunktionen der
Vorgänger dienen als fachliche Referenz; Produktionsdateien wurden neu geschrieben.

## 5. Konkretes Ergebnis und bewusste Grenzen

Unter `V:\enigma2-connect` entsteht eine eigenständige lokale Git-Struktur mit Integration,
Dashboardkarte, Tests, CI und dieser Dokumentation. Es wird kein GitHub-Repository erstellt
und nichts in eine laufende HA-Installation kopiert.

Die neue Fassung implementiert die tragende Schnittmenge sowie Quellenliste,
Sendernummernwahl, Notify, Remote, Sensorik, Kamera, Auswahl, Timer und Medienbrowser.
Es gibt keine behauptete vollständige Parität: Discovery, Wake-on-LAN,
Temperatur-/Ressourcensensoren, rekursive Aufnahmeordner, Streaming-Proxy und frei
konfigurierbare Makro-Buttons sind als nächste Ausbauschritte dokumentiert.

Der alte Enigma-Snapshot enthält keinen ausgefüllten Lizenzabschnitt und keine
LICENSE-Datei; HAVU nennt MIT in der README, enthält aber ebenfalls keine LICENSE-Datei.
Es wurden deshalb keine ursprünglichen Produktionsdateien als Basis kopiert.
Das neue Projekt steht nach der erweiterten Lizenzprüfung unter **Apache-2.0** und
dokumentiert seine fachlichen Vorläufer in NOTICE. Die Detailbewertung unterscheidet
fehlende Lizenzfreigabe und unvollständige Dokumentation einer vorhandenen MIT-Erklärung.
