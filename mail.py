# -*- coding: utf-8 -*-
"""Verschickt generierte Fake-Dokumente als E-Mails an einen festen Adressaten.

Drei Transportwege:
  file  (Standard) schreibt fertige .eml-Dateien in einen Ordner — kein Konto, kein Server, kein Netz.
  sink             startet einen lokalen SMTP-Server (127.0.0.1), verschickt echt per SMTP und
                   legt die Mails als .eml ab — testet den echten SMTP-Pfad, braucht kein Konto.
  smtp             echte Zustellung über einen vorhandenen Server (Host/Port/Benutzer/Passwort).

Aufruf:
    python mail.py --to eingang@vollmer-elektro.de --count 50 --seed 20260927 --mail-dir ./mails --verify
    python mail.py --to eingang@vollmer-elektro.de --count 20 --transport sink --verify
    python mail.py --to eingang@vollmer-elektro.de --count 5 --transport smtp \
        --smtp-host smtp.example.com --smtp-user benutzer --smtp-pass geheim --from noreply@example.com
"""
from __future__ import annotations

import argparse
import io
import os
import random
import smtplib
import sys
import time
from datetime import date, datetime, time as dtime, timedelta
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen as G  # noqa: E402
import pools as P  # noqa: E402

# Betreff- und Textbausteine je Dokumenttyp
MUSTER = {
    "rechnung": ("Rechnung {nr} vom {datum}",
                 "Sehr geehrte Damen und Herren,\n\nanbei erhalten Sie unsere Rechnung {nr} vom {datum} "
                 "über {betrag}.\nZahlungsziel: {ziel} Tage netto ohne Abzug. Bitte geben Sie bei der "
                 "Überweisung die Rechnungsnummer an.\n\nBei Rückfragen stehen wir Ihnen gerne zur Verfügung."),
    "mahnung": ("Zahlungserinnerung zu {nr}",
                "Sehr geehrte Damen und Herren,\n\nzu der Rechnung {nr} über {betrag} konnten wir bis heute "
                "keinen Zahlungseingang feststellen.\nWir bitten um Ausgleich bis zum {frist}.\n\nSollte sich "
                "unser Schreiben mit Ihrer Zahlung überschnitten haben, betrachten Sie es bitte als gegenstandslos."),
    "angebot": ("Angebot {nr}",
                "Sehr geehrte Damen und Herren,\n\nwie besprochen erhalten Sie im Anhang unser Angebot {nr} "
                "über {betrag}.\nDie Preise gelten 30 Tage. Lieferzeit und Ausführung stimmen wir nach "
                "Auftragseingang mit Ihnen ab.\n\nWir würden uns über eine Zusammenarbeit freuen."),
    "lieferschein": ("Lieferschein {nr} — Lieferung an Sie unterwegs",
                     "Sehr geehrte Damen und Herren,\n\nunsere Lieferung ist heute an Sie herausgegangen. "
                     "Den Lieferschein {nr} finden Sie im Anhang.\nBitte prüfen Sie die Ware bei Eingang auf "
                     "Vollständigkeit und Transportschäden."),
    "auftragsbestaetigung": ("Auftragsbestätigung {nr}",
                             "Sehr geehrte Damen und Herren,\n\nvielen Dank für Ihren Auftrag. Wir bestätigen "
                             "die Ausführung unter der Auftragsnummer {nr} zum Gesamtbetrag {betrag}.\n"
                             "Den verbindlichen Liefertermin nennen wir Ihnen mit der Auftragsplanung."),
    "bestellung": ("Bestellung {nr}",
                   "Sehr geehrte Damen und Herren,\n\nim Anhang erhalten Sie unsere Bestellung {nr} über "
                   "{betrag}.\nBitte bestätigen Sie uns Liefertermin und Auftragsnummer kurz per Mail."),
    "gutschrift": ("Gutschrift zu {nr}",
                   "Sehr geehrte Damen und Herren,\n\nanbei die Gutschrift zu {nr} über {betrag}. "
                   "Der Betrag wird mit offenen Posten verrechnet."),
    "reklamation": ("Mängelanzeige zur Lieferung {nr}",
                    "Sehr geehrte Damen und Herren,\n\nbei der Wareneingangsprüfung zur Lieferung {nr} haben "
                    "wir Mängel festgestellt, die wir im Anhang dokumentiert haben.\nWir bitten um Behebung "
                    "innerhalb von zwei Wochen."),
    "brief": ("Ihr Schreiben — {nr}",
              "Sehr geehrte Damen und Herren,\n\nvielen Dank für Ihre Nachricht. Wir haben den Sachverhalt "
              "aufgenommen und melden uns nach Abschluss der Prüfung bei Ihnen.\n\nFür Rückfragen stehen wir "
              "gerne zur Verfügung."),
    "formular": ("Formular {nr} — Rücklauf bis {frist}",
                 "Sehr geehrte Damen und Herren,\n\nanbei erhalten Sie das Formular {nr}. Bitte füllen Sie es "
                 "vollständig aus und senden Sie es bis zum {frist} zurück.\n\nVielen Dank für Ihre Mitwirkung."),
    "kontoauszug": ("Ihr Kontoauszug liegt bereit",
                    "Sehr geehrte Damen und Herren,\n\nIhr Kontoauszug {nr} steht im Anhang bereit.\n"
                    "Bitte prüfen Sie die Buchungen und melden Sie Abweichungen innerhalb von sechs Wochen."),
    "vertrag": ("Vertragsunterlagen {nr}",
                "Sehr geehrte Damen und Herren,\n\nanbei erhalten Sie die Vertragsunterlagen zur Durchsicht.\n"
                "Bitte senden Sie uns ein gegengezeichnetes Exemplar bis zum {frist} zurück."),
    "rundschreiben": ("Rundschreiben {nr}",
                      "Sehr geehrte Damen und Herren,\n\nanbei unser aktuelles Rundschreiben mit den "
                      "Änderungen für die kommenden Monate.\n\nBitte beachten Sie die Hinweise im Einzelnen."),
    "quittung": ("Beleg zu Ihrer Bestellung",
                 "Sehr geehrte Damen und Herren,\n\nanbei der Beleg zu Ihrer Bestellung über {betrag}.\n"
                 "Vielen Dank für Ihren Auftrag."),
    "lohnabrechnung": ("Entgeltabrechnung {nr}",
                       "Sehr geehrte Damen und Herren,\n\nanbei die Entgeltabrechnung AUSZAHLUNG {betrag}.\n"
                       "Einwendungen bitten wir innerhalb von sechs Monaten geltend zu machen."),
    "police": ("Ihr Versicherungsschein {nr}",
               "Sehr geehrte Damen und Herren,\n\nanbei erhalten Sie den Versicherungsschein {nr}.\n"
               "Bitte prüfen Sie die Angaben zu Versicherungssumme und Selbstbehalt."),
    "steuerbescheid": ("Bescheid {nr}",
                       "Sehr geehrte Damen und Herren,\n\nder Bescheid {nr} ist im Anhang beigefügt.\n"
                       "Der ausgewiesene Betrag von {betrag} ist fristgerecht zu zahlen."),
    "frachtbrief": ("Frachtbrief {nr} — Sendung unterwegs",
                    "Sehr geehrte Damen und Herren,\n\nunsere Sendung ist heute verladen worden. Den "
                    "Frachtbrief {nr} finden Sie im Anhang."),
    "inventur": ("Inventurliste {nr}",
                 "Sehr geehrte Damen und Herren,\n\nanbei die Inventurliste {nr} zum Stichtag {datum}.\n"
                 "Bitte um Rückmeldung bei Abweichungen."),
    "protokoll": ("Protokoll {nr}",
                  "Sehr geehrte Damen und Herren,\n\nanbei das Protokoll {nr}.\nWir bitten um Bestätigung "
                  "oder Ergänzung innerhalb einer Woche."),
}
SPAM_BETREFF = [
    "Angebot: Wartung Ihrer Elektroanlage — 15 % Rabatt noch bis Freitag",
    "Achtung: Ihre Rechnung weicht von der Bestellung ab",
    "Ihre Bewertung ist uns wichtig — 3 Fragen, 1 Minute",
    "Neue Fördermittel für Wärmepumpen — Antragsfrist läuft",
    "Einladung: Innungsversammlung mit Fachvortrag",
    "IG-Metall-Tarifinfo für Mitgliedsbetriebe",
]
HTML_RAHMEN = """<html><body style="font-family:Arial,Helvetica,sans-serif;font-size:11pt;color:#222">
<p>{absaetze}</p>
<hr style="border:none;border-top:1px solid #ccc">
<p style="font-size:9pt;color:#666">{absender}<br/>{strasse}<br/>{plz_ort}<br/>Tel. {tel} &middot; {mail}</p>
</body></html>"""


def pdf_bytes(rng, typ, ctx, st, titel):
    """Baut das Dokument wie gen.py, aber in den Speicher statt auf die Platte."""
    story, meta = G.TYP_FUNCS[typ](rng, ctx, st)
    buf = io.BytesIO()
    G.write_pdf(buf, story, ctx, typ, st, meta["titel"])
    return buf.getvalue(), meta


def baue_mail(rng, seed, ziel_adresse, von_adresse=None, zielname="Vollmer Elektrotechnik GmbH"):
    rng, typ, today, ctx, font = G.derive(seed)
    st = G.basis_styles(font)
    text_rng = random.Random(seed ^ 0x5EED)
    daten, meta = pdf_bytes(rng, typ, ctx, st, "")
    nummer = meta["nummer"] or ctx["az"]
    betrag = G.eur(abs(meta["betrag"])) if meta["betrag"] else G.eur(round(text_rng.uniform(48, 3200), 2))
    frist = G.dt(ctx["datum"] + timedelta(days=text_rng.choice([7, 14, 21, 30])))
    if typ in MUSTER:
        betreff, text = MUSTER[typ]
        betreff = betreff.format(nr=nummer, datum=G.dt(ctx["datum"]), betrag=betrag, frist=frist)
        text = text.format(nr=nummer, datum=G.dt(ctx["datum"]), betrag=betrag, frist=frist,
                           ziel=text_rng.choice([14, 30, 30]))
    else:  # nur zur Sicherheit, falls neue Typen dazukommen
        betreff, text = f"{meta['titel']} {nummer}", "Sehr geehrte Damen und Herren,\n\nanbei erhalten Sie die angeforderten Unterlagen."
    if text_rng.random() < 0.08:  # Werbe-/Verteilerpost ohne Anlass
        betreff, text = text_rng.choice(SPAM_BETREFF), rng.choice(P.BRIEF_ABSATZ)

    anrede_name = ctx["bearbeiter"].split()[0]
    signatur = (f"\n\nMit freundlichen Grüßen\n{anrede_name}\n{ctx['absender'][1]} · {ctx['abteilung']}\n"
                f"{ctx['absender'][0]}\nTel. {ctx['absender'][5]}")
    body = text + signatur

    msg = EmailMessage()
    msg["To"] = f"{zielname} <{ziel_adresse}>" if zielname else ziel_adresse
    msg["From"] = von_adresse or f"{ctx['absender'][0]} <{ctx['absender'][6]}>"
    msg["Subject"] = betreff if text_rng.random() > 0.18 else f"AW: {betreff}"
    zeitpunkt = datetime.combine(ctx["datum"], dtime(text_rng.randint(6, 20), text_rng.randint(0, 59),
                                                    text_rng.randint(0, 59)))
    # timestamp() statt Ordinaltag * 86400 — Windows kann Zeitstempel außerhalb ~1970..3000 nicht umrechnen
    msg["Date"] = formatdate(zeitpunkt.timestamp(), localtime=True)
    msg["Message-ID"] = make_msgid(domain=ctx["absender"][6].split("@")[-1])
    msg["Reply-To"] = ctx["absender"][6]

    anhang_gewuenscht = text_rng.random() < 0.78
    if text_rng.random() < 0.3 and anhang_gewuenscht:
        absaetze = "</p><p>".join(l for l in body.split("\n") if l.strip())
        msg.set_content(body)
        msg.add_alternative(HTML_RAHMEN.format(absaetze=absaetze, absender=ctx["absender"][0],
                                              strasse=ctx["absender"][2], plz_ort=f"{ctx['absender'][3]} {ctx['absender'][4]}",
                                              tel=ctx["absender"][5], mail=ctx["absender"][6]), subtype="html")
    else:
        msg.set_content(body)
    if anhang_gewuenscht:
        dateiname = G.make_name(random.Random(seed ^ 0xBEEF), typ, ctx, seed % 9999)
        msg.add_attachment(daten, maintype="application", subtype="pdf", filename=dateiname)
    return msg, typ, betreff, (dateiname if anhang_gewuenscht else None)


class EmlOrdner:
    """Legt jede Mail als .eml-Datei ab — als Ersatz für ein echtes Postfach."""

    def __init__(self, ordner):
        self.ordner = ordner
        os.makedirs(ordner, exist_ok=True)
        self.n = 0

    def speichere(self, msg, nummer):
        self.n += 1
        pfad = os.path.join(self.ordner, f"{nummer:05d}_{msg['Message-ID'].strip('<>').replace('/', '-')[:48]}.eml")
        with open(pfad, "wb") as fh:
            fh.write(msg.as_bytes())
        return pfad


def baue_sink(ordner):
    """Lokaler SMTP-Server, der Mails entgegennimmt und als .eml ablegt."""
    from aiosmtpd.controller import Controller

    ablage = EmlOrdner(ordner)

    class Handler:
        async def handle_DATA(self, server, session, envelope):
            self.zaehler = getattr(self, "zaehler", 0) + 1
            pfad = os.path.join(ablage.ordner, f"{self.zaehler:05d}_{envelope.mail_from.replace('@', '_at_')}.eml")
            with open(pfad, "wb") as fh:
                fh.write(envelope.original_content)
            return "250 Nachricht angenommen"

    return Controller(Handler(), hostname="127.0.0.1", port=int(os.environ.get("MAIL_SINK_PORT", 8026)))


def verifiziere(ordner, ziel, erwartet):
    """Liest die abgelegten Mails zurück und prüft Empfänger, Anhänge und Text."""
    import glob
    import collections
    from email import policy
    from email.parser import BytesParser
    from email.utils import parseaddr
    from pypdf import PdfReader

    dateien = sorted(glob.glob(os.path.join(ordner, "*.eml")))
    falsch_ziel, ohne_text, kaputte_pdfs, mit_anhang, betreffe, absender = [], [], [], 0, [], collections.Counter()
    for p in dateien:
        with open(p, "rb") as fh:
            msg = BytesParser(policy=policy.default).parse(fh)
        if parseaddr(msg["To"])[1] != parseaddr(ziel)[1]:
            falsch_ziel.append((os.path.basename(p), msg["To"]))
        if len((msg.get_body(preferencelist=("plain",)) or msg).get_content().strip()) < 40:
            ohne_text.append(os.path.basename(p))
        absender[msg["From"]] += 1
        betreffe.append(msg["Subject"])
        for teil in msg.iter_attachments():
            if teil.get_content_type() == "application/pdf":
                mit_anhang += 1
                try:
                    if len(PdfReader(io.BytesIO(teil.get_payload(decode=True))).pages) < 1:
                        kaputte_pdfs.append(os.path.basename(p))
                except Exception:  # noqa: BLE001
                    kaputte_pdfs.append(os.path.basename(p))
    print(f"Geprüft: {len(dateien)} Mails in {ordner} (erwartet {erwartet})")
    print(f"  falscher/n Empfänger: {len(falsch_ziel)} | ohne Text: {len(ohne_text)} | "
          f"kaputte PDF-Anhänge: {len(kaputte_pdfs)} | mit PDF-Anhang: {mit_anhang}")
    print(f"  Absender: {len(absender)} verschiedene | Beispiele für Betreffzeilen:")
    for b in betreffe[:5]:
        print("    -", b)
    return 0 if (len(dateien) == erwartet and not falsch_ziel and not ohne_text and not kaputte_pdfs) else 1


def main():
    ap = argparse.ArgumentParser(description="Fake-Dokumente als E-Mail an einen festen Adressaten")
    ap.add_argument("--to", required=True, help="fester Empfänger (Adresse oder Anzeigename <adresse>)")
    ap.add_argument("--count", type=int, default=50)
    ap.add_argument("--seed", type=int, default=20260927)
    ap.add_argument("--transport", choices=["file", "sink", "smtp"], default="file")
    ap.add_argument("--mail-dir", default="./mails", help="Ablage der .eml-Dateien (file/sink)")
    ap.add_argument("--smtp-host", default=os.environ.get("SMTP_HOST"))
    ap.add_argument("--smtp-port", type=int, default=int(os.environ.get("SMTP_PORT", 587)))
    ap.add_argument("--smtp-user", default=os.environ.get("SMTP_USER"))
    ap.add_argument("--smtp-pass", default=os.environ.get("SMTP_PASS"))
    ap.add_argument("--from", dest="von", default=None, help="Absenderadresse überschreiben")
    ap.add_argument("--rate", type=float, default=20.0, help="Mails pro Sekunde (0 = ungebremst)")

    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--verify", action="store_true", help="abgelegte Mails anschließend prüfen")
    a = ap.parse_args()

    if "<" in a.to and a.to.rstrip().endswith(">"):
        zielname, zieladresse = a.to.split("<")[0].strip(), a.to.split("<")[-1].rstrip(">").strip()
    else:
        zielname, zieladresse = "", a.to.strip()

    controller = None
    if a.transport == "sink":
        controller = baue_sink(a.mail_dir)
        controller.start()
        if not a.quiet:
            print(f"Lokaler SMTP-Server läuft auf 127.0.0.1:{os.environ.get('MAIL_SINK_PORT', 8026)}")
    ordner = EmlOrdner(a.mail_dir) if a.transport == "file" else None
    verbindung = None
    if a.transport == "smtp":
        if not a.smtp_host:
            print("FEHLER: --smtp-host (oder SMTP_HOST) fehlt für echte Zustellung", file=sys.stderr)
            return 2
        verbindung = smtplib.SMTP(a.smtp_host, a.smtp_port, timeout=30)
        verbindung.ehlo()
        if a.smtp_port != 25 and verbindung.has_extn("starttls"):
            verbindung.starttls()
            verbindung.ehlo()
        if a.smtp_user:
            verbindung.login(a.smtp_user, a.smtp_pass)
    elif a.transport == "sink":
        verbindung = smtplib.SMTP("127.0.0.1", int(os.environ.get("MAIL_SINK_PORT", 8026)), timeout=30)

    t0 = time.time()
    gesendet, fehler = 0, []
    try:
        rng_seeds = random.Random(a.seed)
        for i in range(a.count):
            seed = rng_seeds.randint(1, 2 ** 31 - 1)
            msg, typ, betreff, anhang = baue_mail(None, seed, zieladresse, a.von, zielname)
            try:
                if a.transport == "file":
                    ordner.speichere(msg, i + 1)
                else:
                    verbindung.send_message(msg)
                gesendet += 1
            except Exception as exc:  # noqa: BLE001
                fehler.append(f"{i+1}: {type(exc).__name__}: {exc}")
            if a.rate and i and i % max(1, int(a.rate)) == 0:
                time.sleep(1.0)
            if not a.quiet and (i + 1) % 25 == 0:
                print(f"  {i+1}/{a.count} Mails  ({time.time()-t0:.0f}s)", flush=True)
    finally:
        if verbindung is not None:
            verbindung.quit()
        if controller is not None:
            controller.stop()

    ziel_ordner = a.mail_dir
    print(f"\nFertig: {gesendet} Mails für {zieladresse} über Transport '{a.transport}' "
          f"({time.time()-t0:.1f}s, Fehler {len(fehler)})")
    if a.transport in ("file", "sink"):
        print(f"Ablage: {os.path.abspath(ziel_ordner)}")
    for f in fehler[:10]:
        print("  FEHLER:", f)
    if a.verify:
        return verifiziere(ziel_ordner, f"{zielname} <{zieladresse}>" if zielname else zieladresse, a.count)
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
