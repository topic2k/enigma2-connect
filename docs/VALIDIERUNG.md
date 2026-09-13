# Prüfstatus und Abnahme

Stand: 13.09.2026, lokale Version 0.1.0, Enigma2 Connect.

## Ausgeführte Prüfungen

| Prüfung | Ergebnis |
| --- | --- |
| Python-Tests gegen echtes Home Assistant 2026.9.1 | **97 bestanden**, 128,49 Sekunden |
| Abdeckung des Integrationscodes | **91 %** Statement-Coverage, 942 Anweisungen, 81 nicht ausgeführt |
| JavaScript-Verhalten der Fernbedienungskarte | **13 bestanden**: 5 Repository-Tests und 8 lokale Regressionen |
| Ruff-Codeprüfung | bestanden |
| Ruff-Formatprüfung | bestanden, einheitliche LF-Zeilenenden |
| Originalquellen | 36 Dateien gegen SHA-256-Bestand geprüft, unverändert |
| Metadaten | JSON/YAML, Python-Syntax, Übersetzungs-/Aktionsfelder und lokale Dokumentationslinks geprüft |

Die Python-Prüfung lief unter Ubuntu 22.04/WSL mit CPython **3.14.7**,
`pytest-homeassistant-custom-component==0.13.364` und Home Assistant **2026.9.1**.
Nur Receiver-Antworten und Transportaufrufe sind simuliert; Config Entries,
Registries, Entitätsplattformen und HA-Aktionen verwenden das reale Framework.
Die Ergebnisse der Umbenennungsprüfung stehen in `.work/rebranding-results.json`.
Das ältere Testprotokoll `.work/pytest-final.log` bleibt als historischer Nachweis erhalten.

Abgedeckt sind Einrichtung, Dubletten, Reauth/Reconfigure, Optionen, alle neun
Plattformen einschließlich tatsächlicher Zustandsanlage und Unload, Auth-/Netzwerkfehler,
optionale Endpunkte, Gerätezuordnung bei zwei Receivern, Befehlsvalidierung und
Serialisierung, Soll-Mute, Sendernummern, eindeutige Sendernamen, Bilder/Nachrichten,
Timerbereiche und wöchentliche Wiederholungen über den Sommerzeitwechsel.
Ergänzende Core-Vergleichstests prüfen TV-/Radio-Bouquets, frei konfigurierte
Bouquetreferenzen, EPG-/Aufnahmemetadaten, sichere Picon-Fallbacks sowie die tatsächlich
verdrahtete Tiefschlaf- und Bildabschaltoption.

Der Konfigurationsfluss wird zusätzlich auf die von Home Assistant an die Oberfläche
übergebene Probatio-Feldliste geprüft: Der Port ist erforderlich und vorbelegt,
Benutzername und Passwort bleiben ohne künstliche Leerwerte optional. Ein eigener
Transporttest bestätigt, dass ohne Benutzernamen kein Authorization-Header gesendet wird.

Die JavaScript-Tests prüfen Abbruch einer Wiederholung bei noch laufender Anfrage,
Stoppen nach einem Fehler und einmaliges Senden ohne Wiederholung. Sie ersetzen
keinen visuellen Dashboardtest auf Browsern oder Mobilgeräten.

Der abschließende Lauf enthält keinen Fehler beim Anlegen der Entitäten. Der gezielte
Offline-Test erzeugt erwartungsgemäß einen Coordinator-Fehler im Log. Warnungen über
Custom Integrations, optionale Kompressionsbibliotheken und langsame Tasks auf dem
WSL-Windows-Mount sind keine fehlgeschlagenen Tests. Es wird kein HA-Qualitätssiegel behauptet.

## Reproduzieren

Auf Linux mit Python 3.14.2 oder neuer im Repository:

```sh
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov=custom_components.enigma2_connect --cov-report=term-missing
node --test tests/frontend.test.cjs
```

Die wichtigsten Testwerkzeuge sind in `pyproject.toml` gepinnt; `uv.lock` fixiert
zusätzlich die transitiven Entwicklungsabhängigkeiten für reproduzierbare Prüfläufe.
Eine entsprechende GitHub-Actions-Konfiguration ist vorhanden. Hassfest wurde
zusätzlich lokal gegen Home Assistant 2026.9.1 ausgeführt: eine Integration,
null ungültige Integrationen. Die HACS-Aktion wird erstmals nach dem Push im
öffentlichen Repository ausgeführt.

Für die lokale WSL-Umgebung liegt `.work/run_tests.sh` bereit. Es verwendet ausschließlich
Testumgebung, Interpreter, temporäre Dateien und Caches unter `/mnt/v/enigma2-connect`.
`--capture=sys` vermeidet einen Fehler der dateideskriptorbasierten pytest-Ausgabenerfassung
auf diesem Windows-Mount. Alte Pfade in einigen Bibliotheks-Tracebacks stammen aus
mitverschobenen Bytecode-Dateien; die Module werden aus der verschobenen Umgebung geladen.

## Hardware- und Oberflächenabnahme

Die produktive Integration wurde an einem Octagon SF8008 4K Supreme mit OpenWebif
2.4.0 und einer Vu+ Solo² mit OpenWebif 1.4.4 geprüft. Am Octagon sind Live-TV und
Radio, Aufnahmewiedergabe, Picons/Bildgrabber, Fernbedienung, Nachrichten, Timer,
Kalender, normaler Standby, GUI-Neustart, Neustart und Tiefschlaf abgenommen. Die
Dashboardkarte wurde auf Desktop, Smartphone und Tablet, in hellen und dunklen
Oberflächen sowie hochkant und quer geprüft.

Die Solo² bestätigt die getrennte Gerätezuordnung, abweichende API-Felder, Katalog-,
Fernbedienungs-, Nachrichten- und Timerfunktionen. Wegen der derzeit fehlenden
DVB-S-Eingangsquelle ist dort noch keine zweite Abnahme von Bild, Ton, Empfangs-EPG,
Stream und echter Aufnahme möglich. Dieser zusätzliche Firmwaretest blockiert die
Veröffentlichung der bereits mit realer Hardware geprüften Version nicht.

Browser-Videostreaming, Cast, Wake-on-LAN, automatische Erkennung und die Anlage neuer
wiederkehrender Timer sind kein implementierter Umfang dieser Version. Details und
weitere bewusste Abgrenzungen stehen in README und Funktionsvergleich.

Projekt-/Issue-URLs und Codeowner verweisen auf das bestätigte öffentliche Repository
[`topic2k/enigma2-connect`](https://github.com/topic2k/enigma2-connect). Die offiziellen
HACS- und Hassfest-Workflows sind vorbereitet; der repositorybezogene Lauf folgt mit
dem ersten Push. Version 0.1.0 ist zunächst für die Installation als benutzerdefiniertes
HACS-Repository vorgesehen. Eine HACS-Standardlistung oder vollständige Erfüllung aller
HA-Qualitätsregeln wird nicht behauptet.

## Dateibestand und Bereinigung

Das neue Git-Repository, der Produktionscode, die Dokumentation und die laufenden
Testwerkzeuge befinden sich unter **`V:\enigma2-connect`**. Die vorher erstellten Verzeichnisse
`.enigma2-ha-build`, `.enigma2-ha-research` und der aufgabenbezogene Ruff-Cache wurden
aus dem alten Repository dorthin verschoben. Beide ursprünglichen Repository-Inhalte
sind unverändert; der Quellenindex enthält ausschließlich ihre 36 Originaldateien.

Nach ausdrücklicher Benutzerfreigabe wurden die verbliebenen Bestände aus der
ursprünglichen Testinstallation in WSL **Ubuntu-22.04** entfernt:

- `/home/topic/.cache/uv`
- `/home/topic/.local/share/uv/python`

Dies umfasst die Laufzeit `cpython-3.14.7-linux-x86_64-gnu`, den darauf zeigenden
Alias `cpython-3.14-linux-x86_64-gnu`, `.lock`, `.gitignore` und das temporäre
Unterverzeichnis. Die ursprünglichen Aufgabenaufrufe und
Erstellungszeiten sind in `.work/relocation-evidence.md` festgehalten.
Der vorbestehende Windows-Cache unter `C:\Users\topic\AppData\Local\uv\cache`
wird nicht als aufgabenexklusiver Bestand behandelt und bleibt erhalten.

Die beiden Linux-Verzeichnisse sind für eine überprüfbare Bereinigung in
`.work/external-linux-artifacts.tar.gz` gesichert und jede reguläre Archivdatei wurde
per SHA-256 mit dem Original verglichen. Das Archiv umfasst 73.326 Einträge;
Prüfdetails und Löschzeitpunkt stehen daneben in `external-linux-artifacts.json`.
Vor der Entfernung wurde die SHA-256-Prüfsumme des Sicherungsarchivs erneut bestätigt.
Die Testumgebung dieses Projekts verwendet die Zielkopie unter `V:\enigma2-connect`.

Die beiden vom Installer eingefügten Zeilen in `.profile` und `.bashrc` wurden
gezielt entfernt. Die ausschließlich auf diese Aufgabe verweisende `uv.env.fish`
liegt jetzt ebenfalls nur als Sicherung unter `.work/installer-profile-backups`.

Die Bereinigung der außerhalb des Zielverzeichnisses angelegten Projekt- und
Testbestände ist damit **abgeschlossen**. Die ursprüngliche automatische Ablehnung
wurde durch die ausdrückliche Freigabe für diese Linux-Dateien geklärt.

## Branding-Exporte

Das ausgewählte Motiv „Integriert“ wird als acht transparente PNGs unter
`custom_components/enigma2_connect/brand/` mitgeliefert. Vektorquellen, Vorschau,
Abmessungs-/Alphaprüfung und Reproduktionsanleitung stehen in
[docs/branding/README.md](branding/README.md). Die Darstellung auf hellen und
dunklen Flächen sowie bei kleinen Icon-Größen wurde visuell geprüft.
Die lokalen Brandgrafiken wurden nach Installation in laufendem Home Assistant auf
der Integrations- und Geräteseite erfolgreich dargestellt.

