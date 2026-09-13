# Veröffentlichungsprüfung 0.1.0

Stand: **13.09.2026**

Ziel ist das öffentliche Repository
[`topic2k/enigma2-connect`](https://github.com/topic2k/enigma2-connect). Die erste
Version ist für die Installation als benutzerdefiniertes HACS-Repository vorgesehen;
eine Aufnahme in den HACS-Standardkatalog ist nicht Teil dieser Veröffentlichung.

## Automatische Prüfungen

- 97 Python-Tests unter Home Assistant 2026.9.1 und Python 3.14.7 bestanden.
- Ruff-Prüfung und Formatprüfung bestanden.
- Fünf Repository-Frontendtests bestanden.
- Hassfest gegen Home Assistant 2026.9.1: eine Integration, null ungültige Integrationen.
- GitHub-Workflows für Tests, Hassfest und die offizielle HACS-Aktion sind vorhanden.

Die HACS-Aktion benötigt den GitHub-Kontext und läuft deshalb erstmals nach dem
ersten Push. Das lokale Paketprüfskript kontrolliert bis dahin dieselben wesentlichen
Metadaten sowie den tatsächlich sichtbaren Git-Dateibestand.

## Paketgrenzen

Git enthält genau `custom_components/enigma2_connect` als Integration. Lokale
Hardwareberichte, Zugangsdaten, Receiver-Adressen, Testumgebungen und Caches liegen
unter `.work/` und sind ausgeschlossen. Das Laufzeitmanifest hat keine zusätzlichen
Python-Anforderungen, weil die verwendeten Pakete bereits von Home Assistant
bereitgestellt werden.

## Live-Prüfung

Die installierte Version wurde mit einem Octagon SF8008 4K Supreme und einer Vu+
Solo² betrieben. Beide Konfigurationseinträge lassen sich getrennt neu laden. Nach
einem vollständigen Home-Assistant-Neustart waren wieder genau zwei Geräte mit je
64 Entitäten vorhanden. Die Receiver-Identitäten blieben getrennt; Timer und
Aufnahmen waren vor und nach dem Neustart unverändert.

Die Solo² wurde entfernt und neu eingerichtet. Danach waren wieder genau zwei Geräte
mit je 64 Entitäten vorhanden; es entstanden keine Dubletten. Der Receiverbestand blieb
unverändert. Ein zusätzlicher Regressionstest stellt sicher, dass Benutzername und
Passwort im HTTP-Konfigurationsfluss leer bleiben dürfen.

## Lizenz

Projektcode und mitgelieferte Laufzeitdateien stehen unter Apache-2.0. Alle Python-
und JavaScript-Quelldateien tragen den passenden SPDX-Hinweis. Der Poppins-Font wird
nur als Branding-Quellmaterial zusammen mit seinem OFL-1.1-Text mitgeliefert. Keine
Produktionsdatei aus den untersuchten, unklar lizenzierten Vorgänger-Repositories ist
enthalten. Einzelheiten und festgehaltene Quellstände stehen in
[`LIZENZEN.md`](LIZENZEN.md).
