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
# 1) Kein Konto, kein Netz: Mail als .eml-Datei ablegen (Standard)
python mail.py --to "Vollmer Elektrotechnik GmbH <eingang@vollmer-elektro.de>" \
               --count 50 --seed 20260927 --mail-dir ./mails --verify

# 2) Lokaler SMTP-Server auf 127.0.0.1:8026 nimmt die Mails entgegen (echter SMTP-Pfad, kein Konto)
python mail.py --to eingang@vollmer-elektro.de --count 20 --transport sink --mail-dir ./mails --verify

# 3) Echte Zustellung über einen vorhandenen Server (braucht Zugangsdaten)
python mail.py --to empfänger@example.de --count 5 --transport smtp \
               --smtp-host smtp.example.com --smtp-port 587 --smtp-user benutzer --smtp-pass geheim \
               --from noreply@example.com
```

| Option | Bedeutung | Default |
|---|---|---|
| `--to` | fester Empfänger, auch `Anzeigename <adresse>` | Pflicht |
| `--count` / `--seed` | Anzahl / Basis-Seed (wie `gen.py`) | 50 / 20260927 |
| `--transport` | `file` (Standard), `sink`, `smtp` | file |
| `--mail-dir` | Ablageordner für die `.eml`-Dateien | ./mails |
| `--smtp-host/-port/-user/-pass` | Zugangsdaten für echte Zustellung (auch `SMTP_HOST` … aus der Umgebung) | – |
| `--from` | Absenderadresse überschreiben (z. B. `noreply@…`) | Absender des Dokuments |
| `--rate` | Mails pro Sekunde | 20 |
| `--verify` | abgelegte Mails zurücklesen und prüfen | aus |

Was in den Mails steckt: deutscher Anschreiben-Text zum Dokument (Rechnung, Mahnung, Angebot,
Behördenformular …), teils zusätzlich als HTML, ~78 % mit dem PDF im Anhang, 18 % als `AW:`-Antwort,
8 % Werbe-/Verteilerpost. Betreff, Absender, Message-ID und Datum passen zum Dokument.

`--verify` liest die `.eml`-Dateien mit dem Standard-`email`-Parser zurück und prüft Empfänger,
Textteil und ob sich jeder PDF-Anhang öffnen lässt; Exit-Code 1 bei Befunden.

Transport `file` und `sink` brauchen **kein E-Mail-Konto**: Dateien bzw. `127.0.0.1` genügen.
Ein Postfach auf einem fremden Server lässt sich ohne Zugangsdaten nicht beliefern — für echte
Zustellung ist ein Account, ein Testdienst (MailHog/Mailtrap/Postmark) oder ein eigener Relay nötig.

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
