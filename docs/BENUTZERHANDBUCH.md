[Deutsch](BENUTZERHANDBUCH.md) | [English](USER_GUIDE.en.md)

# Benutzerhandbuch

[Zur kurzen Übersicht](../README.md#deutsch)

Mit Enigma2 Connect bedienst du deinen Receiver über Home Assistant: Sender
wechseln, Lautstärke einstellen, Aufnahmen auf dem Fernseher abspielen und
Nachrichten anzeigen. Du kannst die Bedienung auch in Automationen einbauen.
Bild und Ton laufen standardmäßig auf dem Receiver und dem angeschlossenen Fernseher.
Die optionale [externe Wiedergabe](#auf-anderen-geräten-abspielen) ergänzt Live-TV
und TS-Aufnahmen auf HLS-fähigen Browsern und Mediengeräten.

## Inhalt

- [Installieren und einrichten](#installieren-und-einrichten)
- [Den Receiver bedienen](#den-receiver-bedienen)
- [Aufnahmen und Sender durchsuchen](#aufnahmen-und-sender-durchsuchen)
- [Vorschaubilder auswählen](#vorschaubilder-auswählen)
- [Einstellungen ändern](#einstellungen-ändern)
- [Fernbedienung im Dashboard](#fernbedienung-im-dashboard)
- [Nachrichten und Automationen](#nachrichten-und-automationen)
  - [Aktionen und Beispiele](#aktionen-und-beispiele)
- [Timer und Kalender](#timer-und-kalender)
- [Probleme lösen](#probleme-lösen)
- [Aktualisieren und entfernen](#aktualisieren-und-entfernen)

## Installieren und einrichten

Du brauchst Home Assistant **2026.9 oder neuer** und einen Enigma2-Receiver mit
aktiviertem OpenWebif. OpenWebif ist die Weboberfläche deines Receivers. Öffne
sie zuerst im Browser und prüfe, ob du dort den Receiver bedienen kannst.
Home Assistant muss diese Adresse ebenfalls erreichen können.

Für die manuelle Installation brauchst du Zugriff auf den Konfigurationsordner von
Home Assistant. Sichere deine Home-Assistant-Installation vor dem Einbau.

1. Kopiere aus diesem Projekt den gesamten Ordner
   `custom_components/enigma2_connect` nach
   `/config/custom_components/enigma2_connect`. Falls `custom_components` noch
   nicht existiert, lege diesen Ordner an.
2. Starte Home Assistant neu.
3. Öffne **Einstellungen → Geräte & Dienste → Integration hinzufügen** und suche
   nach **Enigma2 Connect**.
4. Gib die IP-Adresse oder den Hostnamen des Receivers ein, zum Beispiel
   `192.168.1.50`. Lass `http://`, Port und weitere Pfadangaben in diesem Feld weg.
5. Trage den OpenWebif-Port im eigenen Feld ein. Üblich sind **80** für HTTP und
   **443** für HTTPS; maßgeblich sind die Einstellungen deines Receivers.
6. Aktiviere HTTPS nur, wenn OpenWebif entsprechend eingerichtet ist. Benutzername
   und Passwort bleiben leer, wenn OpenWebif keine Anmeldung verlangt.
7. Schließe den Dialog ab und öffne das neu angelegte Gerät.

Die Verbindungsfelder gelten ebenso für **Neu konfigurieren** und eine erneute
Anmeldung:

| Feld | Standard und Bedeutung |
| --- | --- |
| Hostname oder IP-Adresse | Kein Standard; Adresse des Receivers ohne Protokoll, Port und Pfad. |
| Port (HTTP: 80, HTTPS: 443) | Bei der Ersteinrichtung 80; bei HTTPS bei Bedarf auf den tatsächlich eingerichteten Port ändern, meist 443. |
| Benutzername | Leer; nur bei aktivierter OpenWebif-Anmeldung ausfüllen. |
| Passwort | Leer; Passwort der OpenWebif-Anmeldung. |
| HTTPS verwenden | Aus; nur einschalten, wenn OpenWebif HTTPS unterstützt und dafür eingerichtet ist. |
| TLS-Zertifikat prüfen | Ein; prüft bei HTTPS, ob das Receiver-Zertifikat vertrauenswürdig ist. Bei einem eigenen, nicht vertrauenswürdigen Zertifikat lässt sich die Prüfung gezielt ausschalten. |

Weitere Receiver fügst du auf dieselbe Weise hinzu. Benenne sie eindeutig,
zum Beispiel „Wohnzimmer“ und „Schlafzimmer“. Die Einrichtung erfolgt vollständig
über die Oberfläche; eine YAML-Konfiguration ist nicht erforderlich.

### HACS

Du kannst das
[Projekt-Repository](https://github.com/topic2k/enigma2-connect) über das HACS-Menü
**Benutzerdefinierte Repositories** als Typ **Integration** hinzufügen und danach
herunterladen. Starte Home Assistant anschließend neu und füge die Integration
wie oben beschrieben hinzu. Die Schritte
erklärt auch die [HACS-Anleitung](https://www.hacs.xyz/docs/faq/custom_repositories/).
Eine Aufnahme in den HACS-Standardkatalog ist nicht zugesagt.

### Automatisch erkennen und Adressen aktualisieren

Wenn OpenWebif seinen Webdienst per Bonjour mit einem Namen beginnend mit
„OpenWebif“ ankündigt, erscheint ein Fund unter **Einstellungen → Geräte & Dienste**.
Öffne **Hinzufügen**, prüfe die vorausgefüllte Adresse, den Port und HTTPS, ergänze
bei Bedarf Zugangsdaten und schließe den Dialog ab. Erst danach wird der Receiver
gekoppelt. Ohne passenden Bonjour-Namen oder bei blockiertem Multicast verwende
die manuelle Einrichtung oben. Die bloße Installation von OpenWebif garantiert
keine passende Ankündigung; Image und Bonjour-/Avahi-Konfiguration sind entscheidend.

Bei bereits gekoppelten Receivern kann Home Assistant eine durch DHCP erkannte
neue IP übernehmen. Dafür müssen die bekannte MAC-Adresse und die Identität in
der OpenWebif-Antwort übereinstimmen. Port, Anmeldung und TLS-Einstellungen bleiben
erhalten. Eine andere Ankündigung schaltet HTTPS nicht ab.

Fehlen nach einem Neustart der Netzwerkschnittstelle die Geräteinformationen in
OpenWebif, kann ein Neustart der Receiver-Benutzeroberfläche (Enigma2/GUI) helfen.
Wähle dafür einen Zeitpunkt ohne laufende Aufnahme. Sobald die bekannte MAC wieder
gemeldet wird, kannst du die Adresse bei Bedarf über **Neu konfigurieren** ändern.
Bei einem über MAC gekoppelten Receiver bleibt auch dieser Weg gesperrt, solange
die Geräteidentität fehlt oder abweicht.

### Unterstützte Geräte

Voraussetzung ist die OpenWebif-JSON-API. Markenname oder Enigma2 allein sind kein
Kompatibilitätsnachweis. Diese Übersicht beschreibt vorhandene Prüfungen vom
13.09.2026 am damaligen Stand 0.1.0. Zusätzlich bestand die aktuelle lesende
Abnahme am Octagon: Einrichtung, Entitäten, Aktualisierung, Screenshot und Picon.
Ergänzend wurden Aufnahmebilder, begrenzte Bedienaktionen und die Adressübernahme
nach einem tatsächlichen DHCP-Wechsel geprüft:

| Receiver / OpenWebif | Belegter Umfang und Grenze |
| --- | --- |
| Octagon SF8008 4K Supreme / 2.4.0 | Live-TV/Radio, Aufnahmen, Picons/Bildschirmfoto, Fernbedienung, Nachrichten, Timer, Standby und Neustart wurden geprüft. |
| Vu+ Solo² / 1.4.4 | Einrichtung ohne Anmeldung, getrennte Gerätezuordnung, Kataloge, Fernbedienung, Nachrichten und Timer wurden geprüft. Ohne DVB-Eingangssignal keine zweite Bild-/Tonabnahme. |
| Andere Enigma2-Receiver / Images | Können mit passender OpenWebif-API funktionieren; noch kein konkreter Hardware-Nachweis. Optionale Daten können fehlen. |
| Receiver ohne OpenWebif-JSON-API | Nicht unterstützt; eine HTML-Weboberfläche allein reicht nicht aus. |

Die neue Erkennung und Adressänderung sind mit gezielt ausgelösten Meldungen und
echten HA-Konfigurationsflüssen getestet, einschließlich der neuen IP des Octagon.
Die automatische Erkennung echter Netzwerkmeldungen steht noch aus. Den genauen Umfang dokumentiert die
[Prüfübersicht](VALIDIERUNG.md#aktuelle-lesende-octagon-abnahme).

## Den Receiver bedienen

Unter **Einstellungen → Geräte & Dienste → Enigma2 Connect** findest du deine
Receiver. Öffne ein Gerät, um seine Bedienelemente und Informationen zu sehen.
Home Assistant nennt diese einzelnen Elemente „Entitäten“.

| Element | Damit kannst du … |
| --- | --- |
| Medienplayer | ein- und ausschalten, Lautstärke ändern, stummschalten und Wiedergabe steuern |
| Bouquet und Senderauswahl | eine Sendergruppe und anschließend einen Sender auswählen |
| Receiver-Steuerung | normalen Standby schalten und die Fernbedienungskarte verwenden |
| Bildschirmnachricht | Text auf dem Fernseher anzeigen |
| Sender und Sendungsinformationen | die aktuelle und nächste Sendung ansehen |
| Zustandsanzeigen | Verbindung, Standby, Aufnahme und Streaming prüfen |
| Signalwerte und Zähler | Empfangswerte sowie die Anzahl von Aufnahmen und Timern ansehen |
| Kamera | ein Bildschirmfoto des Receivers ansehen |
| Kalender | die Timer des Receivers ansehen |
| Listen aktualisieren | Sender, Timer und Aufnahmen erneut abrufen |

Füge den **Medienplayer** deinem Dashboard hinzu. Wähle dort unter **Quelle**
einen Sender aus. Eine Sendergruppe heißt bei Enigma2 „Bouquet“; damit kannst du
beispielsweise zwischen TV-Favoriten und Radiosendern wechseln.

Zum Ausschalten wird standardmäßig **Standby** verwendet. Daraus lässt sich der
Receiver wieder einschalten. **Tiefschlaf** fährt ihn dagegen herunter; aus diesem
Zustand kann die Integration ihn nicht aufwecken. Der Schalter
**Receiver-Steuerung** verwendet immer normalen Standby, auch wenn für den
Medienplayer Tiefschlaf eingestellt wurde.

Play, Pause und Stop senden den entsprechenden Befehl. Der Receiver meldet
jedoch nicht zuverlässig zurück, ob eine Wiedergabe gerade pausiert ist.
Verlasse dich dafür auf das Bild am Fernseher. Manche Dashboardkarten blenden
Stop nicht ein; die [Fernbedienungskarte](#fernbedienung-im-dashboard) bietet
zusätzliche Tasten. Weitere einzelne Tasten lassen sich bei Bedarf als
standardmäßig deaktivierte Button-Entitäten in den Entitätseinstellungen aktivieren.

Signalqualität, SNR und gemeldete Bitfehlerrate sind optionale Diagnosen und bei
neuen Entitäten zunächst deaktiviert. Öffne **Einstellungen → Geräte & Dienste →
Entitäten**, zeige deaktivierte Entitäten an und aktiviere den gewünschten Sensor.
Vorhandene Aktivierungsentscheidungen bleiben bei Updates erhalten. Der Receiver
bietet außerdem Zustandsanzeigen für Standby, Aufnahme, Streaming und Verbindung;
Verbindung und **Listen aktualisieren** gehören zu den Diagnosen.

## Aufnahmen und Sender durchsuchen

Es gibt zwei Zugänge zu deinen Aufnahmen:

- Öffne am Medienplayer **Medien durchsuchen** für die Aufnahmen dieses Receivers.
- Öffne in der Seitenleiste **Medien → Enigma2 Connect**, um zwischen allen
  eingerichteten Receivern zu wählen.

Öffne die gewünschten Unterordner und wähle eine Aufnahme aus. In der
Medien-Seitenleiste wählst du unten den Receiver als Wiedergabegerät aus,
auf dem die Aufnahme liegt. Für „Webbrowser“ oder andere Geräte aktiviere zuerst
die unten beschriebene externe Wiedergabe.

Neben dem Titel stehen Datum, Uhrzeit, Sender und Länge, soweit diese Angaben
vorhanden sind. Die Uhrzeit richtet sich nach der in Home Assistant eingestellten
Zeitzone. Ordner stehen vor Aufnahmen; aufgeführt wird, was OpenWebif aus dem
Aufnahmeverzeichnis einschließlich Unterordnern meldet.

### Mehrere Receiver zusammen anzeigen

Öffne die [Receiver-Optionen](#einstellungen-ändern) und stelle **Aufnahmen in der
Medien-Kachel** auf **Receiver zusammenfassen**. Diese Einstellung gilt für alle
Receiver. Gleichnamige Unterordner werden zusammen angezeigt. Jede Aufnahme trägt
den Namen ihres Receivers; gleichnamige Aufnahmen bleiben einzelne Einträge.

### Sender zusätzlich im Medienbrowser anzeigen

Standardmäßig enthält der Medienbrowser nur Aufnahmen. Aktiviere in den Optionen
**Sender im Medienbrowser anzeigen**, wenn du dort zusätzlich einen Ordner
**Sender** möchtest. **Bouquet für den Medienbrowser** legt dessen Sendergruppe
fest. Bleibt das Feld leer, folgt der Ordner der gerade ausgewählten Sendergruppe.
Eine eigene Auswahl hier ändert die Sendergruppe unter **Quelle** nicht.
Die Auswahl zeigt die Bouquet-Namen auch nach erneutem Öffnen der Optionen.
Ist ein gespeichertes Bouquet momentan nicht verfügbar, bleibt die Zuordnung
erhalten; ersatzweise wird sein Dateiname angezeigt. Neue Bouquets werden aus
der vom Receiver gelieferten Liste ausgewählt.

Diese Optionen gelten pro Receiver und wirken in beiden Medienansichten. Bei
zusammengefassten Aufnahmen führt der Senderordner zuerst zu den Receivern und
dann zu ihren Sendern. Wähle den zugehörigen Receiver oder nutze die externe Wiedergabe.
Senderlogos werden vom Receiver geladen; fehlt ein Logo, erscheint ein Fernsehsymbol.

### Auf anderen Geräten abspielen

1. Öffne **Einstellungen → Geräte & Dienste → Enigma2 Connect → Konfigurieren →
   Einstellungen** für den gewünschten Receiver.
2. Aktiviere **Wiedergabe auf anderen Geräten**. Für Live-TV aktiviere zusätzlich
   **Sender im Medienbrowser anzeigen** und wähle bei Bedarf ein Bouquet.
3. Prüfe **Live-TV-Streamingport** (normalerweise **8001**). Aktiviere **HTTPS für
   Live-TV-Streaming** nur, wenn dieser Port HTTPS unterstützt. Der separate
   OpenWebif-Zugang bleibt für Aufnahmen zuständig; beide verwenden die gespeicherte Anmeldung.
4. Öffne **Medien → Enigma2 Connect** und wähle **Webbrowser** oder einen
   geeigneten Medienplayer, etwa ein Cast-Gerät, als Wiedergabegerät.
5. Wähle eine TS-Aufnahme oder einen Sender unter **Sender**. Der Start kann
   einige Sekunden dauern. Stoppe die Wiedergabe am Zielgerät.

**Stream-Verarbeitung → Automatisch** ist voreingestellt. Die Integration prüft
bei Live-TV zuerst den HLS-Ausgang des Receivers. Geeignetes HLS wird über Home
Assistant weitergereicht, ohne einen FFmpeg-Encoder zu starten. Andernfalls werden
passende Bild- und Tonspuren unverändert in HLS verpackt. Für ungeeignete Live-TV-
Codecs wird zusätzlich der in OpenWebif konfigurierte Transcoding-Ausgang geprüft.
Der Receiver muss diesen bereitstellen; ein sichtbarer Transcoding-Abschnitt allein
garantiert das nicht. Seine Einstellungen werden nicht verändert.

Bei Live-TV und der Aufnahme-Wiedergabe ohne vollständiges Spulen werden nur
ungeeignete Spuren auf Home Assistant umgewandelt. Passendes Video behält
seine ursprüngliche Auflösung und Bildrate. Die Software-Umwandlung liefert maximal
720p/25 fps und AAC-Stereoton. Zur Formaterkennung wird **ffprobe** aus dem FFmpeg-
Paket benötigt; zum Verpacken oder Umwandeln **FFmpeg**, für die Video-Umwandlung
zusätzlich **libx264**. Fehlt die Erkennung oder scheitert der optimierte Start,
wird automatisch die bisherige vollständige Umwandlung versucht.

Bei Problemen wähle **Stream-Verarbeitung → Kompatibilität (immer umwandeln)**.
Dieser Modus benötigt mehr CPU-Leistung und umgeht Receiver-HLS/Transcoding.
Das Zielgerät muss HLS unterstützen und die Home-Assistant-Adresse erreichen.
Bei Cast müssen auch Namensauflösung und gegebenenfalls das HTTPS-Zertifikat passen.
Firefox und Edge wurden vom Nutzer für die bisherige vollständige Umwandlung
bestätigt. Optimierte Aufnahmewiedergabe mit mehreren Vor-/Rücksprüngen wurde am
16.09.2026 in HA bestätigt; der konkrete Browser wurde dabei nicht angegeben.
Konkrete Cast-Geräte benötigen weiterhin eigene Praxistests.

Unter **Maximale gleichzeitige Streams** legst du die Grenze pro Receiver fest:
**Standard 5**, eine andere positive ganze Zahl oder **0 für unbegrenzt**. Eine neue
Wiedergabe beendet keine andere. Bei erreichter Grenze wird nur der zusätzliche
Start abgelehnt. Stoppe eine Wiedergabe und warte bis zu zwei Minuten nach dem
letzten Abruf, bis ihr Platz wieder nutzbar ist, oder passe die Grenze an.
Auch kürzlich gestoppte Streams zählen bis dahin mit. Das Speichern der Receiver-
Optionen lädt die Integration neu und beendet dabei ihre laufenden Streams.

Mehrere Zuschauer desselben Live-Senders teilen **einen Stream und einen Platz**.
Solange mindestens ein Zuschauer Daten abruft, bleibt dieser Stream aktiv.
Jeder Start einer Aufnahme belegt dagegen einen eigenen Platz und beginnt am
Anfang, damit Zuschauer unabhängig voneinander schauen können. Die Grenze gilt
auch für gerade startende Streams. Freie Tuner, Entschlüsselung, Receiver-Encoder
und Home-Assistant-Leistung können die tatsächlich mögliche Anzahl weiter begrenzen.

**In Aufnahmen spulen:** Öffne eine abgeschlossene TS-Aufnahme, warte auf den
Start und ziehe die Zeitleiste auf die gewünschte Stelle. Wenn der Receiver
Dateiabschnitte gezielt liefern kann und die Dauer ermittelt wird, zeigt der
Player die gesamte Aufnahme. Vor- und Rücksprünge sind auch außerhalb des
bisherigen Puffers möglich. Nach einem Sprung kann das Bild kurz laden.

Im Modus **Automatisch** bleibt geeignetes H.264-Video unverändert: Auflösung,
Bildrate und Bildqualität der Aufnahme bleiben erhalten. Geeigneter AAC-Ton wird
ebenfalls übernommen; andernfalls wird nur der Ton zu AAC umgewandelt. HA verpackt
die angeforderten Abschnitte für den Browser. Dafür benötigt der Receiver einen
passenden Aufnahmeindex (`.ts.ap`); aktuelle FFmpeg-Funktionen und ffprobe müssen
auf HA verfügbar sein. Ein Vollscan oder vollständiger Download ist nicht nötig.

Fehlen diese Voraussetzungen oder ist **Kompatibilität** gewählt, greift die
bisherige vollständige Umwandlung mit libx264: bis 720p/25 fps, Zielbitrate 2 Mbit/s
und AAC-Ton. Das Debuglog nennt unter `VOD remux unavailable` den Rückfallgrund.
Der Moduswechsel erfolgt in den Optionen der Integration; Speichern beendet
laufende Streams. Die Aufnahme bleibt auf dem Receiver, HA hält höchstens 32 MiB
Abschnittsdaten je Sitzung. Jede Wiedergabe besitzt eine unabhängige Zeitleiste.
Der optimierte Einstieg beginnt am ersten verzeichneten Schlüsselbild; ein kurzer
Vorlauf davor kann entfallen. Bei Darstellungsproblemen hilft der Kompatibilitätsmodus.

Fehlen passende Dateizugriffe oder eine verlässliche Dauer, beginnt automatisch
die bisherige Wiedergabe mit einem begrenzten Fenster. Das Debuglog nennt den
Grund unter `VOD unavailable`; vollständiges Spulen steht dann nicht bereit.
Noch laufende oder während der Wiedergabe veränderte Aufnahmen sind nicht für
diesen VOD-Modus geeignet. Unterstützt werden Aufnahmen bis 24 Stunden Dauer.
Wird eine Datei nach dem Start verändert, kann die Wiedergabe abbrechen.

Bei Live-TV und im Aufnahme-Fallback umfasst lokales HLS acht Segmente mit zwei
Sekunden Zieldauer; kopierte Schlüsselbildabstände können diese verlängern.
Bei Receiver-HLS bestimmt der Receiver das Fenster. Langes Pausieren und
automatisches Fortsetzen an einer gespeicherten Position sind nicht enthalten.
Nach zwei Minuten ohne Abruf wird aufgeräumt; spätestens nach sechs Stunden ist
eine neue Auswahl nötig. Geteilte Wiedergabe-URLs gewähren bis zum Ablauf Zugriff.

Der Receiver muss erreichbar sein und für Live-TV freie Tuner beziehungsweise
Entschlüsselungsmöglichkeiten haben. Die Integration sendet beim externen Start
keinen Umschalt- oder Einschaltbefehl; Firmware und Tunerbelegung können dennoch
den Empfang begrenzen. Radio ohne Videospur, andere Aufnahmeformate, Untertitel,
Tonspurauswahl und Wiedergabefortschritt auf dem Receiver werden nicht übernommen.

## Vorschaubilder auswählen

In den Receiver-Optionen bestimmst du unter **Vorschaubilder für Aufnahmen –
Bildquellen**, welche Bilder angezeigt werden. Mehrere Quellen sind möglich.
Entferne alle Häkchen, um die Bilder auszuschalten.

### Ein Bild aus der Aufnahme

Standard ist **Snapshot aus der Aufnahme**: ein Einzelbild zehn Minuten nach
Beginn der Aufnahmedatei. Ein Aufnahmevorlauf zählt dabei mit. Den Zeitpunkt
kannst du je Receiver ändern. Bei einer kürzeren, abgeschlossenen Aufnahme wird
ein Bild aus ihrer Mitte verwendet. Bei einer noch laufenden Aufnahme wartet
die Bildgewinnung, bis die gewählte Stelle verfügbar ist.

Die Bilder werden im Hintergrund vorbereitet, neuere Aufnahmen zuerst. Dafür
musst du den Medienbrowser nicht öffnen. Bei großen Sammlungen werden ältere
Bilder erst beim Aufrufen erzeugt. Die Vorbereitung kann etwas dauern und startet
keine Wiedergabe auf dem Fernseher. OpenWebif muss das Lesen der Aufnahmedatei
erlauben. Hinweise zu fehlenden Bildern stehen unter [Probleme lösen](#probleme-lösen).

### Film- und Serienbilder aus dem Internet

Wähle zusätzlich **TMDB** oder **OMDb (IMDb-Zuordnung)** und trage den jeweiligen
API-Schlüssel ein. Das ist ein Zugangsschlüssel des Anbieters, kein Passwort
deines Receivers. Du erhältst ihn über
[TMDB](https://developer.themoviedb.org/docs/getting-started) beziehungsweise
[OMDb](https://www.omdbapi.com/apikey.aspx).

Nur ausgewählte Anbieter werden abgefragt. Dafür erhalten sie den Aufnahmetitel,
auch bei der Vorbereitung im Hintergrund. OMDb ist ein eigener Dienst mit
IMDb-Zuordnung, keine direkte Suche auf der IMDb-Webseite. Bei gleichen oder
ungenauen Titeln kann die Suche ein unpassendes Bild liefern.

### Eigene Bildadresse

Mit **Eigene Bild-URL** kannst du ein Bild von einem eigenen Bilddienst verwenden.
Trage eine direkte Adresse zu einer JPEG-, PNG- oder WebP-Datei ein. Eine normale
Webseite oder eine Adresse, die erst weiterleitet, funktioniert nicht.

Bei Bedarf darf die Adresse Platzhalter enthalten:

| Platzhalter | Wird ersetzt durch … |
| --- | --- |
| `{title}` | den Aufnahmetitel |
| `{filename}` | den Dateinamen ohne Ordner |
| `{channel}` | den Sendernamen |

Beispiel: `https://bilder.example/{title}.jpg`. Die eingefügten Angaben werden an
deinen Bilddienst übertragen. Verwende eine Adresse ohne eingebetteten Benutzernamen
oder Passwort. Eine feste Bildadresse ohne Platzhalter ist ebenfalls möglich.

Bei mehreren gewählten Quellen gilt: **eigene URL → TMDB → OMDb → Snapshot**.
Sobald ein Bild gefunden wurde, werden die folgenden Quellen nicht mehr abgefragt.
Fehlt überall ein Bild, bleibt ein neutrales Symbol. Die Aufnahme ist trotzdem abspielbar.
Bilder werden zwischengespeichert; geänderte Bildeinstellungen veranlassen neue Bilder.

## Einstellungen ändern

Öffne **Einstellungen → Geräte & Dienste → Enigma2 Connect** und beim gewünschten
Receiver **Konfigurieren**. Im Menü **Receiver-Optionen** hast du zwei Möglichkeiten:

- **Receiver-Einstellungen**: Einstellungen ansehen, ändern und speichern.
- **Vorschaubilder neu generieren**: Bilder mit den bereits gespeicherten
  Bildquellen erneut erstellen lassen.

### Receiver-Einstellungen

Die meisten Standardwerte kannst du beibehalten. Bei der Bouquet-Auswahl siehst du
die Namen deiner Sendergruppen. **—** bedeutet: keine eigene Gruppe festlegen.

| Einstellung | Standard und Bedeutung |
| --- | --- |
| Aufnahmen in der Medien-Kachel (gilt für alle Receiver) | Getrennt nach Receiver; alternativ zusammenfassen. Diese Auswahl wird für alle Receiver gespeichert. |
| Abfrageintervall (Sekunden) | 15 Sekunden; 5–300 Sekunden möglich. Kleinere Werte aktualisieren den Zustand häufiger. |
| Wiedergabe auf anderen Geräten | Aus; HLS über Home Assistant mit mehreren gleichzeitigen Streams. |
| Maximale gleichzeitige Streams | 5 pro Receiver; positive ganze Zahl, 0 = unbegrenzt. Derselbe Live-Sender wird gemeinsam genutzt; Aufnahmen starten separat. |
| Stream-Verarbeitung | Automatisch; geeignete Receiver-Ausgabe und unveränderte Spuren bevorzugen. Kompatibilität erzwingt die vollständige Umwandlung auf Home Assistant. |
| Live-TV-Streamingport | 8001; unabhängig vom OpenWebif-Port. |
| HTTPS für Live-TV-Streaming | Aus; nur für einen HTTPS-fähigen Streamingport aktivieren. |
| Sender im Medienbrowser anzeigen | Aus; ergänzt einen Senderordner in beiden Medienansichten. |
| Bouquet für den Medienbrowser | Leer; folgt der aktuell unter Quelle ausgewählten Sendergruppe. Eine eigene Auswahl ändert die Quelle des Medienplayers nicht. |
| Vorschaubilder für Aufnahmen – Bildquellen | Nur Snapshot; mehrere Quellen auswählbar. Keine Auswahl schaltet Vorschaubilder aus. |
| Snapshot-Zeitpunkt nach Aufnahmebeginn | 10 Minuten; 0–1440 Minuten in Schritten von 0,1 Minuten. Bezieht sich auf die Aufnahmedatei einschließlich Vorlauf. |
| TMDB API-Schlüssel | Leer; erforderlich, wenn TMDB als Bildquelle ausgewählt ist. |
| OMDb API-Schlüssel | Leer; erforderlich, wenn OMDb als Bildquelle ausgewählt ist. |
| Eigene Bild-URL | Leer; für die Bildquelle „Eigene Bild-URL“ eine direkte Bildadresse eintragen. |
| Standard-Bouquet (optional) | Leer; verwendet beim Laden zunächst die erste gelieferte Sendergruppe. Wähle eine Gruppe, um sie als Startgruppe festzulegen. |
| Zeitzone des Receivers | Zunächst die HA-Zeitzone; zum Beispiel `Europe/Berlin`. Wichtig für wiederkehrende Timer. |
| Medienbild | Senderlogo; alternativ Bildschirmfoto oder kein Bild. Betrifft den Medienplayer, nicht die Vorschaubilder der Aufnahmen. |
| Anzeigedauer (Sekunden) | 10 Sekunden; 1–120 Sekunden für Bildschirmnachrichten über `notify.send_message`. |
| Nachrichtentyp (0–3) | 1: Information. Außerdem 0: Ja/Nein-Frage, 2: Warnung, 3: Fehler. Gilt für `notify.send_message`; Darstellung je nach Receiver. |
| Verhalten beim Ausschalten | Standby; alternativ Tiefschlaf. Betrifft den Medienplayer. Aus dem Tiefschlaf kann die Integration den Receiver nicht einschalten. |

Bis auf die gemeinsame Darstellung der Aufnahmen gelten die Einstellungen nur
für den gewählten Receiver. Hinweise zu Bildquellen, Zugangsschlüsseln und
Platzhaltern findest du unter [Vorschaubilder auswählen](#vorschaubilder-auswählen).
Speichere deine Änderungen am Ende des Formulars.

### Vorschaubilder neu generieren

1. Falls du andere Bilder möchtest, wähle zuerst unter **Receiver-Einstellungen**
   die gewünschten Bildquellen und speichere sie.
2. Öffne die Receiver-Optionen erneut und wähle **Vorschaubilder neu generieren**.
   Die Vorbereitung startet direkt für diesen Receiver.
3. Warte etwas und öffne die Medienliste erneut, um die neuen Bilder zu sehen.

Die Medienliste bleibt währenddessen nutzbar. Neuere Aufnahmen werden im
Hintergrund vorbereitet; ältere erhalten beim nächsten Abruf ein neues Bild.
Die gespeicherten Einstellungen und die Bilder anderer Receiver bleiben erhalten.
Du kannst die Neugenerierung bei Bedarf wiederholen. Sind alle Bildquellen
deaktiviert, startet nichts: Wähle und speichere zuerst mindestens eine Quelle.

### Verbindung und Aktualisierung

**Neu konfigurieren** ändert Adresse, Port, Zugangsdaten und HTTPS-Einstellungen.
Bei einem nicht vertrauenswürdigen eigenen HTTPS-Zertifikat kann die
Zertifikatsprüfung ausgeschaltet werden. Bei abgelehnten Zugangsdaten fordert
Home Assistant eine erneute Anmeldung an.

Ein während der Bedienung gewechseltes Bouquet bleibt bis zum Neuladen aktiv.
Speichere eine gewünschte Startgruppe in den Optionen. Timer und Aufnahmen werden
normalerweise alle zwei Minuten, Senderlisten alle fünf Minuten aktualisiert.
Für eine sofortige Aktualisierung verwende **Listen aktualisieren**.
Die Aktion wartet auf ihren Abruf und meldet einen Fehler, wenn der Receiver
nicht aktualisiert werden konnte. Auch direkt aufeinanderfolgende Aufrufe
verwenden einen neuen Abruf statt des vorherigen Ergebnisses.

Ist der Receiver nicht erreichbar, werden seine Bedienelemente als **Nicht verfügbar**
angezeigt. Die Verbindungsanzeige bleibt sichtbar und zeigt die fehlende Verbindung.
Fehlen nur einzelne optionale Werte, können Sensoren **Unbekannt** anzeigen;
ein nicht abrufbarer Timerkatalog macht den Kalender nicht verfügbar. Die Integration
versucht weitere Abrufe automatisch. Ausfall und Wiederverbindung werden jeweils
einmal protokolliert, nicht bei jeder Wiederholung.

Die Zustände werden lokal abgefragt, standardmäßig alle 15 Sekunden. Zwischen
den Abfragen kann die Anzeige hinter der Receiver-Bedienung zurückliegen.
Eine neue Abfrage erfolgt auch nach passenden Bedienaktionen. Aufnahmen und
Timer folgen ihrem Zwei-Minuten-Takt, Senderlisten dem Fünf-Minuten-Takt.
Aufnahmebilder werden beim Einrichten und bei Katalogänderungen im Hintergrund
vorbereitet: höchstens 128 aktuelle Bilder, ein Auftrag gleichzeitig mit mindestens
fünf Sekunden Pause. Ältere Bilder entstehen bei Bedarf. Der lokale Bildspeicher
gilt bis zu sieben Tage; der Browser kann Aufnahmebilder einen Tag und Senderlogos
15 Minuten wiederverwenden. Bildschirmfotos werden höchstens fünf Sekunden
wiederverwendet. **Vorschaubilder neu erzeugen** umgeht den Aufnahmebildspeicher.

## Fernbedienung im Dashboard

Die Fernbedienungskarte wird zusätzlich zur Integration installiert:

1. Kopiere `www/enigma2-connect-remote-card.js` nach
   `/config/www/enigma2-connect-remote-card.js`. Wenn du `www` neu anlegst,
   starte Home Assistant danach einmal neu.
2. Öffne die Ressourcenverwaltung deiner Dashboards und füge
   `/local/enigma2-connect-remote-card.js` als **JavaScript-Modul** hinzu.
   Die [HA-Anleitung zur Ressourcenverwaltung](https://developers.home-assistant.io/docs/frontend/custom-ui/registering-resources/)
   hilft beim Finden der entsprechenden Seite.
3. Bearbeite dein Dashboard. Suche unter **Karte hinzufügen → Nach Karte** nach
   **Enigma2** und wähle **Enigma2 Connect Fernbedienung**.
4. Wähle im Karteneditor die **Receiver-Steuerung** des gewünschten Receivers.
   Vergib bei Bedarf einen Namen, zum Beispiel „Wohnzimmer“.

Pfeile, Lautstärke, Kanal und Spultasten unterstützen Gedrückthalten. Die Karte
braucht keine eigenen Receiver-Zugangsdaten. Fehler erscheinen direkt in der Karte.

Nach einem Kartenupdate ersetze die Datei und ändere den bestehenden
Ressourceneintrag beispielsweise auf `/local/enigma2-connect-remote-card.js?v=2`.
Lade den Browser vollständig neu. Lege keinen zweiten Ressourceneintrag an.
Ein Home-Assistant-Neustart ist für das reine Kartenupdate nicht nötig.

Die optionale Karte lässt sich auch manuell konfigurieren:

```yaml
type: custom:enigma2-connect-remote-card
entity: remote.test_receiver_remote
name: Wohnzimmer
```

## Nachrichten und Automationen

Eine Bildschirmnachricht kannst du zunächst unter **Entwicklerwerkzeuge →
Aktionen** ausprobieren: Wähle **Benachrichtigungen: Nachricht senden**
(`notify.send_message`), als Ziel **Bildschirmnachricht** deines Receivers und
trage den Text ein. Ein Titel ist optional.

Für eine Nachricht beim Klingeln an der Haustür:

1. Erstelle unter **Einstellungen → Automationen & Szenen** eine Automation.
2. Wähle die Betätigung deiner Klingel als Auslöser.
3. Füge als Aktion **Nachricht senden** hinzu.
4. Wähle die Bildschirmnachricht-Entität des Receivers als Ziel.
5. Gib beispielsweise „Es hat geklingelt“ ein und speichere die Automation.

Für einen abweichenden Nachrichtentyp oder eine andere Anzeigedauer verwende die
Nachrichtenaktion von **Enigma2 Connect** und wähle dort den Receiver als Gerät.
Antworten auf Ja/Nein-Fragen werden derzeit nicht an Home Assistant zurückgegeben.

Auch Senderwechsel, Standby und Tastenfolgen lassen sich automatisieren.
Die folgenden Beispiele zeigen dir die passenden Aktionen.

Die Integration stellt keine eigenen Auslöser oder Bedingungen bereit. Verwende in
Automationen die Standard-Auslöser und Zustandsbedingungen von Home Assistant,
zum Beispiel eine Änderung der Aufnahme- oder Verbindungsanzeige.

### Aktionen und Beispiele

Die folgenden Beispiele helfen dir bei eigenen Skripten und Automationen.
Du kannst sie unter **Entwicklerwerkzeuge → Aktionen** im YAML-Modus ausprobieren
oder als einzelne Aktion in eine Automation übernehmen. YAML ist dabei die
Textansicht der Einstellungen. Die Beispiele enthalten keinen Auslöser.

Ersetze die Beispiel-Entitäten durch deine eigenen Ziele. Wähle bei einer
Geräteaktion den Receiver zuerst in der Oberfläche aus; die YAML-Ansicht zeigt
dir seine `device_id`. Passe auch Senderkennungen und Termine an.

| Aktion | Ziel und Daten |
| --- | --- |
| `remote.send_command` | Remote-Entität; `command`, optional `delay_secs`, `num_repeats`, `hold_secs` |
| `media_player.play_media` | Medienplayer; `channel` für eine Sendernummer, `enigma2_reference` für eine Service-Referenz, `enigma2_recording` für eine Aufnahme-Referenz |
| `media_player.media_play`, `.media_pause`, `.media_stop` | Medienplayer; Wiedergabetasten ohne verlässliche Pause-Rückmeldung |
| `notify.send_message` | Bildschirmnachricht-Entität; `message`, optional `title`. Verwendet Nachrichtentyp und Anzeigedauer aus den Receiver-Einstellungen. |
| `enigma2_connect.message` | `device_id`, `text`, optional `type` (0–3, Standard 1) und `timeout` (1–120 Sekunden, Standard 10) |
| `enigma2_connect.reboot`, `.restart_gui`, `.deep_standby` | `device_id`; Receiver-Neustart, GUI-Neustart oder Tiefschlaf |
| `enigma2_connect.timer_add` | `device_id`, `service_reference`, `begin`, `end`, `name`; optional `description`, `justplay`, `afterevent` |
| `enigma2_connect.timer_delete`, `.timer_toggle` | `device_id`, `service_reference`, `begin`, `end` des vorhandenen Timers |

Wähle immer den gewünschten Receiver als Ziel. Namen mit einem führenden Punkt
in der Tabelle beginnen genauso wie die erste Aktion derselben Zeile.
Für Tastenfolgen kannst du beispielsweise `menu`, `up`, `down` und `ok` verwenden.
`delay_secs` ist die Pause zwischen Tastendrücken in Sekunden; `num_repeats`
wiederholt die Folge. `hold_secs` größer als 0 sendet einen langen Tastendruck;
wie lange er wirkt, hängt vom Receiver ab.

Gib Beginn und Ende eines Timers mit Datum, Uhrzeit und Zeitzone wie im Beispiel
an. `+02:00` steht dort für die deutsche Sommerzeit; passe den Wert an deinen
Termin und Standort an. Mit `justplay: true` schaltet der Receiver zum Sender,
ohne aufzunehmen. `afterevent` bestimmt das Verhalten danach: 0 = nichts,
1 = Standby, 2 = Tiefschlaf, 3 = automatisch. Zum Löschen oder Aktivieren/Deaktivieren
brauchst du Senderkennung und ursprünglichen Beginn und Ende des vorhandenen Timers.
Bei Serien betrifft die Änderung die ganze Serie. Die Listen werden danach aktualisiert.

#### Tastenfolge senden

```yaml
action: remote.send_command
target:
  entity_id: remote.test_receiver_remote
data:
  command: [menu, down, down, ok]
  delay_secs: 0.3
  num_repeats: 1
```

#### Sender nach Nummer wählen

```yaml
action: media_player.play_media
target:
  entity_id: media_player.test_receiver
data:
  media_content_type: channel
  media_content_id: "105"
```

#### Nachricht auf dem Fernseher anzeigen

```yaml
action: notify.send_message
target:
  entity_id: notify.test_receiver_screen_message
data:
  title: Türklingel
  message: Es hat geklingelt.
```

#### Einzelnen Aufnahme-Timer anlegen

```yaml
action: enigma2_connect.timer_add
data:
  device_id: DEINE_RECEIVER_GERAETE_ID
  service_reference: "1:0:1:6DD2:44D:1:C00000:0:0:0:"
  begin: "2026-10-10T20:15:00+02:00"
  end: "2026-10-10T21:45:00+02:00"
  name: Film
  description: Aufnahme aus Home Assistant
  justplay: false
  afterevent: 3
```

## Timer und Kalender

Der Kalender zeigt Aufnahme- und Umschalt-Timer vom Receiver, auch wöchentliche
Wiederholungen. Du kannst sie dort ansehen, aber nicht direkt bearbeiten.

Einen einzelnen Timer legst du unter **Entwicklerwerkzeuge → Aktionen →
Enigma2 Connect: Timer anlegen** an. Wähle den Receiver und gib Name, Beginn,
Ende und die Senderkennung aus OpenWebif ein. Die Senderkennung heißt
**Service-Referenz** und ist nicht die Sendernummer. Ein Beispiel mit allen
Feldern findest du in der [Aktionsreferenz](#aktionen-und-beispiele).
Für einen Umschalt-Timer aktiviere **Nur umschalten**.

Löschen und Aktivieren/Deaktivieren erfolgen ebenfalls über die Enigma2-Connect-
Aktionen. Bei einem wiederkehrenden Timer betrifft die Änderung die ganze Serie.
Neue Serien und Änderungen einzelner Wiederholungen richtest du direkt in
OpenWebif oder am Receiver ein. Achte bei Zeitumstellungen auf die richtige
Receiver-Zeitzone und prüfe die Termine auch am Gerät.

## Probleme lösen

| Problem | Was du prüfen kannst |
| --- | --- |
| Integration wird nicht gefunden | Ordner korrekt kopiert und Home Assistant neu gestartet? Receiver werden nicht automatisch erkannt. |
| Verbindung schlägt fehl | OpenWebif im Browser öffnen; dann Adresse, Port, Anmeldung und HTTPS über **Neu konfigurieren** prüfen. Alte Webinterfaces ohne OpenWebif werden nicht unterstützt. |
| Receiver ist „Nicht verfügbar“ | Netzwerk und Stromversorgung prüfen. Tiefschlaf beendet gewöhnlich die Erreichbarkeit; normaler Standby ist ein anderer Zustand. |
| Neue Aufnahmen oder Sender fehlen | **Listen aktualisieren** drücken. Falls Einträge weiterhin fehlen, die entsprechende Liste in OpenWebif prüfen. |
| Browser meldet „Medientyp nicht unterstützt“ | Integration auf mindestens `1.2.0-dev.2` aktualisieren und Home Assistant neu starten. `dev.1` meldete einen MIME-Typ, den der HA-Medien-Dialog nicht als HLS erkennt; ein Browserwechsel behebt diese Ursache nicht. |
| Aufnahme spielt nicht | Receiver auswählen oder externe Wiedergabe aktivieren. Bei externen Zielen FFmpeg mit libx264/AAC, HA-Erreichbarkeit, TS-Format und CPU-Auslastung prüfen; bei Live-TV außerdem Streamingport, Anmeldung und freie Tuner prüfen. |
| Vorschaubild fehlt | Bildquellen und Schlüssel prüfen, Vorbereitung abwarten. Bei laufenden Aufnahmen muss die gewünschte Stelle erst vorhanden sein. Einzelbilder benötigen FFmpeg auf dem HA-System und lesbare Aufnahmedateien; technische Hinweise stehen in der Entwicklerdokumentation. |
| Filmplakat passt nicht | Die Titelsuche kann einen anderen Treffer finden. Verwende stattdessen einen Snapshot oder eine eigene Bildadresse. |
| Senderlogo fehlt | Passende Senderlogos müssen auf dem Receiver vorhanden sein. Ohne Logo erscheint ein Ersatzsymbol. |
| Bildschirmfoto ist kurz schwarz | Nach einem Senderwechsel braucht der Receiver Zeit zum Bildaufbau. Später erneut ansehen. |
| Play/Pause-Anzeige stimmt nicht | Der Receiver meldet den Pausezustand nicht zuverlässig. Prüfe die Wiedergabe am Fernseher. |
| Karte fehlt oder zeigt alte Inhalte | Ressourcenadresse, Modultyp und gewählte Receiver-Steuerung prüfen; Browser nach einem Update vollständig neu laden. |
| Signalwerte oder Zähler sind unbekannt | Der Receiver liefert möglicherweise keine passenden Werte oder eine Listenabfrage ist fehlgeschlagen. Spätere Abfragen versuchen es erneut. |

Bei Neustart, GUI-Neustart oder Tiefschlaf kann die Verbindung abbrechen, bevor
Home Assistant eine Bestätigung erhält. Der Befehl kann trotzdem angekommen sein.
Prüfe den Receiver, bevor du ihn erneut sendest; auch eine Rückfrage am Fernseher
kann noch offen sein. Ein unbekannter Zustand bei **Bildschirmnachricht** vor der
ersten Nachricht ist hingegen kein Verbindungsfehler.

Für weitere Hilfe melde im
[Issue-Tracker](https://github.com/topic2k/enigma2-connect/issues) die Schritte,
das erwartete und tatsächliche Verhalten sowie HA-Version, Receiver-Modell und
OpenWebif-Version. Unter **Geräte & Dienste** kannst du einen Diagnoseexport
herunterladen. Dieser enthält Abrufstatus und Anzahlen, keine Zugangsdaten,
Netzwerkadressen, Sendernamen oder Aufnahmetitel.

Die Oberfläche ist deutsch und englisch. Die Fernbedienung folgt deiner
Profilsprache, die Aufnahmekachel und automatisch vergebene Entitätsnamen der
HA-Systemsprache. Für andere Sprachen wird Englisch verwendet. Eigene Namen
und Receiver-Texte werden nicht übersetzt.

### Reparaturhinweis zu FFmpeg

**FFmpeg für Aufnahmebilder fehlt** bedeutet, dass die gewählte Snapshot-Quelle
kein ausführbares FFmpeg findet. Installiere FFmpeg in der Home-Assistant-Laufzeit
oder korrigiere den dort konfigurierten Programmpfad; lade danach Enigma2 Connect
neu. Alternativ entferne in den Receiver-Einstellungen die Bildquelle
**Snapshot aus der Aufnahme** und speichere. Dann verschwindet der Hinweis.
Receiver-Steuerung und Medienlisten bleiben währenddessen bedienbar. Beim
Entfernen des Receiver-Eintrags wird auch sein Reparaturhinweis entfernt.

### Streaming-Fehler untersuchen

Aktiviere in Home Assistant bei Enigma2 Connect die Debug-Protokollierung und
starte den betroffenen Stream erneut. Die Meldungen mit `[stream=…]` zeigen den
Verarbeitungsweg, erkannte Formate und Rückfallgründe. Dieselbe Kennung gehört
zu derselben Wiedergabesitzung. Beim linearen Kompatibilitätsmodus werden Eingangsformate
nicht geprüft (`not_probed`); VOD prüft die Aufnahme auch in diesem Modus. Technische Einzelheiten und
aktuelle Qualitätsvorgaben stehen in der [Entwicklerdokumentation](ENTWICKLUNG.md#streaming-diagnose-und-qualität).

## Aktualisieren und entfernen

Erstelle vor einem Update eine HA-Sicherung und lies das
[Changelog](../CHANGELOG.md). Ersetze bei manueller Installation den
Komponentenordner durch die neue Fassung und starte Home Assistant neu.
Aktualisiere die Fernbedienungskarte separat wie oben beschrieben.

Zum Entfernen lösche den Integrationseintrag unter **Geräte & Dienste**. Danach
kannst du den Komponentenordner und die separat eingebundene Kartenressource
entfernen. Die Aufnahmen und Timer auf dem Receiver bleiben erhalten.
