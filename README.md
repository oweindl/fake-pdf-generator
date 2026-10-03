# fake-pdf-generator

Erzeugt massenhaft realistische Fake-PDFs für Testumgebungen: Posteingang eines kleinen
Handwerksbetriebs — Rechnungen, Mahnungen, Lieferscheine, Angebote, Kontoauszüge, Verträge,
Behördenpost, Formulare, Quittungen, Lohnabrechnungen, Inventurlisten und mehr.

Zwei Betriebsarten: **Dateien** (`gen.py` → PDF-Bestand) und **E-Mail** (`mail.py` → dieselben
Dokumente als Mails an einen festen Adressaten, Anhang als PDF).

Gedacht für Lasttests, DMS-/Archiv-Tests, OCR-Pipelines, Klassifizierung, Volltextsuche,
Mail-Ingestion- und Import-Tests — dort, wo echte Dokumente fehlen oder nicht verwendet werden dürfen.

Alle Firmen, Personen, Adressen, IBANs, Rechnungsnummern und Beträge sind **frei erfunden**.
Es besteht kein Personenbezug.

## Ergebnis

* **20 Dokumenttypen** mit Gewichten (realistischer Mix, Rechnung ≈ 29 %)
* Ablage nach **Jahr/Monat** des Dokumentdatums (optional flach mit `--flat`)
* **chaotisch-realistische Dateinamen** wie in echten Postfächern:
  `Scan_2024-03-12_0007.pdf`, `SCAN71264.PDF`, `Kopie von rechnung_612.pdf`,
  `rechnung April 2022 Müller.pdf`, `0000039.pdf`, gemischte Endungen `.pdf/.PDF/.Pdf`
* **eine simulierte Firma** als Empfängerin aller Eingänge (`SIM_FIRMA` in `pools.py`),
  Absender je Typ passend: Finanzamt → Steuerbescheid, Steuerkanzlei → Lohnabrechnung,
  Bank → Kontoauszug, Versicherung → Police, Spedition → Frachtbrief, Kunde → Bestellung/Reklamation
* echtes **Textlayer** in jeder Datei (durchsuchbar, keine Scans), Fußzeile mit Seitenzahl,
  volle PDF-Metadaten (Titel, Autor, Subject, Keywords)
* anschließend `_index.csv` mit Datei, Typ, Titel, Datum, Ordner, Absender, Empfänger,
  Nummer, Betrag, Seiten, Bytes — direkt als Import-/Mapping-Vorlage nutzbar

Richtwerte (12 Prozesse, Windows): **10.000 PDFs ≈ 38 MB, ≈ 12.700 Seiten, ~18 Sekunden, 0 Fehler.**

## Kommandoübersicht

```bash
# --- Dateien ---------------------------------------------------------------
python gen.py --out D:/pdf-temp --count 10000 --seed 20260927 --jobs 12   # großer Bestand, Jahr/Monat
python gen.py --out ./eingang   --count 5 --flat                        # 5 Dateien flach (Watchfolder)
python gen.py --out ./heute     --count 20 --flat --document-today      # nur mit heutigem Datum
python check.py ./out                                                    # Bestand prüfen (Exit 1 bei Befund)

# --- Mails (Empfänger steht in mail.env) -----------------------------------
python mail.py --count 5 --mail-dir ./mails --verify                     # .eml ablegen, kein Konto
python mail.py --count 20 --transport sink --verify                      # über lokalen SMTP-Server
python mail.py --transport smtp --count 1                                # echt senden (Konto nötig)
python mail.py --transport smtp --count 1 --document-today               # Dokument im Anhang auf heute
python mail.py --count 5 --date-from-document                            # Kopf mit Dokumentdatum
python mail.py --check-connection                                        # Anmeldung testen, sendet nichts
python mail.py --check-recipient                                         # existiert der Empfänger?
python mail.py --verify-imap --count 1                                   # Zustellung im Postfach nachsehen
python mail.py --imap-list 10                                            # Postfach ansehen
python mail.py --serve --serve-seconds 120                               # nur Sink betreiben (Testserver)

# --- alles auf einmal ------------------------------------------------------
python testrun.py            # 8 Kombinationen durchprüfen (Dateien, Mails, Datumsarten, SMTP-Pfad)
python testrun.py --live     # zusätzlich echte Anmeldung und eine Testmail
./testlauf.sh                # dasselbe, richtet bei Bedarf .venv und Abhängigkeiten ein
testlauf.cmd                 # Windows-Variante
```

## Testlauf über alle Kombinationen

`testrun.py` fährt die Betriebsarten als echte Kommandozeilenaufrufe durch und meldet PASS/FAIL:

| # | Schritt | Prüft |
|---|---|---|
| 1 | Dateien Jahr/Monat, 400 Stück | alle 20 Dokumenttypen, 45 Monatsordner, `check.py` fehlerfrei |
| 2 | Dateien flach, 50 Stück | keine Unterordner, `check.py` fehlerfrei |
| 3 | Dateien `--document-today`, 20 Stück | Dokumentdatum = heute |
| 4 | Mails als `.eml`, 20 Stück | Empfänger, Text, PDF-Anhänge (`--verify`) |
| 5 | Mails über lokalen SMTP-Sink, 10 Stück | echter SMTP-Pfad ohne Konto |
| 6 | Mails über `smtp`-Transport gegen Sink | Envelope, Absenderadresse, Anzeigename, Anhang |
| 7 | Mails `--document-today`, 10 Stück | Anhänge tragen das laufende Jahr |
| 8 | Mail-Kopf-Datum | jetzt (Δ < 5 min) vs. `--date-from-document` (Vergangenheit) |
| 9 | `--live` | SMTP-Anmeldung, Empfängerprüfung, 1 echte Testmail |

```bash
python testrun.py                 # ohne echten Versand, räumt den Arbeitsordner danach weg
python testrun.py --keep          # Arbeitsordner behalten
python testrun.py --out D:/test   # eigener Arbeitsordner
python testrun.py --live          # schickt wirklich eine Mail an MAIL_TO
```

Exit-Code 1, sobald ein Schritt fehlschlägt — in CI und Skripten auswertbar. In
`.github/workflows/ci.yml` läuft er bei jedem Push auf Python 3.12, 3.13 und 3.14.

## Leitstand: Oberfläche für alles

```bash
python panel.py                    # startet http://127.0.0.1:8765 und öffnet den Browser
python panel.py --port 9000 --no-browser
python panel.py --selftest         # Smoke-Test ohne Browser (läuft in der CI)
node ui_smoke.mjs                  # Oberflächentest: DOM-Shim + echter Server, prüft jeden Knopf
```

Kleine lokale Oberfläche mit Formularen, Live-Ausgabe, Stop-Knopf und Liste der letzten Läufe:

| Bereich | Aktionen |
|---|---|
| PDFs erzeugen | Zielordner, Anzahl, Seed, Prozesse, Ablage (Jahr/Monat oder flach), Datum (2023–2026 oder heute) — plus „Bestand prüfen“ |
| Mails senden | Anzahl, Seed, Transport (file/sink/smtp), Datum im Kopf, Ablage, Dokument auf heute |
| Mailserver & Postfach | Anmeldung prüfen, Empfängeradresse prüfen, neueste Mails ansehen |
| Testlauf & Testserver | kompletter Testlauf (optional mit echter Testmail), SMTP-Testserver starten |

Der Server bindet nur an `127.0.0.1`, braucht keine Anmeldung und führt **ausschließlich fest
verdrahtete Kommandos** aus: Aktionen werden als Argumentlisten zusammengesetzt (keine Shell),
Zahlen auf erlaubte Bereiche geprüft, Pfade auf Steuerzeichen. Feldwerte merkt sich der Browser
(`localStorage`). `ui_smoke.mjs` fährt jeden Knopf an und lässt einen echten Durchlauf über die
Oberfläche laufen — so fallen Formularfehler auf, ohne dass jemand klicken muss.

## Installation

```bash
python -m venv .venv
# Windows
.venv/Scripts/python -m pip install -r requirements.txt
# Linux/macOS
.venv/bin/python -m pip install -r requirements.txt
```

Getestet mit Python 3.14, reportlab 5.0.1, pypdf 6.19.0. Keine Schriftdateien nötig
(Basis-14-Schriften Helvetica, Times, Courier).

## Benutzung

```bash
# 10.000 Eingangsdokumente nach ./out, reproduzierbar über den Seed
python gen.py --out ./out --count 10000 --seed 20260927 --jobs 12

# flach (ohne Jahr/Monat-Unterordner), z. B. für einen Eingangs-Watchfolder
python gen.py --out ./watchfolder --count 10 --seed 20261001 --flat

# Index woanders ablegen (hält den Testordner sauber)
python gen.py --out ./out --count 500 --index ./index.csv
```

| Option | Bedeutung | Default |
|---|---|---|
| `--out` | Zielordner (wird angelegt) | Pflicht |
| `--count` | Anzahl der PDFs | 10000 |
| `--seed` | Basis-Seed; gleicher Seed = identischer Bestand | 20260927 |
| `--jobs` | Parallelprozesse | CPU-Kerne − 2 |
| `--flat` | keine Jahr/Monat-Unterordner | aus |
| `--index` | Pfad der Index-CSV | `<out>/_index.csv` |
| `--quiet` | kein Fortschritt auf stdout | aus |

## Beispieldateien

`examples/` enthält 50 fertige PDFs (alle 20 Dokumenttypen, ~190 KB) samt `examples/_index.csv`,
erzeugt mit `--seed 4711`. Damit lässt sich eine Demo-Umgebung sofort befüllen, ohne den
Generator laufen zu lassen:

```bash
cp examples/*.pdf /pfad/zum/eingangsordner/
```

## E-Mails senden

`mail.py` baut dieselben Dokumente (gleiche Seeds → gleicher Inhalt) und verschickt sie als Mails
an **einen festen Adressaten**. Ohne konfiguriertes E-Mail-Konto nutzbar:

```bash
# 0) Empfänger steht in mail.env (MAIL_TO) — reicht für den Normalfall
python mail.py --count 5 --mail-dir ./mails --verify

# 1) Kein Konto, kein Netz: Mail als .eml-Datei ablegen (Standard, Empfänger explizit)
python mail.py --to "Vollmer Elektrotechnik GmbH <eingang@vollmer-elektro.de>" \
               --count 20 --seed 20260927 --mail-dir ./mails --verify

# 2) Lokaler SMTP-Server auf 127.0.0.1:8026 nimmt die Mails entgegen (echter SMTP-Pfad, kein Konto)
python mail.py --to eingang@vollmer-elektro.de --count 20 --transport sink --mail-dir ./mails --verify

# 3) Echte Zustellung über einen vorhandenen Server (braucht Zugangsdaten)
python mail.py --to empfänger@example.de --count 5 --transport smtp \
               --smtp-host smtp.example.com --smtp-port 587 --smtp-user benutzer --smtp-pass geheim \
               --from noreply@example.com
```

| Option | Bedeutung | Default |
|---|---|---|
| `--to` | fester Empfänger, auch `Anzeigename <adresse>` | `MAIL_TO` aus `mail.env` |
| `--count` / `--seed` | Anzahl / Basis-Seed (wie `gen.py`) | 5 / 20260927 |
| `--document-today` | auch das Dokument selbst auf heute datieren (Nummern ziehen das Jahr mit) | aus |
| `--date-from-document` | Mail-Kopf auf das Dokumentdatum setzen statt auf die aktuelle Zeit | aus |
| `--transport` | `file` (Standard), `sink`, `smtp` | file |
| `--mail-dir` | Ablageordner für die `.eml`-Dateien | ./mails |
| `--smtp-host/-port/-user/-pass` | Zugangsdaten für echte Zustellung (auch `SMTP_*` aus `mail.env` oder der Umgebung) | Port 587 |
| `--smtp-ssl` | implizites TLS (Port 465); sonst STARTTLS automatisch | aus |
| `--check-connection` | nur Verbindung und Anmeldung prüfen, nichts senden | aus |
| `--no-auth` | ohne Anmeldung senden (lokale Testserver) | aus |
| `--serve` / `--serve-seconds` | nur den lokalen SMTP-Sink betreiben und auf Post warten | aus / bis Strg-C |
| `--check-recipient` | prüfen, ob die Empfängeradresse auf dem Server existiert (sendet nichts) | aus |
| `--verify-imap` / `--imap-wait` | nach dem Senden im Postfach prüfen, ob die Mails angekommen sind | aus / 45 s |
| `--imap-list N` | nur die neuesten N Mails im Postfach auflisten, nichts senden | aus |
| `--imap-host/-port/-user/-pass` | Posteingangsserver (Standard: `IMAP_HOST`/`SMTP_*`) | 993 |
| `--config` | andere Konfigurationsdatei | `mail.env` neben dem Skript |
| `--from` | Absenderadresse überschreiben (z. B. `noreply@…`) | Absender des Dokuments |
| `--rate` | Mails pro Sekunde | 20 |
| `--verify` | abgelegte Mails zurücklesen und prüfen | aus |

**Datum:** Mails tragen immer das **aktuelle Versanddatum** im Kopf — sie sollen im Postfach oben
stehen, nicht in der Vergangenheit. Das Dokument im Anhang behält seinen eigenen Zeitraum (2023–2026);
mit `--document-today` wird auch dieses auf heute datiert (inklusive Jahr in Rechnungsnummern und
Dateinamen). `--date-from-document` stellt das alte Verhalten wieder her, wenn ein Bestand bewusst
historisch aussehen soll.

Was in den Mails steckt: deutscher Anschreiben-Text zum Dokument (Rechnung, Mahnung, Angebot,
Behördenformular …), teils zusätzlich als HTML, ~78 % mit dem PDF im Anhang, 18 % als `AW:`-Antwort,
8 % Werbe-/Verteilerpost. Betreff, Absender, Message-ID und Datum passen zum Dokument.

`--verify` liest die `.eml`-Dateien mit dem Standard-`email`-Parser zurück und prüft Empfänger,
Textteil und ob sich jeder PDF-Anhang öffnen lässt; Exit-Code 1 bei Befunden.

### Echter Versand: nur vier Zeilen fehlen

`mail.env` (liegt neben `mail.py`, ist in `.gitignore`) enthält den festen Empfänger bereits:

```ini
MAIL_TO=rechnungen@olwe.de
SMTP_HOST=mxe9c5.netcup.net      # Postausgangsserver, Authentifizierung erforderlich
SMTP_PORT=587                    # STARTTLS; alternativ 465 mit SMTP_SSL=true
SMTP_USER=pdfcloud-pro@olwe.de
SMTP_PASS=                       # ← nur dieses Feld fehlt noch
SMTP_FROM=pdfcloud-pro@olwe.de
```

Steht `SMTP_FROM`, wird diese Adresse als Absender gesetzt (Envelope und Header) — der **Anzeigename**
bleibt der Name der erfundenen Firma, die Adresse kommt aus dem eigenen Konto. Ohne das würde der
Fremd-Absender an SPF/DKIM scheitern.

### Zustellung wirklich nachweisen (IMAP)

```bash
python mail.py --transport smtp --count 1 --verify-imap     # senden und im Postfach nachsehen
python mail.py --imap-list 10                               # nur Postfach ansehen
```

`--check-recipient` fragt den Server, ob die Zieladresse existiert — ohne Mailversand. Es wird zusätzlich
eine Kontrolladresse derselben Domain geprüft; wird die nicht abgelehnt, prüft der Server Empfänger nicht
und das Ergebnis ist wertlos:

```
$ python mail.py --check-recipient
Empfängerprüfung (es wird keine Mail gesendet):
  RCPT rechnungen@olwe.de             → 250 2.1.5 Ok
  RCPT gibt-es-nicht-a23588e1@olwe.de → 550 5.1.1 … User unknown in virtual mailbox table
```

`--verify-imap` sammelt die Message-IDs der gesendeten Mails und pollt damit den Posteingang
(IMAP über TLS, `mxe9c5.netcup.net:993`). Gefundene Mails werden mit UID bestätigt; was nicht
auftaucht, wird als „noch nicht zugestellt, gefiltert oder Postfach gehört nicht zu diesem Konto"
ausgewiesen — die Prüfung liest das Postfach von `pdfcloud-pro@olwe.de`, ein getrenntes Postfach
`rechnungen@olwe.de` kann sie nicht einsehen.

Solange das Passwort fehlt, meldet der Test genau das (und sonst nichts):

```
$ python mail.py --check-connection
Konfiguration geladen: .../mail.env
SMTP: mxe9c5.netcup.net:587 als pdfcloud-pro@olwe.de → Empfänger rechnungen@olwe.de, 5 Mail(s)
  Server: ESMTP · Verschlüsselung: STARTTLS · Anmeldemethoden:  DIGEST-MD5 CRAM-MD5 PLAIN LOGIN
FEHLER: In mail.env fehlt noch: SMTP_PASS — Anmeldung daher nicht möglich.
```

Sobald Host/Benutzer/Passwort eingetragen sind:

```bash
python mail.py --transport smtp --count 5 --check-connection   # erst prüfen, sendet nichts
python mail.py --transport smtp --count 5                      # dann wirklich senden
```

Transport `file` und `sink` brauchen **kein E-Mail-Konto**: Dateien bzw. `127.0.0.1` genügen.
Ein Postfach auf einem fremden Server lässt sich ohne Zugangsdaten nicht beliefern — für echte
Zustellung ist ein Account, ein Testdienst (MailHog/Mailtrap/Postmark) oder ein eigener Relay nötig.
Bei `--transport smtp` wird **wirklich versendet**; das Skript gibt vorher Host, Empfänger und Anzahl aus.

## Verifikation

```bash
python check.py ./out
```

Lädt jede Datei einzeln mit pypdf und meldet: defekte/leere PDFs, fehlendes Textlayer,
Dokumente ohne Adressat, Seitenverteilung, Gesamtgröße, Ordner- und Namensstruktur,
Abweichungen zwischen Index und Platte. Funktioniert für Jahr/Monat- und flache Ablage.
Exit-Code 1 bei Befunden — damit in CI oder Skripten auswertbar.

Getestet mit Python 3.12, 3.13 und 3.14 (siehe GitHub-Actions-Lauf).

## Anpassen

* **Firma, Adressen, Kunden, Behörden, Artikel:** `pools.py` — `SIM_FIRMA` ist die simulierte
  Firma, `FIRMEN` die Lieferanten, `KUNDEN_FIRMEN` die Kunden, `INSTITUTIONEN` Banken/Behörden.
* **Verteilung der Dokumenttypen:** Liste `TYPEN` in `gen.py` (Name, Gewicht, Builder).
* **Zeitraum:** Datumsbereich in `derive()` (`gen.py`).
* **Neuer Dokumenttyp:** Builder `doc_xxx(rng, ctx, st) -> (story, meta)` schreiben und in
  `TYPEN` eintragen; `FESTE_ABSENDER` legt den passenden Absendertyp fest.

Wichtig beim Erweitern: ein Dokument = ein Seed. `derive(seed)` erzeugt Datum, Typ, Kontext und
Schrift deterministisch; Dateinamensbildung und Worker rufen es identisch auf, sonst passt der
Dateiname nicht zum Inhalt.

## Bekannte Grenzen

* Nur digitale Text-PDFs — keine Scan-Optik (Bild im PDF, Schräglage, Rauschen). Für OCR-Tests
  wäre zusätzlich Pillow nötig; bewusst noch nicht eingebaut.
* Keine absichtlich kaputten Dateien, keine Duplikate/Doppelscans, keine ZIP-Container.
* Dokumente sind in sich plausibel, aber erfunden: Beträge, Nummernkreise und Steuersätze sind
  zufällig und nicht buchhalterisch konsistent über mehrere Dokumente hinweg.

## Lizenz

MIT — siehe `LICENSE`.
