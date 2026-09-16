[Deutsch](RELEASING.md) | [English](RELEASING.en.md)

# Veröffentlichung

Neue Worktrees für dieses Projekt liegen immer unter `V:\enigma2-connect-worktrees`.

## Inhaltsverzeichnis

- [Entwicklung und Branches](#entwicklung-und-branches)
- [Version vor dem Pull Request](#version-vor-dem-pull-request)
- [Prüfungen](#prüfungen)
- [Release veröffentlichen](#release-veröffentlichen)

Entwicklungsumgebung und Projektaufbau stehen in der
[Entwicklerdokumentation](docs/ENTWICKLUNG.md).

## Entwicklung und Branches

Es gelten die [Projektvorgaben](AGENTS.md), übernommen aus BT-RC.
Für jede Aufgabe vom aktuellen `develop` einen eigenen, passend benannten Branch
anlegen. Kleine Änderungen im bestehenden Arbeitsverzeichnis bearbeiten;
für umfangreichere Aufgaben zusätzlich einen eigenen Worktree erstellen.
Fertige Änderungen nach passenden Prüfungen auf dem Arbeitsbranch committen,
nach `develop` übernehmen und `develop` pushen; dafür ist keine weitere Freigabe nötig.
`develop` sammelt abgeschlossene Änderungen. Keine direkte Implementierung auf
`develop` oder `main`.

Erst nach ausdrücklicher Nutzerfreigabe den gesammelten Stand für einen Pull Request
von `develop` nach `main` vorbereiten und den PR eröffnen. Die Übernahme nach `main`
erfolgt ausschließlich über diesen PR und benötigt ebenfalls die Nutzerfreigabe.
Ein Release einschließlich Entwurf oder Tag benötigt eine separate ausdrückliche
Anweisung; eine PR- oder Merge-Freigabe ist keine Release-Freigabe.

Die Version automatisch anhand des gesamten unveröffentlichten Umfangs seit dem
letzten stabilen Release erhöhen: Patch für Korrekturen, interne Änderungen und
Dokumentation, Minor für rückwärtskompatible neue Funktionen, Major für inkompatible
Änderungen. Entwicklungsstände heißen `X.Y.Z-dev.N`, beginnend mit `dev.1`.
Weitere abgeschlossene Änderungen derselben Zielversion erhöhen den Zähler;
eine höhere Zielversion beginnt wieder mit `dev.1`. Nicht pro Dateiedit erhöhen.

Diese Versionsstellen gemeinsam pflegen:

- `custom_components/enigma2_connect/manifest.json`: `version`.
- `pyproject.toml`: `project.version`, dieselbe vollständige Versionskennung.
- `uv.lock`: lokales Paket `enigma2-connect`, bei Entwicklungsversionen in der
  normalisierten Python-Schreibweise `X.Y.Z.devN`.
- Neuester Eintrag und Inhaltsverzeichnis von [CHANGELOG.md](CHANGELOG.md) und
  [CHANGELOG.en.md](CHANGELOG.en.md).

Beide Changelogs beginnen mit einem Inhaltsverzeichnis und führen die neueste
Version zuerst. Bei jeder relevanten Änderung den Eintrag der Zielversion
fortschreiben und ausdrücklich als unveröffentlichte Entwicklerversion markieren.
Veröffentlichte Historie erhalten; keine Versionshistorie in der README duplizieren.

Die lokale Ausgangsfassung `0.1.0` ist auf `main` vergeben. Bei Einführung dieser
Regeln ergeben die zusätzlich vorhandenen Funktionen die Zielversion `0.2.0-dev.1`.
Das ist keine Aussage über eine erfolgte Veröffentlichung; vor einem PR muss die
tatsächliche Remote- und Release-Basis erneut geprüft werden.

## Version vor dem Pull Request

1. Unmittelbar vor jedem PR nach `main` Remote-Branches und Tags abrufen, etwa mit
   `git fetch origin --prune --tags`, und die veröffentlichten GitHub-Releases
   prüfen. Lokale Versionsangaben oder Tags allein reichen nicht.
2. Die passende Version anhand des letzten stabilen Releases und aller vorgesehenen
   Änderungen neu bestimmen. Solange noch kein stabiles Release existiert, die
   vorhandene Version auf `main` als Ausgangsbasis verwenden. Zwischenzeitliche
   Versionsanhebungen anderer Branches berücksichtigen. Keine bereits veröffentlichte
   oder auf `main` vergebene Version erneut verwenden und keine Version absenken.
3. Noch auf dem Quellbranch das vollständige `-dev.N` entfernen, alle Versionsstellen
   einschließlich Lockdatei und beide Changelog-Inhaltsverzeichnisse synchronisieren.
   Den Eintrag weiterhin als unveröffentlicht kennzeichnen; nur die Kennzeichnung
   als Entwicklerversion entfällt. Betroffene lokale Prüfungen ausführen;
   die vollständigen CI-Ergebnisse müssen vor dem Merge erfolgreich vorliegen.
4. Ohne aktuellen Remote-Abgleich ist die Vorbereitung unvollständig. Ändert sich
   `main` oder die Release-Basis während des offenen PR, den Abgleich vor dem Merge
   wiederholen und Anpassungen im Quellbranch vornehmen. Erst nach Nutzerfreigabe mergen.

Eine Version ohne Entwicklungssuffix und ein Merge erlauben keine automatischen
Tags, Release-Entwürfe oder Veröffentlichungen.

## Prüfungen

Vor der Übernahme nach `main` müssen alle erforderlichen CI-Prüfungen für den
aktuellen PR-Stand erfolgreich sein. Alle Integrationsqualitätsvorgaben müssen
weiterhin erfüllt bleiben; der erreichte Qualitätsstatus darf sich gegenüber dem
bisherigen Stand und dem aktuellen `main` nicht verschlechtern.

Die [Qualitätscheckliste](custom_components/enigma2_connect/quality_scale.yaml)
auf Auswirkungen der Änderung prüfen. Nicht durch CI abgedeckte, von der Änderung
betroffene Anforderungen zusätzlich prüfen und Nachweise in beiden Prüfübersichten
aktualisieren. Erfüllte Kriterien, Testabdeckungsgrenzen und Prüfstrenge nicht
absenken oder durch unbegründete Ausnahmen umgehen. Verschlechterungen und fehlende
erforderliche Nachweise sperren den Merge; grüne CI allein belegt nicht die
inhaltliche Erfüllung aller Qualitätskriterien.

Lokal genügen zur Änderung passende, gezielte Prüfungen. Bereits durch aktuelle
CI-Ergebnisse belegte Prüfungen müssen nicht vollständig lokal wiederholt werden.
Ein PR darf zur Ausführung der CI eröffnet werden. Bei Änderungen am Quellbranch
oder an `main` vor dem Merge aktuelle CI-Ergebnisse für den daraus entstehenden
PR-Stand sicherstellen und den Qualitätsabgleich für betroffene Anforderungen erneuern.

Die vollständigen Prüfbefehle dienen als Referenz und zur Fehleranalyse; je nach
Änderung die passenden auswählen. Unter Linux/WSL mit Python ab 3.14.2 im Projektverzeichnis:

```sh
uv sync --locked --group dev
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
uv run --locked pytest --cov=custom_components.enigma2_connect --cov-branch --cov-report=term-missing --cov-report=json:coverage.json
uv run --locked python scripts/check_config_flow_coverage.py coverage.json --silver
uv run --locked python -m compileall -q custom_components tests
node --test tests/frontend.test.cjs
git diff --check
```

Nach einer Versionsänderung `uv lock --offline` ausführen und prüfen, dass nur die
erwarteten Projektmetadaten angepasst werden. Abhängigkeiten nicht beiläufig aktualisieren.
Versionsstellen und beide Changelogs einschließlich Sprachlinks prüfen.
Die Workflows `.github/workflows/tests.yml` und `.github/workflows/validate.yml`
prüfen Tests, Ruff, Typen, Testabdeckung, Hassfest und HACS. Vor jedem Merge müssen
die Jobs `test`, `hassfest` und `hacs` erfolgreich sein. Für eine technische
Merge-Sperre müssen diese Checks zusätzlich in den GitHub-Schutzregeln für `main`
verpflichtend hinterlegt sein; die Workflow-Dateien allein erzwingen das nicht.
Für ein Release müssen die Prüfungen für den tatsächlich zu veröffentlichenden
Commit erfolgreich sein.

Prüfumfang, bekannte Grenzen und Hardware-Ergebnisse stehen in
[der Prüfübersicht](docs/VALIDIERUNG.md). Neue Funktionen zusätzlich in
Home Assistant mit den betroffenen Receivern und beiden Oberflächensprachen prüfen.
Bestehende Prüfberichte belegen ihren dokumentierten Stand; sie gelten nicht
automatisch für spätere Änderungen. Simulierte Tests sind keine Hardwareabnahme.

## Release veröffentlichen

Voraussetzung ist eine ausdrückliche Release-Anweisung des Nutzers. Sie ist auch
für Release-Entwürfe und Release-Tags erforderlich.

1. Version und vorgesehenen Commit auf `main` prüfen. Ausstehende Änderungen nach
   dem Ablauf [Version vor dem Pull Request](#version-vor-dem-pull-request) vorbereiten.
2. Im Rahmen der beauftragten Veröffentlichung die Unveröffentlicht-Kennzeichnung
   in beiden Changelogs entfernen. Auch diese Änderung auf einem Arbeitsbranch
   vorbereiten und nach Nutzerfreigabe per PR übernehmen. Versionsabgleich wiederholen;
   die reine Freigabe des bestehenden Eintrags begründet keine neue Produktversion.
3. Erfolgreiche CI und den tatsächlichen Hardware-Prüfumfang für den Release-Commit
   kontrollieren und dokumentieren. Manifest, Projektmetadaten, Lockdatei und beide
   Changelogs müssen dieselbe stabile Version `X.Y.Z` enthalten.
4. Den geprüften Commit auf `main` mit dem annotierten Tag `vX.Y.Z` markieren und
   diesen Tag übertragen. Ein Tag allein ist kein veröffentlichtes GitHub-Release.
5. Im Repository `topic2k/enigma2-connect` ein GitHub-Release zum Tag `vX.Y.Z` mit
   dem Titel `X.Y.Z` erstellen. Die zugehörigen Abschnitte beider Changelogs als
   zweisprachige Release-Beschreibung verwenden und als reguläres Release veröffentlichen.

Ein beauftragter Entwurf bleibt bis zu den erfolgreichen Prüfungen unveröffentlicht.
Bei Änderungen Ziel-Commit und zweisprachige Beschreibung aktualisieren.
ZIP-Dateien nur auf ausdrücklichen Wunsch erzeugen. Die Integration liegt unter
`custom_components/enigma2_connect`; die optionale Karte unter `www/` wird separat
installiert, siehe [Benutzerhandbuch](docs/BENUTZERHANDBUCH.md#fernbedienung-im-dashboard).
Lokale Dateien unter `.work/` und `.local-archive/` nicht verteilen.
Die Lizenz bleibt Apache-2.0. HACS-Installation und Paketgrenzen beschreibt die
[Entwicklerdokumentation](docs/ENTWICKLUNG.md#dateibestand-und-lokale-archive); die HACS-Standardlistung ist
ein separater Schritt.
