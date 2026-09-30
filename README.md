# fake-pdf-generator

Erzeugt massenhaft realistische Fake-PDFs für Testumgebungen: Posteingang eines kleinen
Handwerksbetriebs — Rechnungen, Mahnungen, Lieferscheine, Angebote, Kontoauszüge, Verträge,
Behördenpost, Formulare, Quittungen, Lohnabrechnungen, Inventurlisten und mehr.

Gedacht für Lasttests, DMS-/Archiv-Tests, OCR-Pipelines, Klassifizierung, Volltextsuche,
Import-Tests — dort, wo echte Dokumente fehlen oder nicht verwendet werden dürfen.

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

## Verifikation

```bash
python check.py ./out
```

Lädt jede Datei einzeln mit pypdf und meldet: defekte/leere PDFs, fehlendes Textlayer,
Dokumente ohne Firmenbezug, Seitenverteilung, Gesamtgröße, Ordner- und Namensstruktur,
Abweichungen zwischen Index und Platte.

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
