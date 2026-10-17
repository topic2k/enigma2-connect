# HA-Testlabor / HA test lab

[Deutsch](#deutsch) | [English](#english)

## Deutsch

Voraussetzungen: Python 3 und Docker mit Compose. Unter Windows Docker Desktop
mit Linux-Containern starten. Im Projektstamm:

```console
python scripts/ha_dev.py start
python scripts/ha_dev.py check
python scripts/ha_dev.py logs
python scripts/ha_dev.py stop
```

`start` installiert den aktuellen Ordner `custom_components/enigma2_connect`
vollständig in einer getrennten Home-Assistant-Instanz mit **HA 2026.10.1**.
Gelöschte Quelldateien verschwinden auch aus der installierten Integration.
HA wird dafür gestoppt; anschließend erledigt das Skript die Ersteinrichtung,
wartet auf den laufenden HA-Kern und prüft das Einrichtungsformular der Integration.
Es wird dabei kein Receiver eingerichtet oder angesprochen.

Öffne **http://127.0.0.1:18124** und melde dich mit dem öffentlichen Testzugang
**`enigma2connect` / `notsecret`** an. Über **Einstellungen → Geräte & Dienste →
Integration hinzufügen → Enigma2 Connect** kannst du einen erreichbaren Receiver
mit OpenWebif ab 2.4.0 hinzufügen. Verwende dessen LAN-Adresse; `localhost`
bezeichnet im Container den Container selbst. Für einen Dienst auf dem
Windows-Host kann `host.docker.internal` verwendet werden. Die Bedienung der
Integration und die optionalen Dashboardkarten erklärt das
[Benutzerhandbuch](../../docs/BENUTZERHANDBUCH.md).

Der Docker-Projektname ist `enigma2-connect-dev`, das Konfigurationsvolume heißt
`enigma2-connect-dev_config`. Port und Volume sind vom EnigmaHACompanion-Labor
getrennt; beide können gleichzeitig laufen. Benutzer, eingerichtete Receiver,
Dashboards und Datenbank bleiben bei `start` und `stop` erhalten. Bei jedem
`start` werden ausschließlich die Integrationsdateien ersetzt und die
mitgelieferte `configuration.yaml` erneut eingespielt. Eigene dauerhafte
YAML-Anpassungen deshalb in `dev/ha/configuration.yaml` vornehmen.
Nach Quelländerungen erneut `start` ausführen; es gibt kein automatisches Neuladen.
`check` prüft die Konfiguration im laufenden Container; `logs` zeigt die letzten
100 Logzeilen. Zum vollständigen Entfernen des Containers bei Erhalt der Daten:

```console
docker compose -f dev/ha/compose.yaml down
```

Ohne `--volumes` bleibt das Volume erhalten. Feste Testzugänge gelten nur für
dieses an Loopback gebundene Labor. Das Skript speichert lokale Anmeldedaten
und Tokens in der ignorierten `.work/ha-dev-access.json`; diese nicht weitergeben.
Wiederholte Starts setzen unterbrochene Ersteinrichtungen fort. Bereits vorhandene
Benutzer werden nicht zurückgesetzt. Fehlt die Zugangsdatei bei geändertem Login,
sie lokal mit `url`, `username` und `password` des bestehenden Labors anlegen;
`url` muss `http://127.0.0.1:18124` sein. Ungültige gespeicherte Refresh-Tokens
führen zu einem erneuten Login mit den gespeicherten Zugangsdaten.

Die Instanz startet ohne automatische Geräteerkennung und ohne Produktivzugänge.
Sie ist vom Host erreichbar; Docker kann ausgehende Verbindungen ins LAN aufbauen.
Nach dem manuellen Hinzufügen eines echten Receivers wirken Bedienaktionen auf
diesen Receiver. Das Labor simuliert keinen OpenWebif-Server. Die Portfreigabe
ermöglicht keinen direkten Zugriff anderer LAN-Geräte auf HA; externe Wiedergabe
und automatische Netzwerkerkennung benötigen gegebenenfalls eine gesonderte
Netzwerkkonfiguration und Praxisprüfung.

Das Image ist bewusst fest versioniert. Für eine andere HA-Version das Image in
`compose.yaml` ändern, erneut `start` und `check` ausführen und das Ergebnis
getrennt dokumentieren. Dieses Windows-Softwarelabor ersetzt keine
HAOS-/Supervisor-/Add-on-, Hardware- oder Mindestversionsprüfung.
Die offizielle [Container-Anleitung](https://www.home-assistant.io/installation/linux/#install-home-assistant-container)
beschreibt Docker Engine unter Linux; die hier verwendete Docker-Desktop-Umgebung
ist eine lokale Entwicklungshilfe. Nachweise und offene Prüfungen stehen in der
[Prüfübersicht](../../docs/VALIDIERUNG.md).

## English

Requires Python 3 and Docker with Compose. On Windows, start Docker Desktop with
Linux containers. Run the commands above from the repository root. `start`
installs the complete current `custom_components/enigma2_connect` directory into
an isolated **HA 2026.10.1** instance. Removed source files are removed from the
installed integration. It stops HA before replacing files, completes onboarding,
waits for HA to finish startup and verifies the integration's setup form.
It does not configure or contact a receiver.

Open **http://127.0.0.1:18124** and use the public test login
**`enigma2connect` / `notsecret`**. Add a reachable OpenWebif 2.4.0+ receiver via
**Settings → Devices & services → Add integration → Enigma2 Connect**.
Use its LAN address; `localhost` inside the container refers to the container.
Use `host.docker.internal` for a service on the Windows host. See the
[user guide](../../docs/USER_GUIDE.en.md) for integration controls and dashboard cards.

Docker project `enigma2-connect-dev` and volume `enigma2-connect-dev_config`
are separate from EnigmaHACompanion's lab; both can run together. Users,
receivers, dashboards and the database survive `start` and `stop`. Each `start`
replaces only integration files and reapplies the supplied `configuration.yaml`.
Make persistent YAML customizations in `dev/ha/configuration.yaml`.
Run `start` again after source changes; there is no automatic reload.
`check` validates configuration in the running container; `logs` prints the last
100 log lines. The `docker compose ... down` command above removes the container
while retaining data; omit `--volumes` to preserve the volume.

Fixed test credentials are exclusively for this loopback-only lab. Local login
details and tokens are stored in ignored `.work/ha-dev-access.json`; do not share
that file. Repeated starts resume interrupted onboarding and retain existing
accounts. If that file is missing and the login has changed, create it locally
with the existing lab's `url`, `username` and `password`; `url` must be
`http://127.0.0.1:18124`. Invalid saved refresh tokens trigger login using the
saved credentials.

No automatic device discovery or production credentials are configured. HA is
accessible from the host and Docker can connect out to LAN receivers. After
manually adding a physical receiver, controls affect that receiver. There is no
OpenWebif simulator. Other LAN devices cannot access HA through the loopback
port; external playback and automatic discovery may require separate network
configuration and acceptance checks.

The image is pinned deliberately. To test another HA version, change the image
in `compose.yaml`, run `start` and `check` again and document the result separately.
This Windows software lab does not establish HAOS, Supervisor, add-on, hardware
or minimum-version compatibility. The official
[Container guide](https://www.home-assistant.io/installation/linux/#install-home-assistant-container)
describes Docker Engine on Linux; this Docker Desktop setup is a local development
aid. See the [verification summary](../../docs/VALIDATION.en.md) for evidence and
outstanding checks.
