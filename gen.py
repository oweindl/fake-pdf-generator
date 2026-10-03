# -*- coding: utf-8 -*-
"""Erzeugt massenhaft realistische Fake-PDFs aus dem Alltag eines Kleinbetriebs.

Aufruf:
    python gen.py --out D:/pdf-temp --count 10000 --seed 42 --jobs 12
"""
from __future__ import annotations

import argparse
import csv
import os
import random
import sys
import time
from datetime import date, timedelta
from multiprocessing import Pool

from reportlab.lib import colors

def _utf8_ausgabe():
    """Kindprozesse schreiben in eine Pipe: ohne das scheitern Umlaute und Pfeile an cp1252."""
    import sys as _sys
    for strom in (_sys.stdout, _sys.stderr):
        try:
            strom.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


_utf8_ausgabe()

from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, A5
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (HRFlowable, KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pools as P

GREY = colors.HexColor("#555555")
LIGHT = colors.HexColor("#DDDDDD")
RULE = colors.HexColor("#999999")


# ---------------------------------------------------------------- Formathilfen
def eur(v):
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s + " \u20ac"


def num(v):
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def dt(d):
    return d.strftime("%d.%m.%Y")


def slug(s):
    return (s.replace("\u00e4", "ae").replace("\u00f6", "oe").replace("\u00fc", "ue")
             .replace("\u00df", "ss").replace("&", "und").replace(" ", "_"))


def pick_addr(rng):
    return f"{rng.choice(P.STRASSEN)} {rng.randint(1, 180)}{rng.choice(['', '', '', 'a', 'b'])}"


# --------------------------------------------------------------------- Kontext
KUNDEN_TYPEN = {"bestellung", "reklamation", "protokoll"}
BEHOERDEN_TYPEN = {"kontoauszug", "police", "steuerbescheid", "rundschreiben", "formular"}


def _inst(rng, art, namensanfang=None):
    pool = [t for t in P.INSTITUTIONEN if (t[1] == art if namensanfang is None else t[0].startswith(namensanfang))]
    return rng.choice(pool)


FESTE_ABSENDER = {
    "steuerbescheid": lambda rng: _inst(rng, None, "Finanzamt"),
    "kontoauszug": lambda rng: _inst(rng, "Bank"),
    "police": lambda rng: _inst(rng, "Versicherung"),
    "rundschreiben": lambda rng: _inst(rng, rng.choice(["Kammer", "BG"])),
    "lohnabrechnung": lambda rng: _inst(rng, None, "Steuerkanzlei"),
    "formular": lambda rng: rng.choice([t for t in P.INSTITUTIONEN if t[1] in ("Beh\u00f6rde", "BG")]),
    "quittung": lambda rng: rng.choice(P.FIRMEN),
    "frachtbrief": lambda rng: rng.choice([t for t in P.FIRMEN if "Spedition" in t[0] or "Logistik" in t[0]]),
    "brief": lambda rng: rng.choice(P.FIRMEN + P.KUNDEN_FIRMEN + P.INSTITUTIONEN),
    # interne Papiere tragen den eigenen Briefkopf
    "inventur": lambda rng: P.SIM_FIRMA,
    "protokoll": lambda rng: P.SIM_FIRMA,
}


def make_ctx(rng, today, aktenzeichen, typ="rechnung"):
    """absender = wer das Schreiben schickt, empf = die simulierte Firma (Empfängerin aller Eingänge)."""
    if typ in FESTE_ABSENDER:
        absender = FESTE_ABSENDER[typ](rng)
    elif typ in BEHOERDEN_TYPEN:
        absender = rng.choice(P.INSTITUTIONEN)
    elif typ in KUNDEN_TYPEN:
        absender = rng.choice(P.KUNDEN_FIRMEN) if rng.random() < 0.75 else rng.choice(P.FIRMEN)
    else:
        absender = rng.choice(P.FIRMEN) if rng.random() < 0.86 else rng.choice(P.INSTITUTIONEN)
    f = P.SIM_FIRMA
    empf = {"name": f[0], "strasse": f[2], "plz": f[3], "ort": f[4], "person": None}
    d = today
    jahr = d.year
    return {
        "absender": absender,
        "empf": empf,
        "firma": f,
        "datum": d,
        "jahr": jahr,
        "az": aktenzeichen,
        "rechnr": f"RE-{jahr}-{rng.randint(1000, 9999)}",
        "angebotnr": f"AN-{jahr}-{rng.randint(100, 999)}",
        "liesnr": f"LS-{jahr}-{rng.randint(1000, 9999)}",
        "abnr": f"AB-{jahr}-{rng.randint(1000, 9999)}",
        "bestnr": f"BE-{jahr}-{rng.randint(1000, 9999)}",
        "kundennr": f"K-{rng.randint(10000, 99999)}",
        "steuernr": f"{rng.randint(10, 99)}/{rng.randint(100, 999)}/{rng.randint(10000, 99999)}",
        "ustid": P.ust_id(rng),
        "iban": P.iban(rng),
        "bank": rng.choice(P.BANKEN)[0],
        "tel": P.telefon(rng),
        "abteilung": rng.choice(P.ABTEILUNGEN),
        "bearbeiter": rng.choice([p[0] for p in P.KUNDEN_PERSONEN]),
        "geschaeftsfuehrer": rng.choice([p[0] for p in P.KUNDEN_PERSONEN]),
        "zahlungsziel": rng.choice([14, 14, 30, 30, 30, 10, 45]),
        "skonto": rng.choice([0, 0, 0, 2, 3]),
        "ustsatz": rng.choice([19, 19, 19, 19, 7]),
    }


def positions(rng, n=None):
    n = n or rng.randint(1, 9)
    items = []
    for _ in range(n):
        if rng.random() < 0.45:
            bez, einheit, preis = rng.choice(P.ARTIKEL)
        else:
            bez, einheit, preis = rng.choice(P.DIENSTLEISTUNGEN)
        menge = rng.choice([1, 1, 2, 3, 4, 5, 10, 12, 20, 25]) if einheit in ("Stk", "Pkt", "Set", "Rolle", "Bogen", "Sack", "Paar") else round(rng.uniform(0.5, 40), 2)
        preis = round(preis * rng.uniform(0.95, 1.25), 2)
        items.append((bez, einheit, menge, preis))
    return items


def pos_tabelle(items, ustsatz, st=None):
    st = st or {}
    rows = [["Pos.", "Bezeichnung", "Menge", "Einheit", "Einzelpreis", "Gesamt"]]
    netto = 0.0
    for i, (bez, einheit, menge, preis) in enumerate(items, 1):
        g = round(menge * preis, 2)
        netto += g
        rows.append([str(i), bez, num(menge), einheit, eur(preis), eur(g)])
    steuer = round(netto * ustsatz / 100, 2)
    brutto = round(netto + steuer, 2)
    rows.append(["", "", "", "", "Zwischensumme netto", eur(netto)])
    rows.append(["", "", "", "", f"Umsatzsteuer {ustsatz} %", eur(steuer)])
    rows.append(["", "", "", "", "Rechnungsbetrag", eur(brutto)])
    t = Table(rows, colWidths=[10 * mm, 78 * mm, 16 * mm, 18 * mm, 25 * mm, 25 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, RULE),
        ("LINEBELOW", (0, len(rows) - 4), (-1, len(rows) - 4), 0.4, LIGHT),
        ("FONTNAME", (4, len(rows) - 3), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t, netto, steuer, brutto


BOLD_OF = {"Helvetica": "Helvetica-Bold", "Times-Roman": "Times-Bold", "Courier": "Courier-Bold"}


def basis_styles(font="Helvetica"):
    bold = BOLD_OF.get(font, "Helvetica-Bold")
    return {
        "font": font, "bold": bold,
        "body": ParagraphStyle("body", fontName=font, fontSize=9.5, leading=13.5, alignment=TA_LEFT, spaceAfter=5),
        "small": ParagraphStyle("small", fontName=font, fontSize=7.5, leading=10, textColor=GREY),
        "h1": ParagraphStyle("h1", fontName=bold, fontSize=16, leading=20, spaceAfter=8),
        "h2": ParagraphStyle("h2", fontName=bold, fontSize=11, leading=14, spaceBefore=6, spaceAfter=4),
        "right": ParagraphStyle("right", fontName=font, fontSize=9.5, leading=13, alignment=TA_RIGHT),
        "center": ParagraphStyle("center", fontName=font, fontSize=9.5, leading=13, alignment=TA_CENTER),
        "mono": ParagraphStyle("mono", fontName="Courier", fontSize=8.5, leading=11),
        "head": ParagraphStyle("head", fontName=bold, fontSize=10, leading=13),
    }


def briefkopf(ctx, st, kompakt=False):
    """Briefkopf des Absenders + Anschriftenblock der eigenen Firma (Eingangspost)."""
    a = ctx["absender"]
    el = [Paragraph(f"<b>{a[0]}</b>", ParagraphStyle("firm", fontName=st["bold"], fontSize=13, leading=16)),
          Paragraph(f"{a[2]} \u00b7 {a[3]} {a[4]} \u00b7 Tel. {a[5]} \u00b7 {a[6]}", st["small"]),
          HRFlowable(width="100%", thickness=0.7, color=RULE, spaceBefore=4, spaceAfter=8),
          Paragraph(f"{ctx['firma'][0]}<br/>{ctx['firma'][2]}<br/>"
                    f"{ctx['firma'][3]} {ctx['firma'][4]}", st["body"]),
          Spacer(1, 4)]
    return el


def fuss(ctx, st, extra=None):
    a = ctx["absender"]
    txt = (f"{a[0]} \u00b7 {a[2]}, {a[3]} {a[4]} \u00b7 Telefon {a[5]} \u00b7 {a[6]}<br/>"
           f"Gesch\u00e4ftsf\u00fchrung: {ctx['geschaeftsfuehrer']} \u00b7 USt-IdNr. {ctx['ustid']} \u00b7 "
           f"Steuernr. {ctx['steuernr']} \u00b7 Bank: {ctx['bank']} \u00b7 IBAN {ctx['iban']}")
    if extra:
        txt += "<br/>" + extra
    return [Spacer(1, 10), HRFlowable(width="100%", thickness=0.4, color=LIGHT), Paragraph(txt, st["small"])]


# ------------------------------------------------------------------ Dokumente
def doc_rechnung(rng, ctx, st):
    items = positions(rng, rng.randint(1, 22 if rng.random() < 0.2 else 7))
    el = briefkopf(ctx, st)
    el.append(Paragraph("Rechnung", st["h1"]))
    kopf = Table([[Paragraph(f"Rechnungsnummer<br/><b>{ctx['rechnr']}</b>", st["small"]),
                   Paragraph(f"Rechnungsdatum<br/><b>{dt(ctx['datum'])}</b>", st["small"]),
                   Paragraph(f"Kundennummer<br/><b>{ctx['kundennr']}</b>", st["small"]),
                   Paragraph(f"Bestellung<br/><b>{ctx['bestnr']}</b>", st["small"])]],
                 colWidths=[43 * mm] * 4)
    kopf.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("BOX", (0, 0), (-1, -1), 0.5, LIGHT), ("INNERGRID", (0, 0), (-1, -1), 0.4, LIGHT),
                              ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    el += [kopf, Spacer(1, 8),
           Paragraph(f"Leistungszeitraum: {dt(ctx['datum'] - timedelta(days=rng.randint(2, 40)))} bis {dt(ctx['datum'])}", st["body"])]
    t, netto, steuer, brutto = pos_tabelle(items, ctx["ustsatz"])
    el += [Spacer(1, 4), t, Spacer(1, 8)]
    zt = f"Zahlbar ohne Abzug innerhalb von {ctx['zahlungsziel']} Tagen."
    if ctx["skonto"]:
        zt += f" Bei Zahlung innerhalb von 10 Tagen {ctx['skonto']} % Skonto."
    el.append(Paragraph(zt, st["body"]))
    if rng.random() < 0.3:
        el.append(Paragraph("Es handelt sich um eine Abschlagsrechnung. Die Schlussrechnung wird nach Abnahme erstellt.", st["small"]))
    el += fuss(ctx, st)
    return el, {"betrag": brutto, "gegenpartei": ctx["empf"]["name"], "nummer": ctx["rechnr"], "titel": "Rechnung"}


def doc_angebot(rng, ctx, st):
    items = positions(rng, rng.randint(2, 12))
    el = briefkopf(ctx, st)
    el.append(Paragraph(f"Angebot {ctx['angebotnr']}", st["h1"]))
    el.append(Paragraph(f"Sehr geehrte Damen und Herren,<br/>auf Grundlage Ihrer Anfrage unterbreiten wir Ihnen "
                        f"nachfolgendes Angebot. Die Preise gelten {rng.choice(['bis zum ' + dt(ctx['datum'] + timedelta(days=30)), 'bei Abruf innerhalb von 6 Wochen', 'freibleibend'])}.",
                        st["body"]))
    t, netto, steuer, brutto = pos_tabelle(items, 19)
    el += [t, Spacer(1, 6),
           Paragraph(f"Lieferzeit: ca. {rng.choice([2, 3, 4, 6, 8])} Wochen nach Auftragseingang. "
                     f"Zahlungsbedingungen: {rng.choice([30, 14])} Tage netto. "
                     f"Es gelten unsere Allgemeinen Gesch\u00e4ftsbedingungen.", st["body"]),
           Paragraph("Wir w\u00fcrden uns \u00fcber eine Zusammenarbeit freuen und stehen f\u00fcr R\u00fcckfragen gerne zur Verf\u00fcgung.", st["body"]),
           Spacer(1, 6), Paragraph(f"Mit freundlichen Gr\u00fc\u00dfen<br/><br/>{ctx['bearbeiter']}<br/>{ctx['abteilung']}", st["body"])]
    el += fuss(ctx, st)
    return el, {"betrag": brutto, "gegenpartei": ctx["empf"]["name"], "nummer": ctx["angebotnr"], "titel": "Angebot"}


def doc_lieferschein(rng, ctx, st):
    items = positions(rng, rng.randint(1, 10))
    el = briefkopf(ctx, st)
    el.append(Paragraph("Lieferschein", st["h1"]))
    el.append(Paragraph(f"Lieferschein-Nr. {ctx['liesnr']} &nbsp;&nbsp;|&nbsp;&nbsp; Datum {dt(ctx['datum'])} "
                        f"&nbsp;&nbsp;|&nbsp;&nbsp; Bestellung {ctx['bestnr']} &nbsp;&nbsp;|&nbsp;&nbsp; "
                        f"Kunde {ctx['kundennr']}", st["small"]))
    rows = [["Pos.", "Artikel / Bezeichnung", "Menge", "Einheit", "Bemerkung"]]
    for i, (bez, einheit, menge, _preis) in enumerate(items, 1):
        rows.append([str(i), bez, num(menge), einheit, rng.choice(["", "", "vollst\u00e4ndig", "Teillieferung", "R\u00fcckstand"])])
    t = Table(rows, colWidths=[12 * mm, 88 * mm, 18 * mm, 18 * mm, 36 * mm], repeatRows=1)
    t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
                           ("GRID", (0, 0), (-1, -1), 0.4, LIGHT), ("ALIGN", (2, 1), (3, -1), "RIGHT")]))
    el += [t, Spacer(1, 10),
           Paragraph("Ware erhalten am: ______________________  Unterschrift Empf\u00e4nger: ______________________", st["body"]),
           Paragraph("Bitte pr\u00fcfen Sie die Lieferung innerhalb von 5 Werktagen auf Vollst\u00e4ndigkeit und "
                     "Transportsch\u00e4den. Sp\u00e4tere Reklamationen k\u00f6nnen nur nach R\u00fccksprache ber\u00fccksichtigt werden.", st["small"])]
    el += fuss(ctx, st)
    return el, {"betrag": None, "gegenpartei": ctx["empf"]["name"], "nummer": ctx["liesnr"], "titel": "Lieferschein"}


def doc_mahnung(rng, ctx, st):
    stufe = rng.randint(1, 3)
    betrag = round(rng.uniform(85, 8600), 2)
    faellig = ctx["datum"] - timedelta(days=rng.choice([16, 22, 35, 48, 60, 90]))
    el = briefkopf(ctx, st)
    el.append(Paragraph(f"{stufe}. Mahnung" if stufe > 1 else "Zahlungserinnerung", st["h1"]))
    el.append(Paragraph(f"Rechnungsnummer {ctx['rechnr']} vom {dt(faellig)} \u2014 offener Betrag {eur(betrag)}", st["body"]))
    el.append(Paragraph(f"Sehr geehrte Damen und Herren,<br/>"
                        f"die oben genannte Rechnung \u00fcber {eur(betrag)} ist am {dt(faellig + timedelta(days=ctx['zahlungsziel']))} "
                        f"zur Zahlung f\u00e4llig gewesen. Ein Zahlungseingang konnte bis heute nicht festgestellt werden.", st["body"]))
    if stufe >= 2:
        el.append(Paragraph(f"Wir bitten Sie eindringlich, den Betrag bis zum "
                            f"{dt(ctx['datum'] + timedelta(days=rng.choice([5, 7, 10])))} auszugleichen.", st["body"]))
    if stufe == 3:
        el.append(Paragraph(f"Sollte der Betrag nicht innerhalb der gesetzten Frist eingehen, "
                            f"werden wir die Angelegenheit ohne weitere Ank\u00fcndigung an unser Inkassob\u00fcro "
                            f"\u00fcbergeben. Die dadurch entstehenden Kosten gehen zu Ihren Lasten. "
                            f"Verzugszinsen berechnen wir mit {num(rng.choice([5.12, 8.17, 9.09]))} % \u00fcber Basiszins.", st["body"]))
    tab = Table([[Paragraph("Rechnungsbetrag", st["body"]), Paragraph(eur(betrag), st["right"])],
                 [Paragraph(f"Verzugszinsen ({rng.randint(4, 60)} Tage)", st["body"]),
                  Paragraph(eur(round(betrag * 0.00017 * 30, 2)), st["right"])],
                 [Paragraph("<b>Gesamtforderung</b>", st["body"]),
                  Paragraph(f"<b>{eur(round(betrag * 1.005 + 2.5, 2))}</b>", st["right"])]],
                colWidths=[120 * mm, 40 * mm])
    tab.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.4, LIGHT), ("LINEABOVE", (0, -1), (-1, -1), 0.6, RULE)]))
    el += [Spacer(1, 6), tab, Spacer(1, 8),
           Paragraph("Sollte sich diese Mahnung mit Ihrer Zahlung \u00fcberschnitten haben, betrachten Sie "
                     "dieses Schreiben bitte als gegenstandslos.", st["small"])]
    el += fuss(ctx, st)
    return el, {"betrag": betrag, "gegenpartei": ctx["empf"]["name"], "nummer": ctx["rechnr"], "titel": f"Mahnung Stufe {stufe}"}


def doc_bestellung(rng, ctx, st):
    items = positions(rng, rng.randint(1, 8))
    el = briefkopf(ctx, st, kompakt=True)
    el.append(Paragraph(f"Bestellung {ctx['bestnr']}", st["h1"]))
    el.append(Paragraph(f"Bestelldatum: {dt(ctx['datum'])}<br/>Lieferanschrift: {ctx['firma'][0]}, "
                        f"{ctx['firma'][2]}, {ctx['firma'][3]} {ctx['firma'][4]}<br/>"
                        f"Kostenstelle: {ctx['abteilung']}", st["body"]))
    t, netto, steuer, brutto = pos_tabelle(items, 19)
    el += [t, Spacer(1, 6),
           Paragraph(f"Gew\u00fcnschter Liefertermin: {dt(ctx['datum'] + timedelta(days=rng.randint(5, 60)))}. "
                     f"Bitte geben Sie die Bestellnummer auf allen Belegen an.", st["body"])]
    el += fuss(ctx, st)
    return el, {"betrag": brutto, "gegenpartei": rng.choice(P.FIRMEN)[0], "nummer": ctx["bestnr"], "titel": "Bestellung"}


def doc_auftragsbestaetigung(rng, ctx, st):
    items = positions(rng, rng.randint(1, 7))
    el = briefkopf(ctx, st)
    el.append(Paragraph("Auftragsbest\u00e4tigung", st["h1"]))
    el.append(Paragraph(f"Wir best\u00e4tigen Ihren Auftrag {ctx['bestnr']} mit der Auftragsnummer "
                        f"{ctx['abnr']} zu den nachfolgenden Konditionen.", st["body"]))
    t, netto, steuer, brutto = pos_tabelle(items, 19)
    el += [t, Spacer(1, 6),
           Paragraph(f"Voraussichtlicher Liefertermin: {dt(ctx['datum'] + timedelta(days=rng.randint(4, 45)))}. "
                     f"Zahlung: {ctx['zahlungsziel']} Tage netto. "
                     f"Teillieferungen sind {rng.choice(['zul\u00e4ssig', 'nicht zul\u00e4ssig'])}.", st["body"]),
           Paragraph("Abweichungen vom bestellten Umfang bitten wir unverz\u00fcglich mitzuteilen.", st["small"])]
    el += fuss(ctx, st)
    return el, {"betrag": brutto, "gegenpartei": ctx["empf"]["name"], "nummer": ctx["abnr"], "titel": "Auftragsbest\u00e4tigung"}


def doc_brief(rng, ctx, st):
    betreff = rng.choice(P.BETREFFZEILEN).format(d=dt(ctx["datum"] - timedelta(days=rng.randint(1, 30))), nr=ctx["bestnr"])
    el = briefkopf(ctx, st, kompakt=True)
    el += [Paragraph(f"{ctx['absender'][0]} \u00b7 {ctx['absender'][2]}", st["small"]), Spacer(1, 6),
           Paragraph(f"{ctx['empf']['name']}<br/>{ctx['empf']['strasse']}<br/>{ctx['empf']['plz']} {ctx['empf']['ort']}", st["body"]),
           Spacer(1, 8), Paragraph(f"<b>Betreff: {betreff}</b>", st["body"]),
           Paragraph(f"Unser Zeichen: {ctx['az']} \u00b7 {dt(ctx['datum'])}", st["small"]), Spacer(1, 4),
           Paragraph("Sehr geehrte Damen und Herren,", st["body"])]
    for _ in range(rng.randint(2, 5)):
        el.append(Paragraph(rng.choice(P.BRIEF_ABSATZ), st["body"]))
    el += [Paragraph("Mit freundlichen Gr\u00fc\u00dfen", st["body"]),
           Spacer(1, 10), Paragraph(f"{ctx['bearbeiter']}<br/>{ctx['abteilung']}<br/>{ctx['absender'][0]}", st["body"])]
    if rng.random() < 0.4:
        el += [Spacer(1, 10), Paragraph("Anlagen: Lageplan, Termin\u00fcbersicht, Protokoll der Begehung", st["small"])]
    el += fuss(ctx, st)
    return el, {"betrag": None, "gegenpartei": ctx["empf"]["name"], "nummer": ctx["az"], "titel": "Gesch\u00e4ftsbrief"}


def doc_formular(rng, ctx, st):
    titel = rng.choice(["Antrag auf Auszahlung", "Zeiterfassungsbogen", "Reisekostenabrechnung",
                        "Stammdaten\u00e4nderung", "Urlaubsantrag", "Materialausgabe", "Fahrtenbuch",
                        "Inventurerfassung", "Sicherheitsunterweisung", "Meldung eines Schadens"])
    el = [Paragraph(titel, st["h1"]),
          Paragraph(f"{ctx['firma'][0]} \u00b7 {ctx['firma'][2]} \u00b7 {ctx['firma'][3]} {ctx['firma'][4]} \u00b7 "
                    f"Abteilung {ctx['abteilung']}", st["small"]),
          Paragraph(f"Formular F-{rng.randint(100, 899)} \u00b7 Stand {dt(ctx['datum'])} \u00b7 Fassung {rng.randint(1, 6)}", st["small"]),
          Spacer(1, 8)]
    rows = []
    for label, key in rng.sample(P.FORMULAR_FELDER, rng.randint(6, 12)):
        wert = rng.choice([ctx["kundennr"], ctx["bestnr"], ctx["abteilung"], ctx["bearbeiter"],
                           dt(ctx["datum"]), eur(round(rng.uniform(9, 2400), 2)), "98999",
                           "1234567890", ctx["iban"], ctx["kundennr"]])
        rows.append([Paragraph(f"<b>{label}</b>", st["body"]), Paragraph(str(wert), st["body"]), ""])
    t = Table(rows, colWidths=[62 * mm, 70 * mm, 28 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, LIGHT), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    el += [t, Spacer(1, 10),
           Paragraph(rng.choice([
               "Die Angaben wurden nach bestem Wissen und Gewissen gemacht.",
               "Bitte vollst\u00e4ndig ausf\u00fcllen und im Original an die Personalabteilung weiterleiten.",
               "Unvollst\u00e4ndige Antr\u00e4ge k\u00f6nnen nicht bearbeitet werden.",
               "Nach Eingang erfolgt eine Pr\u00fcfung durch die zust\u00e4ndige Abteilung."]), st["small"]),
           Spacer(1, 12),
           Paragraph(f"Datum, Unterschrift: ______________________ &nbsp;&nbsp;&nbsp; "
                     f"Genehmigung: ______________________", st["body"])]
    el += fuss(ctx, st)
    return el, {"betrag": None, "gegenpartei": ctx["empf"]["name"], "nummer": f"F-{rng.randint(1000,9999)}", "titel": titel}


def doc_kontoauszug(rng, ctx, st, seiten=None):
    seiten = seiten or rng.randint(2, 6)
    saldo = round(rng.uniform(800, 45000), 2)
    el = [Paragraph(f"{ctx['firma'][0]} \u2014 Gesch\u00e4ftskonto bei {ctx['absender'][0]}", st["h1"]),
          Paragraph(f"Kontoauszug Nr. {rng.randint(1, 12)} \u00b7 Blatt 1 &nbsp;|&nbsp; "
                    f"IBAN {ctx['iban']} &nbsp;|&nbsp; Zeitraum {dt(ctx['datum'] - timedelta(days=30))} \u2013 {dt(ctx['datum'])}", st["body"]),
          Spacer(1, 6)]
    for s in range(seiten):
        rows = [["Buchung", "Verwendungszweck", "Auftraggeber / Empf\u00e4nger", "Soll", "Haben"]]
        for _ in range(rng.randint(14, 22)):
            d = ctx["datum"] - timedelta(days=rng.randint(0, 30))
            betrag = round(rng.uniform(4, 3200), 2)
            rows.append([dt(d),
                         rng.choice([f"RE {ctx['rechnr']}", "Lastschrift", "Überweisung", "Kartenzahlung girocard",
                                     "Abschlag Strom", "Lohn/Gehalt", "Beitrag BG", "DATEV-Export",
                                     "Miete Gewerbeobjekt", "Tankbeleg", "Büromaterial", "Telefon/Internet"]),
                         rng.choice([f[0] for f in P.FIRMEN]),
                         eur(betrag) if rng.random() < 0.5 else "",
                         "" if rng.random() < 0.5 else eur(betrag)])
        t = Table(rows, colWidths=[20 * mm, 45 * mm, 55 * mm, 22 * mm, 22 * mm], repeatRows=1)
        t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
                               ("GRID", (0, 0), (-1, -1), 0.3, LIGHT), ("ALIGN", (3, 1), (-1, -1), "RIGHT")]))
        el.append(t)
        el.append(Paragraph(f"Saldo per {dt(ctx['datum'])}: {eur(saldo + rng.uniform(-900, 900))}", st["body"]))
        if s < seiten - 1:
            el.append(PageBreak())
    return el, {"betrag": None, "gegenpartei": ctx["empf"]["name"], "nummer": f"KA-{rng.randint(1000,9999)}", "titel": "Kontoauszug"}


def doc_vertrag(rng, ctx, st):
    seiten = rng.choice([4, 5, 6, 8, 10, 12, 14])
    art = rng.choice(["Wartungsvertrag", "Dienstleistungsvertrag", "Mietvertrag Gewerbeobjekt",
                      "Rahmenvertrag Lieferbeziehungen", "Werkvertrag \u00fcber Instandsetzung",
                      "Vertrag \u00fcber EDV-Betreuung", "Leasingvertrag Fahrzeug", "Entsorgungsvertrag"])
    el = [Paragraph(art, st["h1"]),
          Paragraph(f"zwischen<br/><b>{ctx['absender'][0]}</b>, {ctx['absender'][2]}, {ctx['absender'][3]} {ctx['absender'][4]} "
                    f"(nachfolgend Auftragnehmer)<br/>und<br/><b>{ctx['empf']['name']}</b>, {ctx['empf']['strasse']}, "
                    f"{ctx['empf']['plz']} {ctx['empf']['ort']} (nachfolgend Auftraggeber)", st["body"]),
          Spacer(1, 8)]
    el.append(Paragraph("Pr\u00e4ambel", st["h2"]))
    el.append(Paragraph(f"Die Parteien beabsichtigen, die Zusammenarbeit im Bereich "
                        f"{ctx['absender'][1]} f\u00fcr die Dauer von {rng.choice([12, 24, 36])} Monaten "
                        f"verbindlich zu regeln. Vertragsbeginn ist der {dt(ctx['datum'])}.", st["body"]))
    PARAS = ['Gegenstand der Leistung', 'Verg\u00fctung', 'Pflichten des Auftragnehmers', 'Vertraulichkeit',
             'Haftung', 'Laufzeit und K\u00fcndigung', 'Datenschutz', 'Schlussbestimmungen', 'Versicherung',
             'M\u00e4ngelhaftung', 'Abnahme', 'Zahlungsbedingungen', 'Sonstiges', 'Reaktionszeiten',
             'Ersatzteile und Material']
    for i in range(1, seiten):
        ueberschrift = PARAS[0] if i == 1 else rng.choice(PARAS[1:])
        el.append(Paragraph(f"\u00a7 {i} {ueberschrift}", st["h2"]))
        for _ in range(rng.randint(2, 4)):
            el.append(Paragraph(rng.choice(P.VERTRAG_ABSATZ), st["body"]))
        el.append(Paragraph(f"({i}) {rng.choice(P.VERTRAG_ABSATZ)}", st["body"]))
        if rng.random() < 0.3:
            el.append(Paragraph(f"Verg\u00fctungspauschale: {eur(round(rng.uniform(180, 4200), 2))} monatlich zzgl. USt.", st["small"]))
        if i < seiten - 1 and rng.random() < 0.6:
            el.append(PageBreak())
    el += [Spacer(1, 14),
           Paragraph(f"{ctx['absender'][3]}, {dt(ctx['datum'])} &nbsp;&nbsp;&nbsp;&nbsp; "
                     f"{ctx['empf']['plz']} {ctx['empf']['ort']}, {dt(ctx['datum'])}", st["small"]),
           Spacer(1, 16),
           Paragraph("___________________________ &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; "
                     "___________________________<br/>Auftragnehmer &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Auftraggeber", st["small"])]
    return el, {"betrag": None, "gegenpartei": ctx["empf"]["name"], "nummer": ctx["az"], "titel": art}


def doc_gutschrift(rng, ctx, st):
    items = positions(rng, rng.randint(1, 5))
    el = briefkopf(ctx, st)
    el.append(Paragraph("Gutschrift", st["h1"]))
    el.append(Paragraph(f"Gutschrift-Nr. {ctx['rechnr'].replace('RE', 'GU')} &nbsp;\u00b7&nbsp; Datum {dt(ctx['datum'])} "
                        f"&nbsp;\u00b7&nbsp; Bezug: Rechnung {ctx['rechnr']}", st["small"]))
    t, netto, steuer, brutto = pos_tabelle(items, ctx["ustsatz"])
    el += [Spacer(1, 4), t, Spacer(1, 6),
           Paragraph(f"Wir erstatten Ihnen {eur(brutto)}. Der Betrag wird auf das bekannte Konto "
                     f"\u00fcberwiesen oder mit offenen Posten verrechnet.", st["body"])]
    el += fuss(ctx, st)
    return el, {"betrag": -brutto, "gegenpartei": ctx["empf"]["name"], "nummer": ctx["rechnr"], "titel": "Gutschrift"}


def doc_reklamation(rng, ctx, st):
    el = briefkopf(ctx, st, kompakt=True)
    el.append(Paragraph("M\u00e4ngelanzeige / Reklamation", st["h1"]))
    el.append(Paragraph(f"Bezug: Lieferung {ctx['liesnr']} vom {dt(ctx['datum'] - timedelta(days=rng.randint(3, 45)))}", st["body"]))
    el.append(Paragraph(f"Sehr geehrte Damen und Herren,<br/>bei der Wareneingangspr\u00fcfung haben wir folgende M\u00e4ngel festgestellt:", st["body"]))
    rows = [[str(i), rng.choice(P.ARTIKEL_KURZ), rng.choice(["Falschlieferung", "Transportschaden", "Ma\u00dfabweichung",
            "Oberfl\u00e4chenfehler", "Fehlmenge", "Fehlende Dokumentation", "Besch\u00e4digte Verpackung"]),
             rng.choice(["3 Stk.", "1 Palette", "2 Kartons", "5 Stk.", "komplett"])] for i in range(1, rng.randint(2, 5))]
    t = Table([["Pos.", "Artikelgruppe", "Mangel", "Umfang"]] + rows, colWidths=[14 * mm, 50 * mm, 60 * mm, 36 * mm])
    t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
                           ("GRID", (0, 0), (-1, -1), 0.4, LIGHT), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE"))]))
    el += [Spacer(1, 4), t, Spacer(1, 6),
           Paragraph(f"Wir fordern Sie auf, den Mangel bis zum {dt(ctx['datum'] + timedelta(days=14))} "
                     f"zu beheben. Andernfalls behalten wir uns {rng.choice(['Minderung', 'Ersatzlieferung', 'R\u00fccktritt vom Vertrag', 'Schadensersatz']) } vor.", st["body"])]
    el += fuss(ctx, st)
    return el, {"betrag": None, "gegenpartei": ctx["empf"]["name"], "nummer": ctx["liesnr"], "titel": "Reklamation"}


def doc_rundschreiben(rng, ctx, st):
    thema = rng.choice(P.RUNDSCHREIBEN_THEMEN)
    el = [Paragraph("Rundschreiben", st["h1"]),
          Paragraph(f"{ctx['absender'][0]} &nbsp;\u00b7&nbsp; {ctx['absender'][2]}, {ctx['absender'][3]} {ctx['absender'][4]} "
                    f"&nbsp;\u00b7&nbsp; {dt(ctx['datum'])} &nbsp;\u00b7&nbsp; Nr. {rng.randint(1, 40)}/{ctx['jahr']}", st["small"]),
          Spacer(1, 8), Paragraph(f"<b>Betrifft: {thema}</b>", st["h2"]),
          Paragraph(f"An alle Mitgliedsbetriebe, Kunden und Gesch\u00e4ftspartner im Zust\u00e4ndigkeitsbereich.", st["small"]), Spacer(1, 4)]
    for _ in range(rng.randint(2, 4)):
        el.append(Paragraph(rng.choice(P.BRIEF_ABSATZ), st["body"]))
    el += [Paragraph("Bitte beachten Sie folgende Punkte im Einzelnen:", st["body"])]
    for i in range(1, rng.randint(3, 6)):
        el.append(Paragraph(f"\u2022 {rng.choice(['Ab dem genannten Datum gilt die neue Regelung verbindlich.', 'R\u00fcckfragen richten Sie bitte an die '+ctx['abteilung']+'.', 'Die Unterlagen stehen im Intranet bereit.', 'Eine Schulung findet am '+dt(ctx['datum']+timedelta(days=7))+' statt.', 'Bitte geben Sie R\u00fcckmeldung bis Ende der Woche.'])}", st["body"]))
    el += [Spacer(1, 12), Paragraph(f"Mit freundlichen Gr\u00fc\u00dfen<br/><br/>{ctx['bearbeiter']}<br/>"
                                    f"{ctx['absender'][0]}", st["body"])]
    return el, {"betrag": None, "gegenpartei": "\u2014", "nummer": ctx["az"], "titel": "Rundschreiben"}


def doc_quittung(rng, ctx, st):
    betrag = round(rng.uniform(2, 320), 2)
    items = positions(rng, rng.randint(1, 4))
    netto = round(betrag / 1.19, 2)
    el = [Paragraph(f"{ctx['absender'][0]}", st["head"]),
          Paragraph(f"{ctx['absender'][2]}, {ctx['absender'][3]} {ctx['absender'][4]}", st["small"]),
          Spacer(1, 4), Paragraph(f"Quittung Nr. {rng.randint(1000, 99999)}", st["h2"]),
          Paragraph(f"Beleg f\u00fcr {ctx['firma'][0]} \u00b7 Kd.-Nr. {ctx['kundennr']}", st["small"]),
          Paragraph(f"{dt(ctx['datum'])} \u00b7 Kasse {rng.randint(1, 3)} \u00b7 Bedienung {ctx['bearbeiter']}", st["small"]),
          Spacer(1, 4)]
    rows = [["Bezeichnung", "Menge", "Einzel", "Summe"]]
    for bez, einheit, menge, preis in items:
        rows.append([bez[:34], num(menge), eur(round(betrag / max(menge, 1), 2)), eur(round(betrag / len(items), 2))])
    t = Table(rows, colWidths=[80 * mm, 18 * mm, 24 * mm, 26 * mm])
    t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.3, LIGHT),
                           ("ALIGN", (1, 1), (-1, -1), "RIGHT")]))
    el += [t, Spacer(1, 6),
           Paragraph(f"Gesamt: {eur(betrag)} \u00b7 darin enthaltene USt 19 %: {eur(round(betrag - netto, 2))}", st["body"]),
           Paragraph(rng.choice(["Barzahlung erhalten \u00b7 Vielen Dank f\u00fcr Ihren Einkauf.",
                                 "Zahlung per Karte \u00b7 Beleg bitte aufbewahren.",
                                 "Gegeben: \u2026 \u00b7 Zur\u00fcck: \u2026"]), st["small"]),
           Paragraph("Bei R\u00fcckgabe innerhalb von 14 Tagen mit Beleg.", st["small"])]
    return el, {"betrag": betrag, "gegenpartei": "\u2014", "nummer": f"Q-{rng.randint(1000,9999)}", "titel": "Quittung"}


def doc_lohnabrechnung(rng, ctx, st):
    brutto = round(rng.uniform(1980, 5400), 2)
    abzuege = [("Lohnsteuer", round(brutto * rng.uniform(0.08, 0.19), 2)),
               ("Solidarit\u00e4tszuschlag", round(brutto * 0.005, 2)),
               ("Rentenversicherung", round(brutto * 0.093, 2)),
               ("Arbeitslosenversicherung", round(brutto * 0.013, 2)),
               ("Krankenversicherung", round(brutto * rng.uniform(0.073, 0.089), 2)),
               ("Pflegeversicherung", round(brutto * 0.018, 2)),
               ("Betriebliche Altersvorsorge", round(brutto * 0.01, 2))]
    summe = round(sum(v for _, v in abzuege), 2)
    el = [Paragraph(f"{ctx['absender'][0]} \u2014 Lohn- und Gehaltsabrechnung", st["head"]),
          Paragraph(f"Arbeitgeber: {ctx['firma'][0]}, {ctx['firma'][2]}, {ctx['firma'][3]} {ctx['firma'][4]}", st["small"]),
          Paragraph(f"Entgeltabrechnung {rng.choice(['Januar','Februar','M\u00e4rz','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember'])} {ctx['jahr']}", st["h1"]),
          Paragraph(f"{ctx['bearbeiter']} \u00b7 Personalnummer {rng.randint(1000, 9999)} \u00b7 "
                    f"{ctx['abteilung']} \u00b7 Steuerklasse {rng.randint(1, 5)} \u00b7 "
                    f"Kostenstelle {rng.randint(100, 999)}", st["small"]), Spacer(1, 6)]
    rows = [["Bezeichnung", "Betrag"], ["Grundgehalt / Monatslohn", eur(brutto)]]
    for _ in range(rng.randint(0, 3)):
        rows.append([rng.choice(["Zulage Schicht", "Fahrtkostenzuschuss", "\u00dcberstunden 1,25-fach",
                                 "Erschwerniszulage", "Verm\u00f6genswirksame Leistungen"]), eur(round(rng.uniform(20, 480), 2))])
    rows.append(["Gesamtbrutto", eur(brutto)])
    for name, v in abzuege:
        rows.append([name, "-" + eur(v)])
    rows.append(["Nettoverdienst", eur(round(brutto - summe, 2))])
    rows.append(["Auszahlungsbetrag", eur(round(brutto - summe, 2))])
    t = Table(rows, colWidths=[110 * mm, 40 * mm])
    t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9), ("GRID", (0, 0), (-1, -1), 0.3, LIGHT),
                           ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                           ("FONTNAME", (0, len(rows) - 1), (-1, len(rows) - 1), "Helvetica-Bold"),
                           ("BACKGROUND", (0, len(rows) - 1), (-1, len(rows) - 1), colors.HexColor("#EEEEEE"))]))
    el += [t, Spacer(1, 6),
           Paragraph("Die Abrechnung wurde maschinell erstellt und ist ohne Unterschrift g\u00fcltig. "
                     "Einwendungen sind innerhalb von sechs Monaten geltend zu machen.", st["small"])]
    return el, {"betrag": round(brutto - summe, 2), "gegenpartei": ctx["bearbeiter"], "nummer": f"LO-{ctx['jahr']}-{rng.randint(1000,9999)}", "titel": "Entgeltabrechnung"}


def doc_frachtbrief(rng, ctx, st):
    el = briefkopf(ctx, st, kompakt=True)
    el.append(Paragraph("Frachtbrief / Transportauftrag", st["h1"]))
    felder = [("Auftragsnummer", ctx["liesnr"]), ("Absender", ctx["absender"][0]),
              ("Empf\u00e4nger", ctx["empf"]["name"]), ("Verladung", f"{dt(ctx['datum'])} 07:30"),
              ("Ankunft geplant", f"{dt(ctx['datum'] + timedelta(days=rng.randint(1, 3)))} {rng.randint(8, 17)}:00"),
              ("Kennzeichen", f"{rng.choice(['B','M','N','KA','HH','L'])}-{rng.choice(['AB','XY','KM','RT'])} {rng.randint(100, 9999)}"),
              ("Gewicht", f"{rng.randint(120, 22000)} kg"), ("Paletten", str(rng.randint(1, 33))),
              ("Frachtf\u00fchrer", ctx["bearbeiter"]), ("Sendungsnummer", f"{rng.randint(10**11, 10**12-1)}")]
    t = Table([[Paragraph(f"<b>{k}</b>", st["body"]), Paragraph(str(v), st["body"])] for k, v in felder], colWidths=[50 * mm, 100 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, LIGHT), ("TOPPADDING", (0, 0), (-1, -1), 5),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    el += [t, Spacer(1, 8),
           Paragraph("Erhaltene Sendung \u00fcberpr\u00fcft: \u25a1 ja &nbsp; \u25a1 nein &nbsp;&nbsp; "
                     "Sichtbare Sch\u00e4den: \u25a1 ja &nbsp; \u25a1 nein &nbsp;&nbsp; "
                     "Anzahl Packst\u00fccke: _______", st["body"]),
           Spacer(1, 14), Paragraph("Ort, Datum: ____________________   Unterschrift: ____________________", st["body"])]
    el += fuss(ctx, st)
    return el, {"betrag": None, "gegenpartei": ctx["empf"]["name"], "nummer": ctx["liesnr"], "titel": "Frachtbrief"}


def doc_inventur(rng, ctx, st):
    seiten = rng.randint(2, 7)
    el = [Paragraph("Inventurliste", st["h1"]),
          Paragraph(f"{ctx['firma'][0]} \u00b7 {ctx['firma'][2]}, {ctx['firma'][3]} {ctx['firma'][4]}", st["small"]),
          Paragraph(f"Standort {rng.choice(['Hauptlager','Au\u00dfenlager','Werkstattlager','Kommissionierung'])} "
                    f"\u00b7 Bereich {ctx['abteilung']} \u00b7 Stichtag {dt(ctx['datum'])} \u00b7 "
                    f"Z\u00e4hlkommission {ctx['bearbeiter']}", st["small"]), Spacer(1, 6)]
    for s in range(seiten):
        rows = [["Lfd.", "Artikelnummer", "Bezeichnung", "Bestand", "Einheit", "Buchwert"]]
        for i in range(rng.randint(16, 28)):
            rows.append([str(i + 1), f"ART-{rng.randint(10000, 99999)}", rng.choice(P.ARTIKEL_KURZ) + " " + rng.choice(["A", "B", "C", "Sonderposten", "Standard", "Ersatzteil", "Verschlei\u00df"]),
                         str(rng.randint(0, 480)), rng.choice(["Stk", "kg", "l", "m", "Karton", "Palette"]),
                         eur(round(rng.uniform(3, 1900), 2))])
        t = Table(rows, colWidths=[12 * mm, 26 * mm, 62 * mm, 20 * mm, 18 * mm, 22 * mm], repeatRows=1)
        t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
                               ("GRID", (0, 0), (-1, -1), 0.3, LIGHT), ("ALIGN", (3, 1), (5, -1), "RIGHT")]))
        el.append(t)
        if s < seiten - 1:
            el.append(PageBreak())
    return el, {"betrag": None, "gegenpartei": "\u2014", "nummer": f"INV-{ctx['jahr']}-{rng.randint(100,999)}", "titel": "Inventurliste"}


def doc_protokoll(rng, ctx, st):
    el = [Paragraph(rng.choice(["Besprechungsprotokoll", "Abnahmeprotokoll", "Begehungsprotokoll", "Wartungsprotokoll"]), st["h1"]),
          Paragraph(f"Ort: {ctx['firma'][2]}, {ctx['firma'][3]} {ctx['firma'][4]} &nbsp;\u00b7&nbsp; "
                    f"Datum: {dt(ctx['datum'])} &nbsp;\u00b7&nbsp; Beginn: {rng.randint(7, 15)}:{rng.choice(['00','15','30','45'])}", st["small"]),
          Paragraph(f"{ctx['firma'][0]} \u00b7 {ctx['firma'][2]}, {ctx['firma'][3]} {ctx['firma'][4]}", st["small"]),
          Spacer(1, 6), Paragraph(f"<b>Teilnehmende:</b> {ctx['bearbeiter']}, {rng.choice([p[0] for p in P.KUNDEN_PERSONEN])}, "
                                  f"{rng.choice([p[0] for p in P.KUNDEN_PERSONEN])}, {ctx['empf']['name']}", st["body"])]
    for i in range(1, rng.randint(4, 9)):
        el.append(Paragraph(f"<b>TOP {i}:</b> {rng.choice(['Stand der Ma\u00dfnahmen', 'Terminplanung', 'Kostenentwicklung', 'Personalplanung', 'Materialverf\u00fcgbarkeit', 'R\u00fcckmeldungen offener Punkte', 'Begehung der R\u00e4umlichkeiten', 'Bewertung der Ergebnisse'])}", st["body"]))
        el.append(Paragraph(rng.choice(P.BRIEF_ABSATZ), st["body"]))
        el.append(Paragraph(f"<i>Ergebnis:</i> {rng.choice(['erledigt', 'in Bearbeitung', 'vertagt', 'R\u00fcckmeldung bis '+dt(ctx['datum']+timedelta(days=14))])} &nbsp;\u00b7&nbsp; "
                            f"Verantwortlich: {rng.choice([p[0] for p in P.KUNDEN_PERSONEN])}", st["small"]))
    el += [Spacer(1, 10), Paragraph(f"Protokollf\u00fchrung: {ctx['bearbeiter']} \u00b7 N\u00e4chster Termin: {dt(ctx['datum'] + timedelta(days=28))}", st["small"])]
    return el, {"betrag": None, "gegenpartei": ctx["empf"]["name"], "nummer": ctx["az"], "titel": "Protokoll"}


def doc_police(rng, ctx, st):
    art = rng.choice(["Betriebshaftpflicht", "Inhaltsversicherung", "Firmenrechtsschutz",
                      "Kfz-Flottenversicherung", "Maschinenversicherung", "Cyber-Versicherung"])
    praemie = round(rng.uniform(190, 6400), 2)
    el = briefkopf(ctx, st, kompakt=True)
    el.append(Paragraph(f"Versicherungsschein \u2014 {art}", st["h1"]))
    felder = [("Versicherungsnummer", f"{rng.choice(['BP','IV','RS','KFZ','MV','CY'])}-{rng.randint(1000000, 9999999)}"),
              ("Versicherungsnehmer", ctx["empf"]["name"]), ("Anschrift", f"{ctx['empf']['strasse']}, {ctx['empf']['plz']} {ctx['empf']['ort']}"),
              ("Versicherungsbeginn", dt(ctx["datum"])), ("Vertragsablauf", dt(ctx["datum"] + timedelta(days=365))),
              ("Jahrespr\u00e4mie netto", eur(praemie)), ("Versicherungsteuer", eur(round(praemie * 0.19, 2))),
              ("Zahlungsrhythmus", rng.choice(["j\u00e4hrlich", "halbj\u00e4hrlich", "viertelj\u00e4hrlich"])),
              ("Selbstbehalt", eur(rng.choice([150, 250, 500, 1000])))]
    t = Table([[Paragraph(f"<b>{k}</b>", st["body"]), Paragraph(str(v), st["body"])] for k, v in felder], colWidths=[52 * mm, 98 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, LIGHT), ("TOPPADDING", (0, 0), (-1, -1), 5),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    el += [t, Spacer(1, 8), Paragraph("Der Versicherungsschutz richtet sich nach den beigef\u00fcgten "
                                      "Versicherungsbedingungen in der jeweils g\u00fcltigen Fassung. "
                                      "Obliegenheitsverletzungen k\u00f6nnen zum Verlust des Versicherungsschutzes f\u00fchren.", st["small"])]
    el += fuss(ctx, st)
    return el, {"betrag": praemie, "gegenpartei": ctx["empf"]["name"], "nummer": f"V-{rng.randint(100000,999999)}", "titel": f"Police {art}"}


def doc_steuerbescheid(rng, ctx, st):
    steuer = round(rng.uniform(120, 9800), 2)
    el = [Paragraph(f"{ctx['absender'][0]} \u2014 {ctx['absender'][2]}, {ctx['absender'][3]} {ctx['absender'][4]}", st["head"]),
          Paragraph("Bescheid \u00fcber Umsatzsteuer-Vorauszahlung", st["h1"]),
          Paragraph(f"{ctx['firma'][0]}, {ctx['firma'][2]}, {ctx['firma'][3]} {ctx['firma'][4]}<br/>"
                    f"Steuernummer {ctx['steuernr']} &nbsp;\u00b7&nbsp; USt-IdNr. {ctx['ustid']} &nbsp;\u00b7&nbsp; Zeitraum {rng.choice(['Januar','Februar','M\u00e4rz','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember'])} {ctx['jahr']} "
                    f"&nbsp;\u00b7&nbsp; Datum {dt(ctx['datum'])}", st["small"]), Spacer(1, 6)]
    rows = [["Position", "Bemessungsgrundlage", "Betrag"],
            ["Ums\u00e4tze 19 %", eur(round(steuer * 4, 2)), eur(round(steuer * 0.76, 2))],
            ["Ums\u00e4tze 7 %", eur(round(steuer * 0.8, 2)), eur(round(steuer * 0.056, 2))],
            ["Vorsteuer abziehbar", "", "-" + eur(round(steuer * 0.31, 2))],
            ["Zahlbetrag", "", eur(steuer)]]
    t = Table(rows, colWidths=[70 * mm, 45 * mm, 35 * mm])
    t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9), ("GRID", (0, 0), (-1, -1), 0.4, LIGHT),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
                           ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                           ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")]))
    el += [t, Spacer(1, 8),
           Paragraph(f"Der Betrag von {eur(steuer)} ist bis zum {dt(ctx['datum'] + timedelta(days=10))} "
                     f"auf das Konto der Finanzkasse zu \u00fcberweisen. "
                     f"Bei versp\u00e4teter Zahlung werden S\u00e4umniszuschl\u00e4ge erhoben.", st["body"]),
           Paragraph("Rechtsbehelfsbelehrung: Gegen diesen Bescheid kann innerhalb eines Monats nach "
                     "Bekanntgabe Einspruch eingelegt werden. Der Einspruch ist schriftlich oder zur "
                     "Niederschrift zu erkl\u00e4ren.", st["small"])]
    return el, {"betrag": steuer, "gegenpartei": "Finanzamt Musterstadt", "nummer": f"UST-{ctx['jahr']}-{rng.randint(10,12)}", "titel": "Steuerbescheid"}


TYPEN = [
    ("rechnung", 30, doc_rechnung),
    ("mahnung", 8, doc_mahnung),
    ("lieferschein", 7, doc_lieferschein),
    ("angebot", 7, doc_angebot),
    ("brief", 8, doc_brief),
    ("bestellung", 5, doc_bestellung),
    ("formular", 5, doc_formular),
    ("auftragsbestaetigung", 4, doc_auftragsbestaetigung),
    ("kontoauszug", 4, doc_kontoauszug),
    ("vertrag", 3, doc_vertrag),
    ("gutschrift", 3, doc_gutschrift),
    ("rundschreiben", 3, doc_rundschreiben),
    ("quittung", 3, doc_quittung),
    ("reklamation", 2, doc_reklamation),
    ("lohnabrechnung", 2, doc_lohnabrechnung),
    ("frachtbrief", 2, doc_frachtbrief),
    ("inventur", 2, doc_inventur),
    ("protokoll", 2, doc_protokoll),
    ("police", 1, doc_police),
    ("steuerbescheid", 1, doc_steuerbescheid),
]
TYP_WEIGHTS = [w for _, w, _ in TYPEN]
TYP_FUNCS = {n: f for n, _, f in TYPEN}


# ------------------------------------------------------------------ Dateinamen
def nrm(s):
    for a, b in (("\u00e4", "ae"), ("\u00f6", "oe"), ("\u00fc", "ue"), ("\u00df", "ss"), ("\u00c4", "Ae"), ("\u00d6", "Oe"), ("\u00dc", "Ue")):
        s = s.replace(a, b)
    return s


def make_name(rng, typ, ctx, counter):
    d = ctx["datum"]
    kunde = nrm(ctx["empf"]["name"])
    kurz = kunde.split()[0]
    muster = rng.random()
    ext = ".pdf" if rng.random() < 0.82 else rng.choice([".PDF", ".Pdf", ".pdf"])
    if muster < 0.16:
        s = f"Scan_{d.strftime('%Y-%m-%d')}_{rng.randint(1, 9999):04d}"
    elif muster < 0.28:
        s = f"{typ}_{ctx['rechnr'].replace('RE-', '')}_{kurz}"
    elif muster < 0.38:
        s = f"{nrm(typ.upper())}-{d.year}-{rng.randint(100, 99999)}"
    elif muster < 0.46:
        s = f"{counter:07d}"
    elif muster < 0.54:
        s = f"SCAN{rng.randint(1, 99999):05d}"
        ext = ".PDF"
    elif muster < 0.60:
        s = f"img-{d.strftime('%Y%m%d')}-{rng.randint(1, 999):03d}"
    elif muster < 0.66:
        s = f"Kopie von {nrm(typ)}_{rng.randint(1, 999):03d}"
    elif muster < 0.72:
        s = f"{nrm(typ)} {d.strftime('%B')} {d.year} {kurz}"
    elif muster < 0.78:
        s = f"Dokument_{rng.randint(1, 99999)}"
    elif muster < 0.84:
        s = f"{kurz}-{nrm(typ)}-{d.strftime('%Y%m%d')}"
    elif muster < 0.88:
        s = f"{d.year}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}_{rng.randint(1, 99):02d} {nrm(typ)}"
    elif muster < 0.92:
        s = f"{rng.randint(1, 999)}"
    elif muster < 0.95:
        s = f"{ctx['kundennr'].replace('-', '')}_{nrm(typ)}_{rng.randint(10, 99)}"
    elif muster < 0.97:
        s = f"{nrm(typ)}-{nrm(ctx['absender'][0])[:22].replace(' ', '_')}"
    else:
        s = f"Bitte_pruefen_{kurz}_{rng.randint(100, 999)}"
    s = s.replace("/", "-").replace("\\", "-").replace(":", "-").replace("?", "").replace("*", "").replace('"', "").replace("<", "").replace(">", "").replace("|", "-")
    s = s.strip()[:110]
    return s + ext


# ---------------------------------------------------------------------- Bauen
def write_pdf(path, story, ctx, typ, st, titel):
    doc = SimpleDocTemplate(path, pagesize=A5 if typ == "quittung" else A4,
                            leftMargin=22 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=20 * mm,
                            title=f"{titel} \u2013 {ctx['absender'][0]}", author=ctx["absender"][0],
                            subject=titel, creator=f"{ctx['absender'][0]} Warenwirtschaft",
                            keywords=f"{typ}, {ctx['absender'][0]}, {ctx['firma'][0]}, {ctx['datum'].year}")

    def fusszeile(canv, d):
        canv.saveState()
        canv.setFont("Helvetica", 7)
        canv.setFillColor(GREY)
        canv.drawString(22 * mm, 12 * mm, f"{ctx['absender'][0]} \u00b7 {ctx['absender'][3]} {ctx['absender'][4]} \u00b7 {ctx['tel']}")
        canv.drawRightString(A4[0] - 18 * mm, 12 * mm, f"Seite {d.page}")
        canv.drawCentredString(A4[0] / 2, 12 * mm, f"{ctx['az']}")
        canv.restoreState()

    doc.build(story, onFirstPage=fusszeile, onLaterPages=fusszeile)
    return doc.page


def derive(seed, heute=False):
    """Erzeugt alle Parameter eines Dokuments deterministisch aus einem Seed.

    Wird sowohl beim Erzeugen der Dateinamen als auch im Worker aufgerufen,
    damit Dateiname und Inhalt garantiert denselben Dokumenttyp haben.
    Mit heute=True wird das Dokument auf den heutigen Tag datiert (Jahr in Nummern
    und Dateinamen zieht mit), sonst auf den Zeitraum 2023–2026.
    """
    rng = random.Random(seed)
    today = date(2023, 1, 2) + timedelta(days=rng.randint(0, (date(2026, 9, 26) - date(2023, 1, 2)).days))
    typ = rng.choices([n for n, _, _ in TYPEN], weights=TYP_WEIGHTS, k=1)[0]
    ctx = make_ctx(rng, today, f"AZ-{rng.randint(10000, 99999)}", typ)
    font = rng.choice(["Helvetica", "Helvetica", "Helvetica", "Times-Roman", "Courier"])
    if heute:
        altes_jahr = ctx["jahr"]
        today = date.today()
        ctx["datum"], ctx["jahr"] = today, today.year
        for feld in ("rechnr", "angebotnr", "liesnr", "abnr", "bestnr"):
            ctx[feld] = ctx[feld].replace(str(altes_jahr), str(today.year))
    return rng, typ, today, ctx, font


def build_one(spec, flat=False, heute=False):
    idx, seed, outdir, name = spec
    rng, typ, today, ctx, font = derive(seed, heute)
    st = basis_styles(font)
    story, meta = TYP_FUNCS[typ](rng, ctx, st)
    if flat:
        ordner = outdir
        os.makedirs(ordner, exist_ok=True)
    else:
        ordner = os.path.join(outdir, f"{today.year:04d}", f"{today.month:02d}")
        os.makedirs(ordner, exist_ok=True)
    path = os.path.join(ordner, name)
    try:
        pages = write_pdf(path, story, ctx, typ, st, meta["titel"])
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{name}: {type(exc).__name__}: {exc}", "index": idx}
    size = os.path.getsize(path)
    return {"error": None, "index": idx, "datei": name, "typ": typ, "titel": meta["titel"],
            "datum": dt(today), "ordner": f"{today.year:04d}/{today.month:02d}",
            "absender": ctx["absender"][0], "empfaenger": ctx["firma"][0],
            "nummer": meta["nummer"], "betrag": meta["betrag"], "seiten": pages, "bytes": size}


def build_chunk(job):
    chunk_id, specs, outdir, flat, heute = job
    res = []
    for spec in specs:
        res.append(build_one((spec[0], spec[1], outdir, spec[2]), flat, heute))
    return chunk_id, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--count", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20260927)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--index", default=None)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--flat", action="store_true", help="ohne Jahr/Monat-Unterordner ablegen")
    ap.add_argument("--document-today", action="store_true",
                    help="Dokumente auf heute datieren statt auf den Zeitraum 2023-2026")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    rng = random.Random(a.seed)
    used = set()
    specs = []
    for i in range(a.count):
        s = rng.randint(1, 2 ** 31 - 1)
        r2, typ, _today, tmp_ctx, _font = derive(s, a.document_today)
        name = make_name(r2, typ, tmp_ctx, i + 1)
        base, ext = os.path.splitext(name)
        ordk = "" if a.flat else f"{_today.year:04d}/{_today.month:02d}/"
        k = ordk + name.lower()
        n = 1
        while k in used or os.path.exists(os.path.join(a.out, ("" if a.flat else ordk), name)):
            name = f"{base}_{n}{ext}"
            k = ordk + name.lower()
            n += 1
        used.add(k)
        specs.append((i, s, name))

    jobs = []
    per = max(1, len(specs) // a.jobs)
    for c in range(0, len(specs), per):
        jobs.append((len(jobs), specs[c:c + per], a.out, a.flat, a.document_today))

    t0 = time.time()
    rows, errors = [], []
    done = 0
    with Pool(a.jobs if len(jobs) > 1 else 1) as pool:
        for chunk_id, res in pool.imap_unordered(build_chunk, jobs):
            for r in res:
                if r.get("error"):
                    errors.append(r["error"])
                else:
                    rows.append(r)
            done += len(res)
            if not a.quiet:
                print(f"  {done}/{len(specs)} Dateien  ({time.time()-t0:.0f}s)", flush=True)
    rows.sort(key=lambda r: r["index"])
    idx_path = a.index or os.path.join(a.out, "_index.csv")
    if rows:
        with open(idx_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    total = sum(r["bytes"] for r in rows)
    print(f"\nFertig: {len(rows)} PDFs in {a.out}")
    print(f"Gesamtgr\u00f6\u00dfe: {total/1024/1024:.1f} MB \u00b7 Dauer {time.time()-t0:.1f}s \u00b7 Fehler {len(errors)}")
    print(f"Index: {idx_path}")
    for e in errors[:20]:
        print("  FEHLER:", e)
    typcount = {}
    for r in rows:
        typcount[r["typ"]] = typcount.get(r["typ"], 0) + 1
    print("Verteilung:", ", ".join(f"{k}={v}" for k, v in sorted(typcount.items(), key=lambda x: -x[1])))


if __name__ == "__main__":
    main()