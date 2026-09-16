[Deutsch](AGENTS.md) | [English](AGENTS.en.md)

# Projektvorgaben

## Projekt

Enigma2 Connect ist eine Home-Assistant-Custom-Integration für Enigma2-Receiver
mit OpenWebif. Ziel: Home Assistant ab 2026.9, Python ab 3.14.2.
Der Projektcode steht unter Apache-2.0. Vorhandene fremde Änderungen erhalten.

## Changelog und Release-Dokumentation

Diese Vorgaben für Versionierung, Changelog, Releases und Branching entsprechen BT-RC.
Diese Projektvorgaben, [RELEASING.md](RELEASING.md) und [CHANGELOG.md](CHANGELOG.md)
zusammen mit ihren englischen Fassungen pflegen. Die Sprachfassungen verlinken
einander. Beide Changelogs beginnen mit einem Inhaltsverzeichnis, führen die
neueste Version zuerst und erhalten bei jeder relevanten Änderung einen Eintrag.
Den Eintrag der aktuellen Zielversion fortschreiben; veröffentlichte Historie erhalten.
Changelogs enthalten ausschließlich Versionshistorie; diese nicht in der README
duplizieren. Die README beschreibt das aktuelle Verhalten und verlinkt Changelog
und Release-Anleitung. Technische Details und Prüfberichte stehen in `docs/`.
Simulierte Tests von tatsächlichen Receiver- und Home-Assistant-Prüfungen unterscheiden.

Die README bleibt eine kurze, leicht verständliche Einführung aus Anwendersicht
mit den wichtigsten Informationen. Ausführliche Bedienungsanleitungen stehen in
[BENUTZERHANDBUCH.md](docs/BENUTZERHANDBUCH.md), wichtige Entwicklerinformationen
in [ENTWICKLUNG.md](docs/ENTWICKLUNG.md). Die gemeinsame `README.md` enthält
Deutsch zuerst und danach Englisch mit Sprunglinks zu beiden Abschnitten.
Benutzerhandbuch und Entwicklerdokumentation behalten getrennte deutsche und
englische Dateien, deren Sprachfassungen sich gegenseitig verlinken.

Das Benutzerhandbuch erklärt Aufgaben mit einfachen Bedienungsschritten und den
Bezeichnungen der Oberfläche. Aktionen und YAML-Anwendungsbeispiele gehören im
Benutzerhandbuch zum Kapitel „Nachrichten und Automationen“. API-Implementierung
und technische Sonderfälle in der Entwicklerdokumentation bündeln. `docs/` schlank halten:
Handbücher, aktuelle Prüfübersicht und wichtige Lizenznachweise. Alte Analysen,
Prüfprotokolle und verworfene Entwürfe bei Bedarf vollständig und überprüfbar
unter `.local-archive/` archivieren; dieser Ordner bleibt per `.gitignore` lokal.
Benötigte Informationen vorher in die aktive Dokumentation übernehmen und Links
aktualisieren. Aktive Branding-Quellen samt Schriftlizenz liegen in `assets/branding/`.

## Versionsstellen

Die Integrationsversion steht in `custom_components/enigma2_connect/manifest.json`.
Zusätzlich `pyproject.toml` und das lokale Paket `enigma2-connect` in `uv.lock`
synchron halten. Eine separate Konstante `INTEGRATION_VERSION` gibt es hier nicht.
Manifest, Projektmetadaten und beide Changelogs verwenden `X.Y.Z-dev.N`;
`uv.lock` verwendet die gleichwertige normalisierte Python-Schreibweise `X.Y.Z.devN`.
Stabile Versionen heißen überall `X.Y.Z`. Nach Änderungen die Lockdatei prüfen.
Bis zur ersten stabilen Veröffentlichung gilt die vorhandene Version auf `main`
als Ausgangsbasis, ohne sie als veröffentlichtes Release darzustellen. Aus der
initialen `0.1.0` auf `main` und unveröffentlichten neuen Funktionen ergibt sich
bei Einführung dieser Regeln `0.2.0-dev.1`; der Remote-Abgleich vor einem PR
bleibt verpflichtend.

## Branches, Freigabe und Releases

- Neue Worktrees für dieses Projekt immer unter `V:\enigma2-connect-worktrees` anlegen.
- Änderungen zuerst auf `develop` oder bei Bedarf auf einem neuen Arbeitsbranch
  umsetzen; keine direkten Änderungen oder Commits auf `main`.
- Änderungen erst nach ausdrücklicher Freigabe durch den Nutzer und ausschließlich
  per Pull Request nach `main` übernehmen.
- Ein neues Release nur auf ausdrückliche Anweisung des Nutzers erstellen.
  Die Freigabe von Änderungen oder eines Pull Requests ist keine Release-Freigabe.
- Die folgenden Versionierungsregeln erlauben keine automatische Veröffentlichung.

## Versionierung

- Bei Änderungen auf `develop` oder einem Arbeitsbranch die Version automatisch
  und ohne gesonderte Aufforderung passend zum gesamten unveröffentlichten Umfang
  gegenüber der letzten stabilen Version erhöhen: Patch für Fehlerkorrekturen,
  interne Änderungen und reine Dokumentation, Minor für rückwärtskompatible neue
  Funktionen, Major für inkompatible Änderungen.
- Entwicklungsstände verwenden `X.Y.Z-dev.N`, beginnend mit `dev.1`, zum Beispiel
  `1.1.0-dev.1`. Bei weiteren abgeschlossenen Änderungen an derselben Zielversion
  den Zähler erhöhen; bei einer höheren Zielversion wieder mit `dev.1` beginnen.
  Nicht für jeden einzelnen Dateiedit eine neue Version vergeben.
- `version` in `manifest.json`, `version` in `pyproject.toml` und der neueste Eintrag in
  beiden Changelogs müssen einschließlich Entwicklungssuffix übereinstimmen.
  Den Changelog-Eintrag ausdrücklich als unveröffentlichte Entwicklerversion
  kennzeichnen und bei weiteren Änderungen derselben Zielversion fortschreiben.
- Unmittelbar vor jedem Pull Request nach `main` den aktuellen Remote-Stand von
  `main`, die Tags und die veröffentlichten Releases abrufen. Die nächste passende
  Version anhand des letzten stabilen Releases und des gesamten vorgesehenen
  Änderungsumfangs neu bestimmen. Zwischenzeitliche Versionsanhebungen durch
  andere Branches oder Commits berücksichtigen; keine bereits veröffentlichte
  oder auf `main` vergebene Version erneut verwenden und keine Version absenken.
- Noch auf dem Arbeitsbranch das vollständige Suffix `-dev.N` entfernen und
  Manifest, `version` in `pyproject.toml`, beide Changelogs und deren Inhaltsverzeichnisse
  synchronisieren. Den Eintrag bis zur Veröffentlichung als unveröffentlicht,
  aber nicht mehr als Entwicklerversion kennzeichnen. Danach die Prüfungen erneut
  ausführen. Ohne aktuellen Remote-Abgleich ist diese Vorbereitung unvollständig.
- Wenn sich `main` oder die Release-Basis während eines offenen Pull Requests
  ändert, den Versionsabgleich vor dem Merge wiederholen und nötige Anpassungen
  im Quellbranch vornehmen. Die Übernahme erfolgt erst nach Nutzerfreigabe.
  Eine Version ohne Entwicklungssuffix oder ein Merge erlaubt keine automatischen
  Tags oder Releases; dafür bleibt eine ausdrückliche Release-Anweisung nötig.

## Entwicklungsregeln

Vor Änderungen:
1. Bestehenden Code analysieren.
2. Bestehende Funktionalität nachvollziehen.
3. Einen kurzen Implementierungsplan erstellen.

Nach Änderungen:
1. Tests ausführen.
2. Python-Syntax prüfen.
3. Home-Assistant-Kompatibilität prüfen, soweit lokal möglich.
4. Betroffene Dokumentationen und Changelogs in beiden Sprachen aktualisieren.
5. Keine ZIP-Datei erzeugen, sofern nicht ausdrücklich verlangt.
