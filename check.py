# -*- coding: utf-8 -*-
"""Prüft einen erzeugten PDF-Bestand: Lesbarkeit, Text, Seiten, Ordner-/Namensstruktur."""
import collections
import csv
import os
import statistics
import sys
from multiprocessing import Pool

from pypdf import PdfReader


def check(p):
    try:
        with open(p, "rb") as fh:
            if fh.read(4) != b"%PDF":
                return "kein PDF-Header", p
        r = PdfReader(p)
        n = len(r.pages)
        if n < 1:
            return "keine Seite", p
        t = "".join((pg.extract_text() or "") for pg in r.pages)
        if len(t.strip()) < 40:
            return "kein Textlayer", p
        if "Vollmer Elektrotechnik" not in " ".join(t.split()) and "/rundschreiben" not in p:
            return "ohne Firmenbezug", p
        return None, (n, len(t))
    except Exception as exc:  # noqa: BLE001
        return "Fehler " + type(exc).__name__, p


def main(base):
    disk = [os.path.join(dp, f) for dp, _, fs in os.walk(base) for f in fs if f.lower().endswith(".pdf")]
    rows = list(csv.DictReader(open(os.path.join(base, "_index.csv"), encoding="utf-8-sig")))
    print("Index-Zeilen:", len(rows), "| PDFs auf Platte:", len(disk))
    bad, pages = collections.Counter(), []
    with Pool(12) as pool:
        for err, info in pool.imap_unordered(check, disk, chunksize=25):
            if err:
                bad[err] += 1
                if sum(bad.values()) <= 15:
                    print("   ", err, ":", info[:90])
            else:
                pages.append(info[0])
    print("Defekte/leere/fremde PDFs:", dict(bad) if bad else "keine")
    print("Seiten: Ø", round(statistics.mean(pages), 2), "| max", max(pages), "| gesamt", sum(pages))
    print("Größe gesamt:", round(sum(os.path.getsize(p) for p in disk) / 1048576, 1), "MB")
    mon = collections.Counter("/".join(p.replace(base, "").strip("\\/").split(os.sep)[:2]) for p in disk)
    print("Ordner:", len(mon), "| kleinster:", min(mon.items(), key=lambda x: x[1]),
          "| größter:", max(mon.items(), key=lambda x: x[1]))
    print("Jahre:", dict(sorted(collections.Counter(k[:4] for k in disk).items())))
    names = collections.Counter(os.path.basename(p) for p in disk)
    print("gleiche Dateinamen (nur in verschiedenen Monaten):", sum(1 for n, c in names.items() if c > 1))
    ill = [p for p in disk if any(c in os.path.basename(p) for c in '<>:"/\\|?*')]
    print("Illegale Zeichen im Namen:", len(ill), "| längster Name:", max(len(os.path.basename(p)) for p in disk), "Zeichen")
    endungen = collections.Counter(os.path.splitext(p)[1] for p in disk)
    print("Endungen:", dict(endungen))
    rows_mon = collections.Counter(r["ordner"] for r in rows)
    diff = {k: (mon.get(k, 0), v) for k, v in rows_mon.items() if mon.get(k, 0) != v}
    print("Abweichung Index <-> Platte:", diff if diff else "keine")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "D:/pdf-temp")
