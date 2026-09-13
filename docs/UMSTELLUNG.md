# Umstellung auf Enigma2 Connect

Das Projekt heißt jetzt **Enigma2 Connect**. Die Umbenennung betrifft auch die
technischen Kennungen der bisherigen lokalen Fassung „Enigma2 HA“.

| Bereich | Bisher | Jetzt |
| --- | --- | --- |
| Projektordner / Repositoryname | `enigma2-ha` | `enigma2-connect` |
| Integrationsdomain / Python-Paket | `enigma2_ha` | `enigma2_connect` |
| Installationsordner | `custom_components/enigma2_ha` | `custom_components/enigma2_connect` |
| Eigene Aktionen | `enigma2_ha.*` | `enigma2_connect.*` |
| Kartenmodul | `enigma2-ha-remote-card.js` | `enigma2-connect-remote-card.js` |
| Dashboard-Kartentyp | `custom:enigma2-ha-remote-card` | `custom:enigma2-connect-remote-card` |

## Bestehende Home-Assistant-Installation

Die neue Domain ist für Home Assistant eine separate Integration. Es gibt keine
automatische Übernahme der alten Config Entries oder Kompatibilitätsalias-Domain.
Eine reine Umbenennung des installierten Ordners reicht deshalb nicht aus.

1. Home-Assistant-Backup erstellen. Receiver-Verbindungsdaten, Optionen sowie
   verwendete Entitäts- und Geräte-IDs notieren. Betroffene Automationen vorübergehend
   deaktivieren.
2. Die bisherigen Einträge von **Enigma2 HA** unter **Einstellungen → Geräte & Dienste**
   entfernen. Den alten Ordner `/config/custom_components/enigma2_ha` entfernen.
3. `custom_components/enigma2_connect` nach
   `/config/custom_components/enigma2_connect` kopieren und Home Assistant neu starten.
4. **Enigma2 Connect** hinzufügen und jeden Receiver mit seinen bisherigen
   Verbindungsdaten und Optionen neu einrichten.
5. In Automationen und Skripten eigene Aktionsnamen auf `enigma2_connect.*` umstellen,
   beispielsweise `enigma2_connect.timer_add`. Geräte- und Entitätsreferenzen anhand
   der neu eingerichteten Integration prüfen und gegebenenfalls aktualisieren.
   Identische IDs und die Übernahme der Historie werden nicht zugesichert.
6. Für die Fernbedienungskarte das neue Modul nach
   `/config/www/enigma2-connect-remote-card.js` kopieren. Die alte Dashboard-Ressource
   durch `/local/enigma2-connect-remote-card.js` als JavaScript-Modul ersetzen und den
   Kartentyp auf `custom:enigma2-connect-remote-card` ändern. Die neue Remote-Entität
   auswählen und den Browser neu laden. Das alte Kartenmodul kann entfernt werden.
7. Funktion und Referenzen prüfen, anschließend die Automationen wieder aktivieren.

Standardaktionen wie `remote.send_command`, `media_player.media_play` und
`notify.send_message` behalten ihre Namen; ihre Ziele müssen zur neuen Einrichtung passen.

## Lokale Entwicklung

Der neue Projektpfad ist `V:\enigma2-connect`, in WSL `/mnt/v/enigma2-connect`.
Gespeicherte Editor-Projekte und Terminals müssen diesen Ordner verwenden.
Python-Imports, Paketmetadaten, CI, Testaufrufe, Kartenregistrierung und aktuelle
Dokumentation verwenden die neuen Namen. Die lokale Testumgebung liegt weiterhin
im Projekt unter `.work`.

Historische Testprotokolle, Sicherungen und alte Logoentwürfe behalten ihre damaligen
Bezeichnungen. Die alten Entwürfe liegen unter `branding/archive/enigma2-ha`.
Diese Bestände dienen der Nachvollziehbarkeit und gehören nicht zur aktiven Integration.

Es ist noch kein Git-Remote konfiguriert. Ein veröffentlichtes Repository wurde
daher nicht umbenannt; `enigma2-connect` ist der vorgesehene Repositoryname.
