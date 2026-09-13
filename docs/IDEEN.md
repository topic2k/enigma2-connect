# Mögliche zukünftige Entwicklungen

Diese Ideen sind vorgemerkt, aber weder zur Umsetzung eingeplant noch zugesagte Funktionen.

## Interaktive Bildschirmnachrichten

Stand: 13. September 2026. Entscheidung: Den aktuellen Funktionsumfang beibehalten;
Antwortabfrage und erweiterte Dialoge vorerst nicht implementieren.

`enigma2_connect.message` sendet Bildschirmnachrichten. Antworten auf Ja/Nein-Fragen
werden derzeit nicht in Home Assistant bereitgestellt.

Mögliche spätere Erweiterungen:

- Antworten in HA-Automationen abfragen und auswerten. OpenWebif bietet dafür bereits
  `messageanswer`; eine reine Ja/Nein-Abfrage benötigt keine Receiver-Erweiterung.
- Die vorausgewählte Antwort festlegen, beispielsweise „Nein“.
- Eigene Antwortmöglichkeiten anbieten, etwa „Jetzt“, „Später“ und „Abbrechen“.
- Einen Zeitablauf eindeutig von einer bewussten Antwort unterscheiden.

Für die konfigurierbare Vorauswahl, eigene Antworten und eine eindeutige
Zeitablauf-Rückgabe wäre zusätzlich eine Erweiterung auf dem Receiver erforderlich:
entweder eine Anpassung von OpenWebif oder ein separates Enigma2-Plugin mit einer
passenden Schnittstelle. Eine Änderung allein an der HA-Integration reicht nicht.
Enigma2 unterstützt solche Dialogoptionen je nach Image bereits intern;
die normale OpenWebif-Nachrichtenschnittstelle stellt sie jedoch nicht bereit.

Bei einer späteren Umsetzung prüfen: Kompatibilität mit den Ziel-Images,
eindeutige Zuordnung von Antworten zu Fragen und Verhalten bei parallelen Dialogen.
OpenWebif speichert derzeit nur die letzte Antwort pro Receiver; bei Zeitablauf
kann der Dialog die ausgewählte Antwort zurückgeben, ohne eine manuelle Bestätigung
davon unterscheidbar zu machen.

Technische Referenzen:

- [OpenWebif-Nachrichtenschnittstelle](https://github.com/E2OpenPlugins/e2openplugin-OpenWebif/blob/master/plugin/controllers/web.py)
- [OpenWebif-Antwortauswertung](https://github.com/E2OpenPlugins/e2openplugin-OpenWebif/blob/master/plugin/controllers/models/message.py)
- [Dialogoptionen in OpenATV](https://github.com/openatv/enigma2/blob/master/lib/python/Screens/MessageBox.py)
