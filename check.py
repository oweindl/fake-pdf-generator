# -*- coding: utf-8 -*-
"""Prüft einen erzeugten PDF-Bestand: Lesbarkeit, Textlayer, Adressat, Seiten, Ablage, Index.

Aufruf: python check.py <ordner>
Funktioniert für Ablage nach Jahr/Monat und für flache Ablage (--flat).
"""
import collections

def _utf8_ausgabe():
    """Kindprozesse schreiben in eine Pipe: ohne das scheitern Umlaute und Pfeile an cp1252."""
    import sys as _sys
    for strom in (_sys.stdout, _sys.stderr):
        try:
            strom.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


_utf8_ausgabe()

import csv
import os
import statistics
import sys
from multiprocessing import Pool

from pypdf import PdfReader

# Dokumenttypen, die begrifflich nicht an die eigene Firma adressiert sind (Rundschreiben an Mitglieder)
OHNE_ANSCHRIFT = {"rundschreiben"}


def check(p):
    try:
        with open(p, "rb") as fh:
            if fh.read(4) != b"%PDF":
                return "kein PDF-Header", (p, 0, False)
        reader = PdfReader(p)
        pages = len(reader.pages)
        if pages < 1:
            return "keine Seite", (p, 0, False)
        text = " ".join("".join((pg.extract_text() or "") for pg in reader.pages).split())
        if len(text) < 40:
            return "kein Textlayer", (p, pages, False)
        return None, (p, pages, "Vollmer Elektrotechnik" in text)
    except Exception as exc:  # noqa: BLE001
        return "Fehler " + type(exc).__name__, (p, 0, False)


def main(base):
    base = os.path.normpath(base)
    disk = [os.path.join(dp, f) for dp, _, fs in os.walk(base) for f in fs
            if f.lower().endswith(".pdf")]
    idx_path = os.path.join(base, "_index.csv")
    rows = list(csv.DictReader(open(idx_path, encoding="utf-8-sig"))) if os.path.exists(idx_path) else []
    typ_pfad = {(r.get("ordner", ""), r["datei"]): r["typ"] for r in rows}
    typ_name = {r["datei"]: r["typ"] for r in rows}
    if rows:
        print(f"Index: {os.path.relpath(idx_path, base)} mit {len(rows)} Zeilen | PDFs auf Platte: {len(disk)}")
    else:
        print(f"Kein _index.csv im Ordner | PDFs auf Platte: {len(disk)}")

    bad, pages, ohne_adressat, ohne_index = collections.Counter(), [], [], []
    with Pool(min(12, max(1, (os.cpu_count() or 2) - 2))) as pool:
        for err, info in pool.imap_unordered(check, disk, chunksize=25):
            path, n_pages, hat_firma = info
            name = os.path.basename(path)
            if err:
                bad[err] += 1
                if sum(bad.values()) <= 15:
                    print("   ", err, ":", path[:95])
                continue
            pages.append(n_pages)
            rel = os.path.relpath(path, base)
            typ = typ_pfad.get((os.path.dirname(rel).replace("\\", "/"), name)) or typ_name.get(name)
            if typ in OHNE_ANSCHRIFT or "rundschreiben" in name.lower():
                pass
            elif not hat_firma:
                ohne_adressat.append(rel)
            if rows and name not in typ_name:
                ohne_index.append(rel)
    print("Defekte/leere PDFs:", dict(bad) if bad else "keine")
    print("Dokumente ohne Adressat im Text:", len(ohne_adressat))
    for rel in ohne_adressat[:10]:
        print("   ", rel)
    if pages:
        print(f"Seiten: Ø {statistics.mean(pages):.2f} | max {max(pages)} | gesamt {sum(pages)}")
    print(f"Größe gesamt: {sum(os.path.getsize(p) for p in disk)/1048576:.1f} MB")

    rel_all = [os.path.relpath(p, base) for p in disk]
    ordner = collections.Counter(os.path.dirname(r) or "(flach)" for r in rel_all)
    if len(ordner) == 1 and "(flach)" in ordner:
        print("Ablage: flach (kein Jahr/Monat-Unterordner)")
    else:
        print(f"Ordner: {len(ordner)} | kleinster: {min(ordner.items(), key=lambda x: x[1])} "
              f"| größter: {max(ordner.items(), key=lambda x: x[1])}")
    jahre = collections.Counter(r["ordner"][:4] for r in rows) if rows else \
        collections.Counter(o[:4] for o in ordner if o[:4].isdigit())
    if jahre:
        print("Dokumente je Jahr:", dict(sorted(jahre.items())))

    namen = collections.Counter(os.path.basename(p) for p in disk)
    print("gleiche Dateinamen:", sum(1 for n, c in namen.items() if c > 1))
    ill = [p for p in disk if any(c in os.path.basename(p) for c in '<>:"/\\|?*')]
    print("Illegale Zeichen im Namen:", len(ill),
          "| längster Name:", max(len(os.path.basename(p)) for p in disk), "Zeichen")
    print("Endungen:", dict(collections.Counter(os.path.splitext(p)[1] for p in disk)))

    fehlend = [r["datei"] for r in rows
               if not os.path.exists(os.path.join(base, r.get("ordner", ""), r["datei"]))
               and not os.path.exists(os.path.join(base, r["datei"]))]
    print("Index ↔ Platte:", f"{len(fehlend)} Index-Einträge ohne Datei, "
          f"{len(ohne_index)} Dateien ohne Index-Eintrag" if (fehlend or ohne_index or not rows)
          else "vollständig")
    return 1 if (bad or ohne_adressat or fehlend or (rows and ohne_index)) else 0


if __name__ == "__main__":
    # Exit-Code 1 bei Befunden — nutzbar für CI und Skripte
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
