# Lizenzprüfung und Entscheidung

Prüfdatum: **12.09.2026**. Grundlage sind die lokalen Vorlagen, die angegebenen
öffentlichen Repository-Stände, Lizenztexte und die tatsächlich in das neue Projekt
geschriebenen Dateien. Dies ist eine technische Lizenzbewertung, keine verbindliche
juristische Freigabe oder vollständige Prüfung sämtlicher historischer Urheberrechte.

## Entscheidung: Apache-2.0

Der **neu geschriebene Projektcode wird unter Apache License 2.0 veröffentlicht**.
Die zuvor vorläufig eingetragene MIT-Lizenz wurde vor Veröffentlichung ersetzt.
`LICENSE`, `NOTICE`, SPDX-Kopfzeilen und `pyproject.toml` dokumentieren diese Entscheidung.

Apache-2.0 ist nicht allein deshalb zwingend, weil eine Custom Integration in
Home Assistant läuft. Die bewusste Wahl schafft jedoch ein einheitliches Lizenzmodell
mit HA Core und enthält eine ausdrückliche Patentlizenz. Zulässige spätere Übernahmen
aus HA Core lassen sich unter Wahrung von Lizenz-, Änderungs- und Urheberhinweisen
integrieren. Grundlage ist der [offizielle Apache-2.0-Lizenztext](https://www.apache.org/licenses/LICENSE-2.0).

**Eine neue Projektlizenz löst keine fehlenden Rechte an fremdem Code.** Deshalb wurden
keine Produktionsdateien aus dem nicht eindeutig lizenzierten älteren Enigma-Projekt
übernommen. Die neue Architektur und Implementierung wurden anhand der Funktionen
und Protokollschnittstellen neu geschrieben. Dies ist keine behauptete formale
Clean-Room-Entwicklung: Die Vorlagen wurden ausdrücklich zur Analyse gelesen.

## Befunde je Repository

| Quelle und geprüfter Stand | Lizenzbefund | Konsequenz |
| --- | --- | --- |
| [cinzas/homeassistant-enigma-player](https://github.com/cinzas/homeassistant-enigma-player/tree/c961361428afb1ceb0c264882595e38c8abee107) | README hat eine leere License-Überschrift; keine LICENSE/COPYING-Datei im geprüften Baum; GitHub-Metadaten `license: null` | Direkte Codeübernahme nicht freigegeben; nur funktionale Referenz |
| [KavajNaruj/homeassistant-enigma-player](https://github.com/KavajNaruj/homeassistant-enigma-player/tree/130316693987cdf390f5bea76af24db1b0fc331e) | Auch im ausgewiesenen Ursprungsrepository keine erkennbare Lizenzfreigabe | Der Fork-Ursprung beseitigt die Unklarheit nicht |
| [howeydium/HAVUOpenWebif](https://github.com/howeydium/HAVUOpenWebif/tree/f20b23d74b6b63f343dd42d2177dec22df068d76) | README erklärt „MIT“; kein vollständiger Lizenztext und kein eigenständiger Copyright-Hinweis; GitHub erkennt keine Lizenz | MIT-Erklärung ist vorhanden, also nicht pauschal „unlizenziert“. Herkunft/Hinweise sind jedoch unvollständig; keine Produktionsdateien kopiert |
| [home-assistant/core](https://github.com/home-assistant/core/blob/2f79d1fd2afdd19d28f9d4662a4de21865ea03ca/LICENSE.md), einschließlich `components/enigma2` | Apache-2.0 im Root-Lizenztext; keine abweichenden Hinweise in den geprüften Integrationsdateien; keine Root-NOTICE gefunden | Übernahme grundsätzlich unter Apache-Bedingungen möglich; hier als Funktionsreferenz genutzt |
| [openwebifpy 4.3.1](https://pypi.org/project/openwebifpy/4.3.1/) | Vollständige MIT-Lizenz im geprüften PyPI-Quellarchiv, Copyright 2019 Finbarr Brady | Mit Apache-2.0 kombinierbar bei Erhalt des MIT-Textes/Hinweises. Bibliothek wird vom neuen Projekt nicht eingebunden oder mitgeliefert |
| [E2OpenPlugins/OpenWebif](https://github.com/E2OpenPlugins/e2openplugin-OpenWebif) | Untersuchte Serverdateien `info.py`/`web.py` nennen GPL Version 3 oder später | Server läuft separat auf dem Receiver; keine Serverdateien in der Integration |

`license: null` ist nur ein Befund der automatischen GitHub-Erkennung. Entscheidend
sind vorhandene Erklärungen und Rechte, nicht dieses Metadatenfeld allein. GitHub
erläutert sowohl Lizenzhinweise in READMEs als auch das Fehlen einer allgemeinen
Weiterverwendungsfreigabe bei nicht lizenzierten öffentlichen Repositories:
[Licensing a repository](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository).

## Besteht ein Lizenzproblem?

**Beim direkten Zusammenkopieren der alten Repositories: ja, insbesondere beim
älteren Enigma-Projekt wegen der fehlenden Lizenzfreigabe.** Weder MIT noch Apache
oder GPL als neuer Dateikopf können diese Lücke nachträglich beheben. Für eine
spätere echte Übernahme müssten die Rechte der maßgeblichen Autoren geklärt werden.

**Bei HAVU ist die Lage besser, aber nicht vollständig dokumentiert:** Die README
enthält eine MIT-Erklärung. Ein fehlender separater Lizenztext macht diese Erklärung
nicht automatisch wertlos. Für eine direkte Weiterverteilung wären der vollständige
Text und zutreffende Urheberhinweise sinnvoll zu vervollständigen. Weil keine HAVU-Dateien
kopiert werden, hängt die neue Codebasis nicht von einer erfundenen Autorenangabe ab.

**OpenWebif erzwingt für diesen HTTP-Client nicht automatisch GPL:** Es wird ein
separat laufender Server über seine öffentliche API angesprochen. Es gibt weder
Linking mit dem Receiver-Server noch Übernahme seiner Implementierung. Die Bewertung
folgt der Unterscheidung zwischen separaten Programmen und einem kombinierten Werk;
die konkrete Kommunikationssemantik ist dabei relevant, nicht bloß das Wort HTTP.
Siehe [GNU-FAQ zu separaten Programmen/Aggregation](https://www.gnu.org/licenses/gpl-faq.html#MereAggregation).
Eine spätere Übernahme von GPL-Servercode wäre eine neue Lizenzentscheidung und darf
nicht ohne Prüfung unter Apache-2.0 umetikettiert werden.

Für den jetzigen, neu implementierten Produktionscode wurde somit **kein bekanntes
Hindernis gegen Apache-2.0 festgestellt**. Das bedeutet nicht, dass eine automatische
Analyse unbekannte Rechte Dritter verbindlich ausschließen könnte.

## Abhängigkeiten und lokale Recherchedateien

Die Integration importiert HA und von HA bereitgestellte Bibliotheken. Ein leeres
`requirements`-Feld bedeutet keine Lizenzfreiheit dieser Bibliotheken. Die geprüfte
Testinstallation meldet für HA 2026.9.1 Apache-2.0, für aiohttp 3.14.3
`Apache-2.0 AND MIT` und für yarl 1.24.5 Apache-2.0. Sie werden nicht in das
Integrationspaket kopiert; ihre eigenen Lizenzdateien bleiben bei ihren Distributionen.
Für ein späteres Gesamtimage oder gebündeltes Installationspaket wäre dessen gesamte
Abhängigkeitsmenge separat zu dokumentieren.

Unter `.work/` liegen ausschließlich lokale Arbeitsmittel: Quellbelege,
Lizenz-Metadaten, Python/Testumgebungen und Caches. Diese behalten ihre jeweiligen
Fremdlizenzen, sind durch `.gitignore` ausgeschlossen und gehören **nicht** in ein Release.
Die Apache-Lizenz des Projekts beansprucht ausdrücklich keine Umlizenzierung dieser Dateien.

## Regeln für weitere Arbeit

1. Neuen eigenen Code mit `SPDX-License-Identifier: Apache-2.0` versehen.
2. Bei echten Fremdcodeübernahmen Quelle, Version, ursprüngliche Hinweise und Änderungen dokumentieren.
3. MIT-Text bei Übernahme entsprechender Codebestandteile beilegen; Apache-Hinweise erhalten.
4. Keine Übernahme aus dem älteren Enigma-Repository ohne geklärte Freigabe.
5. Keine GPL-Serverbestandteile in den Apache-Produktionscode kopieren.
6. `.work`, Testumgebungen und Paket-Caches aus Veröffentlichungen ausschließen.
