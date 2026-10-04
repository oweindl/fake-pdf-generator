# -*- coding: utf-8 -*-
"""Entsperrt verschlüsselte PDFs: legt lesbare Kopien ohne Passwortschutz ab.

    python unlock.py <ordner> --passwort GEHEIM
    python unlock.py <ordner> --passwort GEHEIM --ziel D:/lesbar
    python unlock.py <datei.pdf> --passwort GEHEIM        # auch einzelne Datei

Die Originale bleiben unangetastet. Standardziel ist <ordner>/entsperrt.
"""
import argparse
import os
import sys

from pypdf import PdfReader, PdfWriter


def _utf8_ausgabe():
    """Kindprozesse schreiben in eine Pipe: ohne das scheitern Umlaute und Pfeile an cp1252."""
    import sys as _sys
    for strom in (_sys.stdout, _sys.stderr):
        try:
            strom.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


_utf8_ausgabe()


def sammle(quelle):
    if os.path.isfile(quelle):
        return [quelle]
    return [os.path.join(dp, f) for dp, _, fs in os.walk(quelle) for f in fs
            if f.lower().endswith(".pdf")]


def main():
    ap = argparse.ArgumentParser(description="Verschlüsselte PDFs entsperren (Kopien ohne Passwort)")
    ap.add_argument("quelle", help="Ordner oder einzelne PDF")
    ap.add_argument("--passwort", "--password", dest="passwort", required=True, help="Passwort der PDFs")
    ap.add_argument("--ziel", default=None, help="Zielordner (Standard: <quelle>/entsperrt)")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    quelle = os.path.abspath(a.quelle)
    if not os.path.exists(quelle):
        print(f"FEHLER: {quelle} gibt es nicht", file=sys.stderr)
        return 2
    ziel = a.ziel or os.path.join(quelle if os.path.isdir(quelle) else os.path.dirname(quelle), "entsperrt")
    os.makedirs(ziel, exist_ok=True)

    dateien = sammle(quelle)
    offen, entsperrt, fehler = 0, [], []
    for p in dateien:
        if os.path.abspath(os.path.dirname(p)) == os.path.abspath(ziel):
            continue  # eigene Ausgabe nicht erneut verarbeiten
        try:
            leser = PdfReader(p)
            if not leser.is_encrypted:
                offen += 1
                continue
            if not leser.decrypt(a.passwort):
                fehler.append((p, "Passwort passt nicht"))
                continue
            schreiber = PdfWriter()
            for seite in leser.pages:
                schreiber.add_page(seite)
            zielname = os.path.splitext(os.path.basename(p))[0] + "_entsperrt.pdf"
            zielpfad = os.path.join(ziel, zielname)
            with open(zielpfad, "wb") as fh:
                schreiber.write(fh)
            entsperrt.append(zielpfad)
            if not a.quiet:
                print(f"  entsperrt: {os.path.relpath(p, quelle)} -> {os.path.relpath(zielpfad, os.path.dirname(ziel))}")
        except Exception as exc:  # noqa: BLE001
            fehler.append((p, f"{type(exc).__name__}: {exc}"))

    print(f"\n{len(dateien)} PDF(s) gefunden: {offen} ohne Verschlüsselung, {len(entsperrt)} entsperrt, "
          f"{len(fehler)} fehlgeschlagen")
    print(f"Lesbare Kopien liegen in: {ziel}")
    for p, grund in fehler[:10]:
        print(f"  FEHLER {os.path.basename(p)}: {grund}")
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
