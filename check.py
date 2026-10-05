# -*- coding: utf-8 -*-
"""Prüft einen erzeugten PDF-Bestand: Lesbarkeit, Textlayer, Adressat, Seiten, Ablage, Index.

Aufruf: python check.py <ordner> [--passwort PASSWORT]
Funktioniert für Ablage nach Jahr/Monat und für flache Ablage (--flat).
Verschlüsselte PDFs gelten nicht als Defekt: ohne Passwort werden sie als "verschlüsselt,
nicht geprüft" gezählt, mit --passwort werden sie entschlüsselt und vollständig geprüft.
"""
import argparse
import collections
import csv
import os
import statistics
import sys
from multiprocessing import Pool

from pypdf import PdfReader


def _utf8_ausgabe():
    """Kindprozesse schreiben in eine Pipe: ohne das scheitern Umlaute und Pfeile an cp1252."""
    import sys as _sys
    for strom in (_sys.stdout, _sys.stderr):
        try:
            strom.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


_utf8_ausgabe()

# Dokumenttypen, die begrifflich nicht an die eigene Firma adressiert sind (Rundschreiben an Mitglieder)
OHNE_ANSCHRIFT = {"rundschreiben"}


def check(argumente):
    p, passwort = argumente
    try:
        with open(p, "rb") as fh:
            if fh.read(4) != b"%PDF":
                return "kein PDF-Header", (p, 0, False, False)
        reader = PdfReader(p)
        # Wichtig: is_encrypted VOR dem Zugriff auf pages prüfen, sonst kommt FileNotDecryptedError
        verschluesselt_datei = reader.is_encrypted
        if verschluesselt_datei:
            if not passwort:
                return None, (p, 0, False, True)   # verschlüsselt, ohne Passwort nicht prüfbar
            if not reader.decrypt(passwort):
                return "Passwort passt nicht", (p, 0, False, True)
        pages = len(reader.pages)
        if pages < 1:
            return "keine Seite", (p, 0, False, False)
        text = " ".join("".join((pg.extract_text() or "") for pg in reader.pages).split())
        if len(text) < 40:
            return "kein Textlayer", (p, pages, False, gesperrt)
        return None, (p, pages, "Vollmer Elektrotechnik" in text, verschluesselt_datei)
    except Exception as exc:  # noqa: BLE001
        return "Fehler " + type(exc).__name__, (p, 0, False, False)


def main():
    ap = argparse.ArgumentParser(description="PDF-Bestand prüfen")
    ap.add_argument("ordner", nargs="?", default=".")
    ap.add_argument("--passwort", "--password", dest="passwort", default=None,
                    help="Passwort für verschlüsselte PDFs (sonst werden sie nur gezählt)")
    a = ap.parse_args()
    base = os.path.normpath(a.ordner)

    disk = [os.path.join(dp, f) for dp, _, fs in os.walk(base) for f in fs
            if f.lower().endswith(".pdf")]
    idx_path = os.path.join(base, "_index.csv")
    rows = list(csv.DictReader(open(idx_path, encoding="utf-8-sig"))) if os.path.exists(idx_path) else []
    typ_pfad = {(r.get("ordner", ""), r["datei"]): r["typ"] for r in rows}
    typ_name = {r["datei"]: r["typ"] for r in rows}
    laut_index_verschluesselt = {r["datei"] for r in rows if r.get("verschluesselt") == "ja"}
    verschluesselt_pfad = {(r.get("ordner", ""), r["datei"]) for r in rows
                           if r.get("verschluesselt") == "ja"}
    if rows:
        print(f"Index: {os.path.relpath(idx_path, base)} mit {len(rows)} Zeilen | PDFs auf Platte: {len(disk)}")
    else:
        print(f"Kein _index.csv im Ordner | PDFs auf Platte: {len(disk)}")
    if a.passwort:
        print("Passwort angegeben: verschlüsselte Dateien werden mitgeprüft")

    bad, pages, ohne_adressat, ohne_index = collections.Counter(), [], [], []
    verschluesselt = []
    mit_passwort_gelesen = []
    verschluesselt_ohne_index = []
    index_behauptet_verschluesselt = []
    with Pool(min(12, max(1, (os.cpu_count() or 2) - 2))) as pool:
        for err, info in pool.imap_unordered(check, [(p, a.passwort) for p in disk], chunksize=25):
            path, n_pages, hat_firma, gesperrt = info
            name = os.path.basename(path)
            if err:
                bad[err] += 1
                if sum(bad.values()) <= 15:
                    print("   ", err, ":", path[:95])
                continue
            schluessel = (os.path.dirname(os.path.relpath(path, base)).replace("\\", "/"), name)
            sagt_index = schluessel in verschluesselt_pfad or name in laut_index_verschluesselt
            if gesperrt and not a.passwort:
                verschluesselt.append(os.path.relpath(path, base))
                if not sagt_index:
                    verschluesselt_ohne_index.append(name)
                continue
            if sagt_index:
                (mit_passwort_gelesen if gesperrt else index_behauptet_verschluesselt).append(
                    os.path.relpath(path, base))
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
    if verschluesselt:
        print(f"Verschlüsselt (ohne Passwort nicht geprüft): {len(verschluesselt)}")
        for rel in verschluesselt[:5]:
            print("   ", rel)
        if verschluesselt_ohne_index:
            print(f"   ACHTUNG: {len(verschluesselt_ohne_index)} davon sind im Index nicht als verschlüsselt vermerkt")
    if mit_passwort_gelesen:
        print(f"Entschlüsselt und geprüft: {len(mit_passwort_gelesen)}")
    if index_behauptet_verschluesselt:
        print(f"ACHTUNG: {len(index_behauptet_verschluesselt)} Datei(en) sind laut Index verschlüsselt, "
              f"aber offen lesbar:")
        for rel in index_behauptet_verschluesselt[:5]:
            print("   ", rel)
    print("Dokumente ohne Adressat im Text:", len(ohne_adressat))
    for rel in ohne_adressat[:10]:
        print("   ", rel)
    if pages:
        print(f"Seiten (geprüfte Dateien): Ø {statistics.mean(pages):.2f} | max {max(pages)} | gesamt {sum(pages)}")
    print(f"Größe gesamt: {sum(os.path.getsize(p) for p in disk)/1048576:.1f} MB")

    rel_all = [os.path.relpath(p, base) for p in disk]
    ordner = collections.Counter(os.path.dirname(r) or "(flach)" for r in rel_all)
    if len(ordner) == 1 and "(flach)" in ordner:
        print("Ablage: flach (kein Jahr/Monat-Unterordner)")
    else:
        print(f"Ordner: {len(ordner)} | kleinster: {min(ordner.items(), key=lambda x: x[1])} "
              f"| größter: {max(ordner.items(), key=lambda x: x[1])}")
    jahre = collections.Counter(r.get("ordner", "")[:4] for r in rows) if rows else \
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
    return 1 if (bad or ohne_adressat or fehlend or (rows and ohne_index)
                 or verschluesselt_ohne_index or index_behauptet_verschluesselt) else 0


if __name__ == "__main__":
    # Exit-Code 1 bei Befunden — nutzbar für CI und Skripte
    sys.exit(main())
