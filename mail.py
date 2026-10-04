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

def _utf8_ausgabe():
    """Kindprozesse schreiben in eine Pipe: ohne das scheitern Umlaute und Pfeile an cp1252."""
    import sys as _sys
    for strom in (_sys.stdout, _sys.stderr):
        try:
            strom.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


_utf8_ausgabe()

import io
import os
import random
import smtplib
import sys
import time
import uuid
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


def pdf_bytes(rng, typ, ctx, st, titel, versch=None):
    """Baut das Dokument wie gen.py, aber in den Speicher statt auf die Platte."""
    story, meta = G.TYP_FUNCS[typ](rng, ctx, st)
    buf = io.BytesIO()
    G.write_pdf(buf, story, ctx, typ, st, meta["titel"], versch)
    return buf.getvalue(), meta


def baue_mail(rng, seed, ziel_adresse, von_adresse=None, zielname="Vollmer Elektrotechnik GmbH",
              dokument_heute=False, datum_aus_dokument=False, versch=None, passwort_im_text=False,
              namensschema=None, nummer_der_mail=1, gesamt=1):
    rng, typ, today, ctx, font = G.derive(seed, dokument_heute)
    st = G.basis_styles(font)
    text_rng = random.Random(seed ^ 0x5EED)
    daten, meta = pdf_bytes(rng, typ, ctx, st, "", versch)
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
    anzeigename = ctx["absender"][0]
    absender_adresse = von_adresse or ctx["absender"][6]
    msg["To"] = f"{zielname} <{ziel_adresse}>" if zielname else ziel_adresse
    msg["From"] = f"{anzeigename} <{absender_adresse}>"
    msg["Subject"] = betreff if text_rng.random() > 0.18 else f"AW: {betreff}"
    if datum_aus_dokument:
        # nur für Bestände, die bewusst historisch aussehen sollen
        zeitpunkt = datetime.combine(ctx["datum"], dtime(text_rng.randint(6, 20), text_rng.randint(0, 59)))
    else:
        zeitpunkt = datetime.now()  # Mails tragen immer das aktuelle Versanddatum
    # timestamp() statt Ordinaltag * 86400 — Windows kann Zeitstempel außerhalb ~1970..3000 nicht umrechnen
    msg["Date"] = formatdate(zeitpunkt.timestamp(), localtime=True)
    msg["Message-ID"] = make_msgid(domain=absender_adresse.split("@")[-1])
    msg["Reply-To"] = absender_adresse

    # Jede Mail hat einen Anhang: Mails ohne Beleg gibt es in diesem Werkzeug nicht
    if versch:
        body += ("\n\nHinweis: Das Dokument im Anhang ist passwortgeschützt."
                 + (f"\nPasswort: {versch['pw']}" if passwort_im_text else ""))
    if text_rng.random() < 0.3:
        absaetze = "</p><p>".join(l for l in body.split("\n") if l.strip())
        msg.set_content(body)
        msg.add_alternative(HTML_RAHMEN.format(absaetze=absaetze, absender=ctx["absender"][0],
                                              strasse=ctx["absender"][2], plz_ort=f"{ctx['absender'][3]} {ctx['absender'][4]}",
                                              tel=ctx["absender"][5], mail=ctx["absender"][6]), subtype="html")
    else:
        msg.set_content(body)
    dateiname = G.make_name(random.Random(seed ^ 0xBEEF), typ, ctx, nummer_der_mail,
                            namensschema, gesamt)
    msg.add_attachment(daten, maintype="application", subtype="pdf", filename=dateiname)
    return msg, typ, betreff, dateiname


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


def verifiziere(ordner, ziel, erwartet, passwort=None):
    """Liest die abgelegten Mails zurück und prüft Empfänger, Anhänge und Text."""
    import glob
    import collections
    from email import policy
    from email.parser import BytesParser
    from email.utils import parseaddr
    from pypdf import PdfReader

    dateien = sorted(glob.glob(os.path.join(ordner, "*.eml")))
    falsch_ziel, ohne_text, kaputte_pdfs, mit_anhang, verschluesselt = [], [], [], 0, 0
    betreffe, absender = [], collections.Counter()
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
                    leser = PdfReader(io.BytesIO(teil.get_payload(decode=True)))
                    if leser.is_encrypted:
                        verschluesselt += 1
                        if passwort:
                            leser.decrypt(passwort)
                    if len(leser.pages) < 1:
                        kaputte_pdfs.append(os.path.basename(p))
                except Exception:  # noqa: BLE001
                    kaputte_pdfs.append(os.path.basename(p))
    print(f"Geprüft: {len(dateien)} Mails in {ordner} (erwartet {erwartet})")
    print(f"  falscher/n Empfänger: {len(falsch_ziel)} | ohne Text: {len(ohne_text)} | "
          f"kaputte PDF-Anhänge: {len(kaputte_pdfs)} | mit PDF-Anhang: {mit_anhang}"
          + (f" (davon verschlüsselt: {verschluesselt})" if verschluesselt else ""))
    print(f"  Absender: {len(absender)} verschiedene | Beispiele für Betreffzeilen:")
    for b in betreffe[:5]:
        print("    -", b)
    return 0 if (len(dateien) == erwartet and not falsch_ziel and not ohne_text
                 and not kaputte_pdfs and mit_anhang == len(dateien)) else 1


KONFIG_NAME = "mail.env"


def lade_config(pfad=None):
    """Liest eine einfache KEY=VALUE-Datei (mail.env) — Vorlage: mail.env.example."""
    kandidaten = [pfad] if pfad else [os.path.join(os.path.dirname(os.path.abspath(__file__)), KONFIG_NAME),
                                      os.path.join(os.getcwd(), KONFIG_NAME)]
    for k in kandidaten:
        if k and os.path.exists(k):
            werte = {}
            for zeile in open(k, encoding="utf-8"):
                zeile = zeile.strip()
                if not zeile or zeile.startswith("#") or "=" not in zeile:
                    continue
                schluessel, wert = zeile.split("=", 1)
                wert = wert.strip().strip('"').strip("'")
                if wert:
                    werte[schluessel.strip().upper()] = wert
            return werte, k
    return {}, None


def imap_verbinde(a):
    """Öffnet das Postfach per IMAP über TLS (Standardport 993)."""
    import imaplib
    M = imaplib.IMAP4_SSL(a.imap_host, a.imap_port, timeout=30)
    M.login(a.imap_user, a.imap_pass)
    return M


def imap_neueste(M, anzahl):
    from email import policy
    from email.parser import BytesParser
    typ, daten = M.select("INBOX")
    if typ != "OK":
        print(f"IMAP: Postfach nicht auswählbar: {daten}")
        return
    typ, res = M.search(None, "ALL")
    ids = res[0].split()[-anzahl:]
    print(f"IMAP: {len(ids)} neueste Mail(s) im Posteingang:")
    for i in reversed(ids):
        typ, teile = M.fetch(i, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE TO)])")
        kopf = b"".join(t[1] for t in teile if isinstance(t, tuple))
        msg = BytesParser(policy=policy.default).parsebytes(kopf)
        print(f"  - {msg['Date']} | {msg['From']} → {msg['To']} | {msg['Subject']}")


def imap_pruefe(a, message_ids, warten):
    """Wartet, bis die Mails im Postfach auftauchen (Zustellnachweis)."""
    if not a.imap_host or not a.imap_user or not a.imap_pass:
        print("IMAP: Zugangsdaten fehlen (IMAP_USER/IMAP_PASS bzw. SMTP_USER/SMTP_PASS).", file=sys.stderr)
        return 2
    try:
        M = imap_verbinde(a)
    except Exception as exc:  # noqa: BLE001
        print(f"IMAP: Anmeldung fehlgeschlagen ({type(exc).__name__}: {exc})", file=sys.stderr)
        return 2
    try:
        if a.imap_list:
            return imap_neueste(M, a.imap_list) or 0
        typ, _ = M.select("INBOX")
        gefunden, ende = {}, time.time() + warten
        while True:
            for mid in message_ids:
                if mid in gefunden:
                    continue
                typ, res = M.search(None, "HEADER", "Message-ID", mid)
                if res and res[0].split():
                    gefunden[mid] = res[0].split()[-1].decode()
            if len(gefunden) == len(message_ids) or time.time() > ende:
                break
            time.sleep(5)
        for mid in message_ids:
            if mid in gefunden:
                print(f"  Zustellung bestätigt: {mid} (UID {gefunden[mid]})")
            else:
                print(f"  Nicht gefunden: {mid} — noch nicht zugestellt, in einen anderen Ordner "
                      f"gefiltert oder das Postfach gehört nicht zu diesem Konto.")
        return 0 if len(gefunden) == len(message_ids) else 1
    finally:
        try:
            M.logout()
        except Exception:  # noqa: BLE001
            pass


def main():
    ap = argparse.ArgumentParser(description="Fake-Dokumente als E-Mail an einen festen Adressaten")
    ap.add_argument("--to", default=None,
                    help="fester Empfänger (Adresse oder Anzeigename <adresse>); sonst MAIL_TO aus mail.env")
    ap.add_argument("--count", type=int, default=5, help="Anzahl Mails (Standard 5)")
    ap.add_argument("--seed", type=int, default=20260927)
    ap.add_argument("--namensschema", "--naming", dest="namensschema", default=None, metavar="MUSTER",
                    help='Muster für den Anhangsnamen, z. B. "okiscan*.pdf"')
    ap.add_argument("--verschluesseln", "--encrypt", dest="verschluesseln", default=None,
                    metavar="PASSWORT", help="PDF-Anhang mit diesem Passwort verschlüsseln")
    ap.add_argument("--verschluesseln-owner", dest="verschluesseln_owner", default=None)
    ap.add_argument("--verschluesseln-rechte", dest="verschluesseln_rechte", default="drucken",
                    choices=["drucken", "alles", "nichts"])
    ap.add_argument("--passwort-im-text", action="store_true",
                    help="Passwort im Mailtext nennen (Standard: nur Hinweis, kein Passwort)")
    ap.add_argument("--document-today", action="store_true",
                    help="auch das Dokument selbst auf heute datieren (Standard: Zeitraum 2023–2026)")
    ap.add_argument("--date-from-document", action="store_true",
                    help="Mail-Kopf auf das Dokumentdatum setzen statt auf die aktuelle Zeit")
    ap.add_argument("--transport", choices=["file", "sink", "smtp"], default="file")
    ap.add_argument("--mail-dir", default="./mails", help="Ablage der .eml-Dateien (file/sink)")
    ap.add_argument("--config", default=None, help=f"Pfad zur Konfigurationsdatei (Standard: {KONFIG_NAME})")
    ap.add_argument("--smtp-host", default=None)
    ap.add_argument("--smtp-port", type=int, default=None)
    ap.add_argument("--smtp-user", default=None)
    ap.add_argument("--smtp-pass", default=None)
    ap.add_argument("--smtp-ssl", action="store_true", help="implizites TLS (Port 465); sonst STARTTLS")
    ap.add_argument("--from", dest="von", default=None, help="Absenderadresse überschreiben")
    ap.add_argument("--rate", type=float, default=20.0, help="Mails pro Sekunde (0 = ungebremst)")

    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--verify", action="store_true", help="abgelegte Mails anschließend prüfen")
    ap.add_argument("--check-connection", action="store_true",
                    help="nur SMTP-Verbindung und Anmeldung prüfen, nichts senden")
    ap.add_argument("--serve", action="store_true",
                    help="nur den lokalen SMTP-Sink betreiben und auf Post warten (kein Versand)")
    ap.add_argument("--serve-seconds", type=float, default=0, help="Laufzeit für --serve (0 = bis Strg-C)")
    ap.add_argument("--imap-host", default=None, help="Posteingangsserver (Standard: SMTP_HOST)")
    ap.add_argument("--imap-port", type=int, default=None, help="IMAP über TLS (Standard 993)")
    ap.add_argument("--imap-user", default=None)
    ap.add_argument("--imap-pass", default=None)
    ap.add_argument("--verify-imap", action="store_true",
                    help="nach dem Senden im Postfach prüfen, ob die Mails angekommen sind")
    ap.add_argument("--imap-wait", type=float, default=45, help="Wartezeit für die Zustellprüfung (Sekunden)")
    ap.add_argument("--imap-list", type=int, default=0,
                    help="nur die neuesten N Mails im Postfach auflisten, nichts senden")
    ap.add_argument("--check-recipient", action="store_true",
                    help="prüfen, ob die Empfängeradresse auf dem Server existiert (sendet nichts)")
    ap.add_argument("--no-auth", action="store_true",
                    help="ohne Anmeldung senden (für lokale Testserver wie den eigenen Sink)")
    a = ap.parse_args()

    # Reihenfolge: Kommandozeile > Umgebungsvariable > mail.env
    cfg, cfg_pfad = lade_config(a.config)
    a.to = a.to or cfg.get("MAIL_TO") or os.environ.get("MAIL_TO")
    a.smtp_host = a.smtp_host or cfg.get("SMTP_HOST") or os.environ.get("SMTP_HOST")
    a.smtp_port = a.smtp_port or int(cfg.get("SMTP_PORT") or os.environ.get("SMTP_PORT") or 587)
    a.smtp_user = a.smtp_user or cfg.get("SMTP_USER") or os.environ.get("SMTP_USER")
    a.smtp_pass = a.smtp_pass or cfg.get("SMTP_PASS") or os.environ.get("SMTP_PASS")
    a.von = a.von or cfg.get("SMTP_FROM") or os.environ.get("SMTP_FROM")
    a.smtp_ssl = a.smtp_ssl or str(cfg.get("SMTP_SSL", os.environ.get("SMTP_SSL", ""))).lower() in ("1", "true", "ja", "yes")
    a.imap_host = a.imap_host or cfg.get("IMAP_HOST") or os.environ.get("IMAP_HOST") or a.smtp_host
    a.imap_port = a.imap_port or int(cfg.get("IMAP_PORT") or os.environ.get("IMAP_PORT") or 993)
    a.imap_user = a.imap_user or cfg.get("IMAP_USER") or os.environ.get("IMAP_USER") or a.smtp_user
    a.imap_pass = a.imap_pass or cfg.get("IMAP_PASS") or os.environ.get("IMAP_PASS") or a.smtp_pass
    versch = G.verschluesselung(a.verschluesseln, a.verschluesseln_owner, a.verschluesseln_rechte)
    if not a.quiet and cfg_pfad:
        print(f"Konfiguration geladen: {cfg_pfad}")

    # Dienende Betriebsarten brauchen keinen Empfänger
    if a.imap_list:
        return imap_pruefe(a, [], 0)

    if a.serve:
        import time as _t
        dienst = baue_sink(a.mail_dir)
        dienst.start()
        port = os.environ.get("MAIL_SINK_PORT", 8026)
        print(f"SMTP-Sink läuft auf 127.0.0.1:{port}, legt Mails in {os.path.abspath(a.mail_dir)} ab.")
        try:
            if a.serve_seconds:
                _t.sleep(a.serve_seconds)
            else:
                while True:
                    _t.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            dienst.stop()
        return 0

    if not a.to:
        print("FEHLER: kein Empfänger — --to angeben oder MAIL_TO in mail.env setzen", file=sys.stderr)
        return 2

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
    if a.transport == "smtp" or a.check_connection or a.check_recipient:
        if not a.smtp_host:
            print("FEHLER: SMTP_HOST fehlt — für echte Zustellung --smtp-host angeben oder "
                  f"SMTP_HOST/SMTP_USER/SMTP_PASS in {KONFIG_NAME} eintragen (Vorlage: mail.env.example)",
                  file=sys.stderr)
            return 2
        print(f"SMTP: {a.smtp_host}:{a.smtp_port} als {a.smtp_user or '(ohne Anmeldung)'} "
              f"→ Empfänger {zieladresse}, {a.count} Mail(s)", flush=True)
        if a.smtp_ssl or a.smtp_port == 465:
            verbindung = smtplib.SMTP_SSL(a.smtp_host, a.smtp_port, timeout=30)
            verschluesselt = "TLS (implizit)"
            verbindung.ehlo()
        else:
            verbindung = smtplib.SMTP(a.smtp_host, a.smtp_port, timeout=30)
            verschluesselt = "unverschlüsselt"
            verbindung.ehlo()  # erst EHLO, sonst sind die Fähigkeiten des Servers unbekannt
            if verbindung.has_extn("starttls"):
                verbindung.starttls()
                verbindung.ehlo()
                verschluesselt = "STARTTLS"
            elif a.smtp_host not in ("127.0.0.1", "localhost"):
                print("WARNUNG: Server bietet kein STARTTLS — Anmeldung liefe unverschlüsselt.",
                      file=sys.stderr)
        if not a.quiet:
            print(f"  Server: {'ESMTP' if verbindung.does_esmtp else 'SMTP'} · Verschlüsselung: {verschluesselt} · "
                  f"Anmeldemethoden: {verbindung.esmtp_features.get('auth', 'keine')}", flush=True)
        fehlend = [] if a.no_auth else [n for n, v in (("SMTP_HOST", a.smtp_host), ("SMTP_USER", a.smtp_user),
                                                       ("SMTP_PASS", a.smtp_pass)) if not v]
        if fehlend:
            print(f"FEHLER: In mail.env fehlt noch: {', '.join(fehlend)} — Anmeldung daher nicht möglich.",
                  file=sys.stderr)
            verbindung.quit()
            return 2
        if a.smtp_user and not a.no_auth:
            verbindung.login(a.smtp_user, a.smtp_pass)
        if a.check_recipient:
            kontrolle = f"gibt-es-nicht-{uuid.uuid4().hex[:8]}@{zieladresse.split('@')[-1]}"
            print("Empfängerprüfung (es wird keine Mail gesendet):", flush=True)
            for adresse in (zieladresse, kontrolle):
                verbindung.mail(a.von or a.smtp_user)
                code, antwort = verbindung.rcpt(adresse)
                text = antwort.decode(errors="replace").strip() if isinstance(antwort, bytes) else str(antwort)
                print(f"  RCPT {adresse:<36} → {code} {text}", flush=True)
                verbindung.rset()
            print(f"  Kontrolladresse {kontrolle} soll abgelehnt werden — passiert das nicht, prüft der "
                  f"Server Empfänger nicht und das Ergebnis sagt nichts aus.")
            verbindung.quit()
            return 0
        if a.check_connection:
            print(f"Verbindung und Anmeldung in Ordnung ({a.smtp_user} bei {a.smtp_host}) — "
                  f"es wurde nichts gesendet.")
            verbindung.quit()
            return 0
    elif a.transport == "sink":
        verbindung = smtplib.SMTP("127.0.0.1", int(os.environ.get("MAIL_SINK_PORT", 8026)), timeout=30)

    t0 = time.time()
    gesendet, fehler, ids = 0, [], []
    try:
        rng_seeds = random.Random(a.seed)
        for i in range(a.count):
            seed = rng_seeds.randint(1, 2 ** 31 - 1)
            msg, typ, betreff, anhang = baue_mail(None, seed, zieladresse, a.von, zielname,
                                                  a.document_today, a.date_from_document,
                                                  versch, a.passwort_im_text, a.namensschema,
                                                  i + 1, a.count)
            try:
                if a.transport == "file":
                    ordner.speichere(msg, i + 1)
                else:
                    verbindung.send_message(msg, from_addr=a.von or None)
                gesendet += 1
                ids.append(msg["Message-ID"])
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
        return verifiziere(ziel_ordner, f"{zielname} <{zieladresse}>" if zielname else zieladresse, a.count,
                           a.verschluesseln)
    if a.verify_imap:
        print(f"\nIMAP-Gegenprobe bei {a.imap_host}:{a.imap_port} (max. {int(a.imap_wait)} s):")
        return imap_pruefe(a, ids, a.imap_wait)
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
