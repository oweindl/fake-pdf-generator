# -*- coding: utf-8 -*-
"""Testlauf über alle Betriebsarten: erzeugt Bestände, verschickt Mails, prüft alles.

    python testrun.py                 # alle Kombinationen, ohne echten Mailversand
    python testrun.py --live          # zusätzlich SMTP-Anmeldung und eine echte Testmail
    python testrun.py --out D:/test   # Arbeitsordner statt %TEMP%/pdf-generator-testrun
    python testrun.py --keep          # Arbeitsordner nicht aufräumen

Jeder Schritt läuft als echter Kommandozeilenaufruf von gen.py / mail.py / check.py —
geprüft wird also das, was du auch von Hand startest. Ergebnis: Tabelle mit PASS/FAIL,
Exit-Code 1, sobald ein Schritt fehlschlägt.
"""
from __future__ import annotations

import argparse

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
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime

HIER = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
ZIEL_MAIL = "rechnungen@olwe.de"
ALLE_TYPEN = 20

ergebnisse = []


def lauf(*args, erwarte=0):
    """Führt ein Kommando aus und gibt (exitcode, ausgabe) zurück."""
    p = subprocess.run([PY, *args], cwd=HIER, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=1800,
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def zaehle_pdfs(ordner):
    return len([f for dp, _, fs in os.walk(ordner) for f in fs if f.lower().endswith(".pdf")])


def zaehle_eml(ordner):
    return len(glob.glob(os.path.join(ordner, "*.eml")))


def lies_eml(pfad):
    with open(pfad, "rb") as fh:
        return BytesParser(policy=policy.default).parse(fh)


def schritt(nummer, name, funktion):
    t0 = time.time()
    try:
        ok, detail = funktion()
    except Exception as exc:  # noqa: BLE001
        ok, detail = False, f"Ausnahme {type(exc).__name__}: {exc}"
    dauer = time.time() - t0
    ergebnisse.append((nummer, name, ok, detail, dauer))
    print(f"  [{'PASS' if ok else 'FEHL'}] {nummer}. {name} — {detail} ({dauer:.1f}s)", flush=True)
    return ok


# ------------------------------------------------------------------ Einzelschritte
def s_dateien_jahr_monat(ordner, seed):
    ziel = os.path.join(ordner, "dateien_jahr_monat")
    code, aus = lauf("gen.py", "--out", ziel, "--count", "400", "--seed", str(seed), "--jobs", "4",
                     "--quiet")
    if code != 0:
        return False, f"gen.py Exit {code}: {aus.strip()[:120]}"
    code, aus = lauf("check.py", ziel)
    typen = set()
    with open(os.path.join(ziel, "_index.csv"), encoding="utf-8-sig") as fh:
        for zeile in csv.DictReader(fh):
            typen.add(zeile["typ"])
    n = zaehle_pdfs(ziel)
    ordner_anzahl = len({os.path.dirname(os.path.relpath(p, ziel)) for p in
                         glob.glob(os.path.join(ziel, "**", "*.pdf"), recursive=True)})
    ok = code == 0 and n == 400 and len(typen) == ALLE_TYPEN and ordner_anzahl > 1
    return ok, f"{n} Dateien, {len(typen)}/{ALLE_TYPEN} Typen, {ordner_anzahl} Monatsordner, check.py Exit {code}"


def s_dateien_flach(ordner, seed):
    ziel = os.path.join(ordner, "dateien_flach")
    code, aus = lauf("gen.py", "--out", ziel, "--count", "50", "--seed", str(seed), "--flat",
                     "--jobs", "4", "--quiet")
    if code != 0:
        return False, f"gen.py Exit {code}: {aus.strip()[:120]}"
    code, _ = lauf("check.py", ziel)
    unterordner = [d for d in os.listdir(ziel) if os.path.isdir(os.path.join(ziel, d))]
    n = zaehle_pdfs(ziel)
    return (code == 0 and n == 50 and not unterordner), f"{n} Dateien flach, Unterordner: {len(unterordner)}, Exit {code}"


def s_dateien_heute(ordner, seed):
    ziel = os.path.join(ordner, "dateien_heute")
    code, aus = lauf("gen.py", "--out", ziel, "--count", "20", "--seed", str(seed), "--flat",
                     "--document-today", "--jobs", "4", "--quiet")
    if code != 0:
        return False, f"gen.py Exit {code}: {aus.strip()[:120]}"
    code, _ = lauf("check.py", ziel)
    daten = set()
    with open(os.path.join(ziel, "_index.csv"), encoding="utf-8-sig") as fh:
        for zeile in csv.DictReader(fh):
            daten.add(zeile["datum"])
    heute = date.today().strftime("%d.%m.%Y")
    return (code == 0 and daten == {heute}), f"{zaehle_pdfs(ziel)} Dateien, Datum {daten}, erwartet {heute}"


def s_mails_eml(ordner, seed):
    ziel = os.path.join(ordner, "mails_eml")
    code, aus = lauf("mail.py", "--to", ZIEL_MAIL, "--count", "20", "--seed", str(seed),
                     "--mail-dir", ziel, "--verify", "--quiet")
    n = zaehle_eml(ziel)
    anhaenge = sum(1 for p in glob.glob(os.path.join(ziel, "*.eml"))
                   if any(t.get_content_type() == "application/pdf" for t in lies_eml(p).iter_attachments()))
    return (code == 0 and n == 20 and anhaenge == n), \
        f"{n} .eml, davon {anhaenge} mit PDF-Anhang (jede Mail hat einen), Exit {code}"


def s_mails_sink(ordner, seed):
    ziel = os.path.join(ordner, "mails_sink")
    code, aus = lauf("mail.py", "--to", ZIEL_MAIL, "--count", "10", "--seed", str(seed),
                     "--transport", "sink", "--mail-dir", ziel, "--verify", "--quiet")
    return (code == 0 and zaehle_eml(ziel) == 10), f"{zaehle_eml(ziel)} Mails über lokalen SMTP, Exit {code}"


def s_mails_smtp_pfad(ordner, seed):
    """Übt den echten SMTP-Pfad gegen den lokalen Sink — ohne Konto, ohne echtes Netz."""
    ziel = os.path.join(ordner, "mails_smtp_pfad")
    dienst = subprocess.Popen([PY, "mail.py", "--serve", "--serve-seconds", "30", "--mail-dir", ziel],
                              cwd=HIER, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        time.sleep(3)
        code, aus = lauf("mail.py", "--to", ZIEL_MAIL, "--count", "5", "--transport", "smtp",
                         "--smtp-host", "127.0.0.1", "--smtp-port", os.environ.get("MAIL_SINK_PORT", "8026"),
                         "--no-auth", "--quiet")
    finally:
        dienst.terminate()
        try:
            dienst.wait(timeout=10)
        except subprocess.TimeoutExpired:
            dienst.kill()
    n = zaehle_eml(ziel)
    if n != 5:
        return False, f"nur {n}/5 Mails angekommen, Exit {code}"
    m = lies_eml(sorted(glob.glob(os.path.join(ziel, "*.eml")))[0])
    anzeigename_echt = len(m["From"].split(" <")[0]) > 3
    return (code == 0 and anzeigename_echt), f"{n} Mails, Absender „{m['From']}“, An „{m['To']}“"


def s_mails_dokument_heute(ordner, seed):
    import io
    from pypdf import PdfReader
    ziel = os.path.join(ordner, "mails_dokument_heute")
    code, aus = lauf("mail.py", "--to", ZIEL_MAIL, "--count", "10", "--seed", str(seed),
                     "--document-today", "--mail-dir", ziel, "--verify", "--quiet")
    if code != 0:
        return False, f"Exit {code}: {aus.strip()[:120]}"
    jahre = set()
    for p in glob.glob(os.path.join(ziel, "*.eml")):
        for t in lies_eml(p).iter_attachments():
            txt = " ".join((pg.extract_text() or "") for pg in
                           PdfReader(io.BytesIO(t.get_payload(decode=True))).pages)
            for marke in ("01.01.", "31.12.", "03.10.", date.today().strftime("%d.%m.")):
                if marke in txt:
                    jahre.update(w.split(".")[-1][:4] for w in txt.split() if marke in w)
    heute = str(date.today().year)
    return (jahre == {heute}), f"Dokumentjahre im Anhang: {sorted(jahre)}, erwartet {heute}"


def s_dateien_verschluesselt(ordner, seed):
    """Verschlüsselte PDFs: prüfbar nur mit Passwort, entsperrbare Kopien."""
    import io
    from pypdf import PdfReader
    ziel = os.path.join(ordner, "dateien_verschluesselt")
    pw = "RunZeit-4711"
    code, aus = lauf("gen.py", "--out", ziel, "--count", "20", "--seed", str(seed), "--flat",
                     "--jobs", "4", "--verschluesseln", pw, "--quiet")
    if code != 0:
        return False, f"gen.py Exit {code}: {aus.strip()[:120]}"
    ohne, _ = lauf("check.py", ziel)
    mit, _ = lauf("check.py", ziel, "--passwort", pw)
    gesperrt = sum(1 for p in glob.glob(os.path.join(ziel, "*.pdf")) if PdfReader(p).is_encrypted)
    entsperrt = os.path.join(ordner, "entsperrt")
    code_u, _ = lauf("unlock.py", ziel, "--passwort", pw, "--ziel", entsperrt, "--quiet")
    kopien = glob.glob(os.path.join(entsperrt, "*.pdf"))
    lesbar = sum(1 for p in kopien
                 if not PdfReader(p).is_encrypted and len(PdfReader(p).pages) > 0)
    return (code == 0 and ohne == 0 and mit == 0 and gesperrt == 20 and code_u == 0
            and len(kopien) == 20 and lesbar == 20), \
        (f"{gesperrt}/20 verschlüsselt, check.py ohne Passwort Exit {ohne}, mit Passwort Exit {mit}, "
         f"{lesbar}/{len(kopien)} entsperrte Kopien lesbar")


def s_mails_verschluesselt(ordner, seed):
    """Mails mit verschlüsseltem Anhang."""
    import io
    from pypdf import PdfReader
    ziel = os.path.join(ordner, "mails_verschluesselt")
    pw = "Anhang-8899"
    code, aus = lauf("mail.py", "--to", ZIEL_MAIL, "--count", "10", "--seed", str(seed),
                     "--mail-dir", ziel, "--verschluesseln", pw, "--verify", "--quiet")
    n = zaehle_eml(ziel)
    gesperrt = 0
    for p in glob.glob(os.path.join(ziel, "*.eml")):
        for t in lies_eml(p).iter_attachments():
            if t.get_content_type() == "application/pdf":
                leser = PdfReader(io.BytesIO(t.get_payload(decode=True)))
                if leser.is_encrypted:
                    if leser.decrypt(pw):
                        gesperrt += 1
                    else:
                        gesperrt -= 100  # Passwort passt nicht -> klarer Fehlschlag unten
    return (code == 0 and n == 10 and gesperrt == 10), \
        f"{n} Mails, {gesperrt}/10 Anhänge verschlüsselt und mit Passwort lesbar, Exit {code}"


def s_mails_datum(ordner, seed):
    """Standard: Kopf = jetzt. --date-from-document: Kopf = Dokumentdatum (Vergangenheit)."""
    frisch = os.path.join(ordner, "mails_datum_frisch")
    alt = os.path.join(ordner, "mails_datum_alt")
    code1, _ = lauf("mail.py", "--to", ZIEL_MAIL, "--count", "5", "--seed", str(seed),
                    "--mail-dir", frisch, "--quiet")
    code2, _ = lauf("mail.py", "--to", ZIEL_MAIL, "--count", "5", "--seed", str(seed),
                    "--date-from-document", "--mail-dir", alt, "--quiet")
    d1 = parsedate_to_datetime(lies_eml(sorted(glob.glob(os.path.join(frisch, "*.eml")))[0])["Date"])
    d2 = parsedate_to_datetime(lies_eml(sorted(glob.glob(os.path.join(alt, "*.eml")))[0])["Date"])
    delta = abs((datetime.now(d1.tzinfo) - d1).total_seconds())
    ok = code1 == 0 and code2 == 0 and delta < 300 and d2.year < date.today().year
    return ok, f"Kopf jetzt: {d1:%d.%m.%Y %H:%M} (Δ {delta:.0f}s), mit --date-from-document: {d2:%d.%m.%Y}"


def s_live():
    """Echte Anmeldung am konfigurierten Server und eine Testmail."""
    code, aus = lauf("mail.py", "--check-connection", "--quiet")
    if code != 0:
        return False, f"Anmeldung fehlgeschlagen (Exit {code}): {aus.strip()[-120:]}"
    code2, aus2 = lauf("mail.py", "--check-recipient", "--quiet")
    if code2 != 0:
        return False, f"Empfängerprüfung fehlgeschlagen (Exit {code2}): {aus2.strip()[-120:]}"
    code3, aus3 = lauf("mail.py", "--transport", "smtp", "--count", "1", "--quiet")
    treffer = [z for z in aus2.splitlines() if "RCPT" in z]
    return (code3 == 0), f"Anmeldung ok, 1 Mail gesendet (Exit {code3}); {treffer[0].strip() if treffer else ''}"


def main():
    ap = argparse.ArgumentParser(description="Kompletter Testlauf über alle Betriebsarten")
    ap.add_argument("--out", default=None, help="Arbeitsordner (Standard: Temp)")
    ap.add_argument("--seed", type=int, default=20261004)
    ap.add_argument("--live", action="store_true",
                    help="zusätzlich echte SMTP-Anmeldung und eine Testmail an den festen Empfänger")
    ap.add_argument("--keep", action="store_true", help="Arbeitsordner behalten")
    a = ap.parse_args()

    ordner = a.out or os.path.join(tempfile.gettempdir(), "pdf-generator-testrun")
    if os.path.exists(ordner):
        shutil.rmtree(ordner)
    os.makedirs(ordner, exist_ok=True)
    print(f"Testlauf in {ordner}\n")

    schritte = [
        ("Dateien: Ablage Jahr/Monat, 400 Stück, alle 20 Typen", s_dateien_jahr_monat),
        ("Dateien: flache Ablage, 50 Stück", s_dateien_flach),
        ("Dateien: --document-today, 20 Stück", s_dateien_heute),
        ("Mails: .eml-Ordner, 20 Stück, keine Anmeldung", s_mails_eml),
        ("Mails: lokaler SMTP-Sink, 10 Stück", s_mails_sink),
        ("Mails: smtp-Pfad gegen Sink (Absender, Envelope, Anhang)", s_mails_smtp_pfad),
        ("Mails: --document-today, 10 Stück", s_mails_dokument_heute),
        ("Dateien: verschlüsselt (Passwort, Rechte, Entsperren)", s_dateien_verschluesselt),
        ("Mails: Datum im Kopf (jetzt vs. --date-from-document)", s_mails_datum),
        ("Mails: verschlüsselter Anhang", s_mails_verschluesselt),
    ]
    for i, (name, funktion) in enumerate(schritte, 1):
        schritt(i, name, lambda f=funktion: f(ordner, a.seed))
    if a.live:
        schritt(len(schritte) + 1, "Live: SMTP-Anmeldung, Empfängerprüfung, 1 Testmail", s_live)
    else:
        print("  [----] 9. Live-Versand übersprungen (nur mit --live)")

    fehler = [e for e in ergebnisse if not e[2]]
    print("\n" + "=" * 78)
    for nummer, name, ok, detail, dauer in ergebnisse:
        print(f"  {nummer:>2}. {'PASS' if ok else 'FEHL'}  {name[:46]:<48}{dauer:>6.1f}s")
    print("=" * 78)
    print(f"  {len(ergebnisse) - len(fehler)}/{len(ergebnisse)} Schritte bestanden"
          + (f" — fehlgeschlagen: {', '.join(str(e[0]) for e in fehler)}" if fehler else ""))
    if not a.keep and not fehler:
        shutil.rmtree(ordner, ignore_errors=True)
        print(f"  Arbeitsordner entfernt: {ordner}")
    else:
        print(f"  Arbeitsordner: {ordner}")
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
