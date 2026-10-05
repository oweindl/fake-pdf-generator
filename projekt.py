# -*- coding: utf-8 -*-
"""Erzeugt zusammenhängende Projektdokumentationen als PDF.

Ein Projekt bekommt eine Nummer im Format P-<Jahr>-<Zahl>-<Kurzbezeichnung> und einen eigenen
Ordner. Darin liegen alle Dokumente, die im Projektverlauf anfallen: Projektübersicht, Skizze,
Besprechungsnotizen, Bautagebuch, Lieferscheine, Aufmaß, Terminplan, Mängelliste, Abnahme,
Behinderungsanzeige, Stundenaufstellung, Abschlagsrechnungen, Fotoliste, Gefährdungsbeurteilung
und Abschlussbericht — alle mit derselben Projektnummer, chronologisch über die Laufzeit verteilt.

    python projekt.py --out D:/projekte --projekte 3 --dokumente 15 --seed 2026
    python projekt.py --out D:/projekte --projekte 1 --dokumente 30 --seed 7 --flat
"""
from __future__ import annotations

import argparse
import csv
import os
import random
import re
import sys
import time
from datetime import date, timedelta
from multiprocessing import Pool

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, PageBreak, Paragraph, Spacer, Table, TableStyle

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen as G  # noqa: E402
import pools as P  # noqa: E402

GREY, LIGHT, RULE = G.GREY, G.LIGHT, G.RULE


def _utf8_ausgabe():
    """Kindprozesse schreiben in eine Pipe: ohne das scheitern Umlaute und Pfeile an cp1252."""
    import sys as _sys
    for strom in (_sys.stdout, _sys.stderr):
        try:
            strom.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


_utf8_ausgabe()

PROJEKTARTEN = [
    ("Elektroinstallation Neubau", "Elektro", ["Mehrfamilienhaus Sonnenweg", "Kindertagesstätte Am Park",
                                               "Bürogebäude Hafenblick", "Schulerweiterung Feldstraße"]),
    ("Sanierung Elektroanlage", "Elektro", ["Grundschule Altstadt", "Verwaltungsgebäude Rathausplatz",
                                            "Wohnblock Lindenallee", "Sporthalle Nordring"]),
    ("Photovoltaik-Aufdachanlage", "Elektro", ["Logistikhalle Gewerbepark", "Landwirtschaftliche Halle Feldweg",
                                               "Werkstattgebäude Industriestraße"]),
    ("Heizungs- und Sanitärsanierung", "SHK", ["Pflegeheim Sonnenhof", "Hotelpension Zur Linde",
                                               "Mehrfamilienhaus Uferstraße"]),
    ("Lüftungsanlage Neubau", "SHK", ["Produktionshalle Werkstraße", "Kantine Gewerbepark Süd"]),
    ("Netzwerk- und EDV-Verkabelung", "IT", ["Kanzlei Justizplatz", "Klinikneubau Forschungsring"]),
    ("Straßen- und Tiefbauarbeiten", "Tiefbau", ["Erschließung Neubaugebiet Talstraße",
                                                 "Sanierung Kanal Hauptstraße"]),
    ("Badsanierung", "SHK", ["Wohnung Mühlenweg 12", "Gästehaus Seestraße 4"]),
]

BAUHERREN = P.KUNDEN_FIRMEN
GEWERKE = ["Elektroinstallation", "Blitzschutz", "Netzwerktechnik", "Heizung", "Sanitär", "Lüftung",
           "Tiefbau", "Erdungsanlage", "Beleuchtung", "Sicherheitstechnik"]
BEHINDERUNGEN = [
    "Verzögerte Materiallieferung durch den Vorlieferanten",
    "Baustellenzufahrt nicht befahrbar (Witterung)",
    "Vorleistung des Rohbaus nicht abgeschlossen",
    "Unvorhergesehener Fund in der Bestandsanlage",
    "Stromanschluss am Bauprovisorium nicht verfügbar",
    "Zusätzliche Koordination mit anderen Gewerken erforderlich",
]
MAENGEL = [
    "Leitung nicht fachgerecht befestigt", "Klemme nicht angezogen", "Kennzeichnung fehlt",
    "Abdeckung beschädigt", "Bohrloch nicht verschlossen", "Schutzleiter nicht angeschlossen",
    "Kabeldurchführung ohne Brandschott", "Beschriftung unlesbar",
]
ARBEITEN = [
    "Leitungsverlegung im Erdgeschoss", "Setzen der Unterverteilung", "Montage der Leuchten",
    "Kabelzug Steigeschacht", "Anschluss der RLT-Anlage", "Erdungsmessung durchgeführt",
    "Dosen setzen und verdrahten", "Schlitze fräsen und schließen", "Rohbauabnahme vorbereitet",
    "Bestandsaufnahme und Aufmaß", "Demontage der Altinstallation", "Prüfung nach DGUV V3",
]
WETTER = [("trocken", 8, 18), ("bewölkt", 6, 15), ("Regen", 4, 12), ("Sonnig", 12, 26),
          ("Nebel", 2, 9), ("Wind", 7, 14), ("Schnee", -3, 3)]


# ------------------------------------------------------------------ Projektkontext
def projekt(rng, jahr, nummer):
    art, gewerk, objekte = rng.choice(PROJEKTARTEN)
    objekt = rng.choice(objekte)
    bauherr = rng.choice(BAUHERREN)
    kurz = G.nrm(objekt).replace(" ", "_")[:28]
    pnr = f"P-{jahr}-{nummer:04d}-{kurz}"
    start = date(jahr, 1, 7) + timedelta(days=rng.randint(0, 300))
    dauer = rng.choice([3, 5, 8, 12, 16, 24]) * 7
    return {
        "nummer": pnr,
        "art": art,
        "gewerk": gewerk,
        "objekt": objekt,
        "bauherr": bauherr,
        "bauleiter": rng.choice([p[0] for p in P.KUNDEN_PERSONEN]),
        "obermonteur": rng.choice([p[0] for p in P.KUNDEN_PERSONEN]),
        "start": start,
        "ende": start + timedelta(days=dauer),
        "summe": round(rng.uniform(18_000, 420_000), 2),
        "team": [p[0] for p in rng.sample(P.KUNDEN_PERSONEN, 3)],
        "bauherr_ansprech": rng.choice([p[0] for p in P.KUNDEN_PERSONEN]),
    }


def dokument_ctx(prj, datum, rng, absender=None, bearbeiter=None):
    """ctx im Format von gen.py, damit Stile, Kopf- und Fußzeile wiederverwendet werden können."""
    a = absender or P.SIM_FIRMA
    return {
        "absender": a,
        "empf": {"name": prj["bauherr"][0], "strasse": prj["bauherr"][1],
                 "plz": prj["bauherr"][2], "ort": prj["bauherr"][3], "person": None},
        "firma": P.SIM_FIRMA,
        "datum": datum,
        "jahr": datum.year,
        "az": prj["nummer"],
        "tel": a[5],
        "bearbeiter": bearbeiter or prj["bauleiter"],
        "abteilung": prj["gewerk"],
        "projekt": prj,
        "geschaeftsfuehrer": prj["bauleiter"],
        "ustid": P.ust_id(rng),
        "steuernr": f"{rng.randint(10, 99)}/{rng.randint(100, 999)}/{rng.randint(10000, 99999)}",
        "iban": P.iban(rng),
        "bank": rng.choice(P.BANKEN)[0],
        "kundennr": f"K-{rng.randint(10000, 99999)}",
        "bestnr": f"BE-{datum.year}-{rng.randint(1000, 9999)}",
        "rechnr": f"AR-{datum.year}-{rng.randint(1000, 9999)}",
        "zahlungsziel": 30,
    }


def kopf(ctx, st, titel, unterzeile=None, mit_adresse=True):
    p = ctx["projekt"]
    el = G.briefkopf(ctx, st) if mit_adresse else [
        Paragraph(f"<b>{ctx['absender'][0]}</b>", st["head"]),
        HRFlowable(width="100%", thickness=0.7, color=RULE, spaceAfter=8)]
    el.append(Paragraph(titel, st["h1"]))
    zeile = (f"Projekt {p['nummer']} &nbsp;\u00b7&nbsp; {p['objekt']} &nbsp;\u00b7&nbsp; "
             f"Bauherr: {p['bauherr'][0]} &nbsp;\u00b7&nbsp; Datum: {G.dt(ctx['datum'])}")
    if unterzeile:
        zeile += f" &nbsp;\u00b7&nbsp; {unterzeile}"
    el.append(Paragraph(zeile, st["small"]))
    el.append(Spacer(1, 6))
    return el


def tabelle(rows, breiten, kopfzeile=True, size=8.5):
    t = Table(rows, colWidths=breiten, repeatRows=1 if kopfzeile else 0)
    stil = [("FONTSIZE", (0, 0), (-1, -1), size), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.3, LIGHT),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if kopfzeile:
        stil += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
                 ("FONTNAME", (0, 0), (-1, 0), st_fett)]
    t.setStyle(TableStyle(stil))
    return t


st_fett = "Helvetica-Bold"


def fuss(ctx, st):
    return G.fuss(ctx, st, extra=f"Projektakte {ctx['projekt']['nummer']} \u00b7 {ctx['projekt']['art']}")


# ---------------------------------------------------------------- Dokumententypen
def d_uebersicht(rng, ctx, st):
    p = ctx["projekt"]
    el = kopf(ctx, st, "Projektübersicht", "Steckbrief", mit_adresse=False)
    felder = [("Projektnummer", p["nummer"]), ("Bezeichnung", p["art"]), ("Bauvorhaben", p["objekt"]),
              ("Bauherr / Auftraggeber", f"{p['bauherr'][0]}, {p['bauherr'][1]}, {p['bauherr'][2]} {p['bauherr'][3]}"),
              ("Gewerk", p["gewerk"]), ("Bauleiter", p["bauleiter"]), ("Obermonteur", p["obermonteur"]),
              ("Projektlaufzeit", f"{G.dt(p['start'])} bis {G.dt(p['ende'])}"),
              ("Auftragssumme netto", G.eur(p["summe"])),
              ("Zahlungsplan", rng.choice(["3 Abschläge à 30/40/30 %", "2 Abschläge à 50 %",
                                           "Abschlag nach Baufortschritt"])),
              ("Baustellenzufahrt", rng.choice(["über Hofeinfahrt, Zufahrt freihalten",
                                                "nur über Nordtor, Schlüssel beim Pförtner",
                                                "öffentliche Straße, Halteverbot beachten"])),
              ("Besonderheiten", rng.choice(["Arbeiten im laufenden Betrieb",
                                             "Denkmalschutzauflagen zu beachten",
                                             "Nachtarbeiten nach Absprache",
                                             "Staubschutz und Absperrung erforderlich"]))]
    el.append(tabelle([[Paragraph(f"<b>{k}</b>", st["body"]), Paragraph(str(v), st["body"])] for k, v in felder],
                      [55 * mm, 110 * mm], kopfzeile=False))
    el += [Spacer(1, 8), Paragraph("<b>Meilensteine</b>", st["h2"])]
    ms = [["Meilenstein", "Termin", "Status"]]
    for i, (name, anteil) in enumerate([("Baustelleneinrichtung", 0.05), ("Rohbauabnahme", 0.3),
                                        ("Montage abgeschlossen", 0.6), ("Abnahme mit Bauherr", 0.9),
                                        ("Schlussrechnung", 1.0)], 1):
        termin = p["start"] + timedelta(days=int((p["ende"] - p["start"]).days * anteil))
        ms.append([name, G.dt(termin), rng.choice(["erledigt", "erledigt", "läuft", "offen"])])
    el.append(tabelle(ms, [70 * mm, 35 * mm, 40 * mm]))
    el += [Spacer(1, 6), Paragraph("<b>Beteiligte</b>", st["h2"])]
    bet = [["Rolle", "Person / Firma", "Kontakt"]]
    for rolle, person in (("Bauleitung Auftragnehmer", p["bauleiter"]), ("Obermonteur", p["obermonteur"]),
                          ("Ansprechpartner Bauherr", p["bauherr_ansprech"]),
                          ("Bauherr", p["bauherr"][0])):
        bet.append([rolle, person, P.telefon(rng) if "@" not in person else person])
    el.append(tabelle(bet, [55 * mm, 60 * mm, 45 * mm]))
    el += fuss(ctx, st)
    return el, {"titel": "Projektübersicht", "betrag": p["summe"]}


def d_skizze(rng, ctx, st):
    p = ctx["projekt"]
    el = kopf(ctx, st, "Projektskizze", "Leistungsumfang und Ablauf", mit_adresse=False)
    el.append(Paragraph("<b>Ausgangslage</b>", st["h2"]))
    el.append(Paragraph(f"Für das Bauvorhaben {p['objekt']} in {p['bauherr'][3]} wurde die Firma "
                        f"{P.SIM_FIRMA[0]} mit den Leistungen im Gewerk {p['gewerk']} beauftragt. "
                        f"Die Maßnahme umfasst die Bereiche {rng.sample(GEWERKE, 3)[0]}, "
                        f"{rng.sample(GEWERKE, 3)[1]} und {rng.sample(GEWERKE, 3)[2]}.", st["body"]))
    el.append(Paragraph("<b>Ziel und Umfang</b>", st["h2"]))
    el.append(Paragraph(rng.choice(P.BRIEF_ABSATZ), st["body"]))
    rows = [["Pos.", "Leistungsposition", "Menge", "Einheit"]]
    for i in range(1, rng.randint(6, 12)):
        bez, einheit, _ = rng.choice(G.P.DIENSTLEISTUNGEN)
        rows.append([str(i), bez, G.num(rng.choice([1, 2, 5, 12, 20, 40, 80])), einheit])
    el += [Spacer(1, 4), tabelle(rows, [12 * mm, 100 * mm, 22 * mm, 22 * mm]), Spacer(1, 8)]
    el.append(Paragraph("<b>Termine und Risiken</b>", st["h2"]))
    el.append(Paragraph(f"Geplanter Beginn {G.dt(p['start'])}, geplantes Ende {G.dt(p['ende'])}. "
                        f"Als Risiko wird vor allem {rng.choice(BEHINDERUNGEN).lower()} gesehen; "
                        f"entsprechend sind Puffer im Terminplan vorgesehen.", st["body"]))
    el.append(Paragraph("<b>Nächste Schritte</b>", st["body"]))
    for s in ("Detailplanung und Werkstattzeichnungen", "Materialdisposition", "Baustelleneinrichtung",
              "Start der Montagearbeiten"):
        el.append(Paragraph(f"\u2022 {s} — Verantwortlich: {rng.choice([p['bauleiter'], p['obermonteur']])}, "
                            f"bis {G.dt(p['start'] + timedelta(days=rng.randint(3, 30)))}", st["body"]))
    el += fuss(ctx, st)
    return el, {"titel": "Projektskizze", "betrag": None}


def d_notiz(rng, ctx, st):
    p = ctx["projekt"]
    thema = rng.choice(["Baubesprechung", "Planungsbesprechung", "Koordinationsgespräch",
                        "Ortsbegehung", "Abstimmung mit dem Bauherrn", "Jour fixe"])
    el = kopf(ctx, st, f"Besprechungsnotiz — {thema}", mit_adresse=False)
    teilnehmer = [p["bauleiter"], p["obermonteur"], p["bauherr_ansprech"]] + \
                 [x[0] for x in rng.sample(P.KUNDEN_PERSONEN, 2)]
    el.append(Paragraph(f"<b>Ort:</b> Baustelle {p['objekt']} &nbsp;\u00b7&nbsp; "
                        f"<b>Beginn:</b> {rng.randint(7, 15)}:{rng.choice(['00', '15', '30'])} Uhr "
                        f"&nbsp;\u00b7&nbsp; <b>Dauer:</b> {rng.randint(1, 3)} h", st["body"]))
    el.append(Paragraph(f"<b>Teilnehmende:</b> " + ", ".join(dict.fromkeys(teilnehmer)), st["body"]))
    for i in range(1, rng.randint(4, 8)):
        el.append(Paragraph(f"<b>TOP {i}:</b> {rng.choice(['Stand der Arbeiten', 'Terminsituation', 'Materialverfügbarkeit', 'Koordination Gewerke', 'Nachträge und Mehrkosten', 'Mängel und Restpunkte', 'Sicherheitsfragen', 'Abstimmung Terminplan'])}", st["body"]))
        el.append(Paragraph(rng.choice(P.BRIEF_ABSATZ), st["body"]))
    el.append(Paragraph("<b>Aufgaben</b>", st["h2"]))
    rows = [["Aufgabe", "Verantwortlich", "Frist", "Status"]]
    for _ in range(rng.randint(2, 5)):
        rows.append([rng.choice(["Nachforderung erstellen", "Material nachbestellen", "Termin mit Bauherrn",
                                 "Mängel beseitigen", "Aufmaß nachreichen", "Zeichnung aktualisieren"]),
                     rng.choice(teilnehmer), G.dt(ctx["datum"] + timedelta(days=rng.choice([3, 7, 14]))),
                     rng.choice(["offen", "läuft", "erledigt"])])
    el += [tabelle(rows, [75 * mm, 40 * mm, 28 * mm, 22 * mm]), Spacer(1, 6),
           Paragraph(f"Protokoll: {ctx['bearbeiter']} \u00b7 Nächste Besprechung: "
                     f"{G.dt(ctx['datum'] + timedelta(days=14))}", st["small"])]
    el += fuss(ctx, st)
    return el, {"titel": thema, "betrag": None}


def d_bautagebuch(rng, ctx, st):
    p = ctx["projekt"]
    wetter, tmin, tmax = rng.choice(WETTER)
    el = kopf(ctx, st, "Bautagebuch — Tagesbericht", mit_adresse=False)
    felder = [("Datum", G.dt(ctx["datum"])), ("Wetter", f"{wetter}, {tmin} bis {tmax} \u00b0C"),
              ("Arbeitsbeginn", f"{rng.randint(6, 8)}:00 Uhr"), ("Arbeitsende", f"{rng.randint(15, 18)}:30 Uhr"),
              ("Geräte auf der Baustelle", rng.choice(["Kernbohrgerät, Leiter, Werkzeugkoffer",
                                                       "Hubarbeitsbühne, Kabeltrommel, Presse",
                                                       "Minibagger, Rüttelplatte, Werkzeug"])),
              ("Baustellenzustand", rng.choice(["Zufahrt frei", "Zufahrt durch Fremdgewerk blockiert",
                                                "Stromanschluss vorhanden", "Wasseranschluss fehlt"]))]
    el.append(tabelle([[Paragraph(f"<b>{k}</b>", st["body"]), Paragraph(str(v), st["body"])] for k, v in felder],
                      [55 * mm, 110 * mm], kopfzeile=False))
    el += [Spacer(1, 8), Paragraph("<b>Personal und Stunden</b>", st["h2"])]
    rows = [["Mitarbeiter", "Funktion", "Stunden", "Tätigkeit"]]
    for person in p["team"] + [p["obermonteur"]]:
        rows.append([person, rng.choice(["Monteur", "Helfer", "Obermonteur", "Auszubildender"]),
                     G.num(rng.choice([4, 6, 8, 8.5, 9])), rng.choice(ARBEITEN)])
    el.append(tabelle(rows, [42 * mm, 30 * mm, 20 * mm, 73 * mm]))
    el += [Spacer(1, 8), Paragraph("<b>Ausgeführte Arbeiten</b>", st["h2"])]
    for _ in range(rng.randint(2, 4)):
        el.append(Paragraph(f"\u2022 {rng.choice(ARBEITEN)}", st["body"]))
    el.append(Paragraph("<b>Behinderungen / Stillstand</b>", st["h2"]))
    if rng.random() < 0.45:
        el.append(Paragraph(f"{rng.choice(BEHINDERUNGEN)} — Stillstand {G.num(rng.choice([1, 2, 3.5, 4]))} h, "
                            f"an Bauherrn gemeldet am {G.dt(ctx['datum'])}.", st["body"]))
    else:
        el.append(Paragraph("Keine Behinderungen, Arbeiten liefen planmäßig.", st["body"]))
    el.append(Paragraph("<b>Mängel / offene Punkte</b>", st["h2"]))
    el.append(Paragraph(rng.choice(MAENGEL) + f" (Bereich {rng.choice(['EG', 'OG 1', 'OG 2', 'Keller', 'Außenanlage'])}), "
                        f"beseitigt: {rng.choice(['ja', 'nein, Nacharbeit erforderlich'])}", st["body"])
               if rng.random() < 0.5 else Paragraph("Keine Mängel festgestellt.", st["body"]))
    el += [Spacer(1, 12), Paragraph(f"Unterschrift Bauleitung: {p['bauleiter']} "
                                    f"&nbsp;&nbsp;&nbsp; Unterschrift Bauherr: ____________________", st["body"])]
    el += fuss(ctx, st)
    return el, {"titel": "Bautagebuch", "betrag": None}


def d_lieferschein(rng, ctx, st):
    p = ctx["projekt"]
    el = kopf(ctx, st, "Lieferschein (projektbezogen)", mit_adresse=False)
    el.append(Paragraph(f"<b>Lieferant:</b> {ctx['absender'][0]}, {ctx['absender'][2]}, "
                        f"{ctx['absender'][3]} {ctx['absender'][4]} &nbsp;\u00b7&nbsp; "
                        f"<b>Lieferschein-Nr.:</b> LS-{ctx['datum'].year}-{rng.randint(1000, 9999)} "
                        f"&nbsp;\u00b7&nbsp; <b>Bestellung:</b> {ctx['bestnr']}", st["body"]))
    el.append(Paragraph(f"<b>Empfänger:</b> {P.SIM_FIRMA[0]}, {P.SIM_FIRMA[2]}, "
                        f"{P.SIM_FIRMA[3]} {P.SIM_FIRMA[4]}<br/>"
                        f"<b>Lieferanschrift:</b> Baustelle {p['objekt']}, {p['bauherr'][1]}, "
                        f"{p['bauherr'][2]} {p['bauherr'][3]} &nbsp;\u00b7&nbsp; "
                        f"<b>Ansprechpartner vor Ort:</b> {p['obermonteur']}", st["body"]))
    rows = [["Pos.", "Artikel / Bezeichnung", "Menge", "Einheit", "Bemerkung"]]
    for i in range(1, rng.randint(3, 9)):
        bez, einheit, _ = rng.choice(G.P.ARTIKEL)
        rows.append([str(i), bez, G.num(rng.choice([1, 2, 5, 10, 25, 50])), einheit,
                     rng.choice(["", "", "vollständig", "Teillieferung", "Rückstand"])])
    el += [Spacer(1, 4), tabelle(rows, [12 * mm, 80 * mm, 20 * mm, 20 * mm, 33 * mm]), Spacer(1, 8),
           Paragraph("Ware erhalten am: ____________________ &nbsp;&nbsp; Name: "
                     f"{p['obermonteur']} &nbsp;&nbsp; Unterschrift: ____________________", st["body"]),
           Paragraph("Die Ware wurde auf Vollständigkeit und Transportschäden geprüft.", st["small"])]
    el += fuss(ctx, st)
    return el, {"titel": "Lieferschein", "betrag": None}


def d_aufmass(rng, ctx, st):
    p = ctx["projekt"]
    el = kopf(ctx, st, "Aufmaßprotokoll", mit_adresse=False)
    el.append(Paragraph(f"Aufgenommen am {G.dt(ctx['datum'])} von {ctx['bearbeiter']} im Beisein von "
                        f"{p['bauherr_ansprech']}. Grundlage: {rng.choice(['Ausführungszeichnung Index C', 'Bestandsplan', 'Werkplanung'])}.",
                        st["body"]))
    rows = [["Pos.", "Bauteil / Bereich", "Länge (m)", "Breite (m)", "Höhe (m)", "Menge", "Einheit"]]
    for i in range(1, rng.randint(6, 14)):
        l, b, h = (round(rng.uniform(0.5, 24), 2), round(rng.uniform(0.2, 12), 2),
                   round(rng.uniform(0.1, 4.5), 2))
        rows.append([str(i), rng.choice(["Wandfläche EG", "Decke OG 1", "Kabeltrasse Flur", "Außenwand Nord",
                                         "Schacht Technik", "Bodenplatte", "Dachfläche"]),
                     G.num(l), G.num(b), G.num(h), G.num(round(l * b * h, 2)),
                     rng.choice(["m²", "m", "Stk"])])
    el += [tabelle(rows, [10 * mm, 50 * mm, 20 * mm, 20 * mm, 20 * mm, 22 * mm, 18 * mm]), Spacer(1, 8),
           Paragraph("Skizzen und Fotodokumentation sind der Projektakte beigefügt. "
                     "Das Aufmaß wurde gemeinsam festgestellt und anerkannt.", st["small"]),
           Spacer(1, 12),
           Paragraph("Unterschrift Auftragnehmer: ____________________ &nbsp;&nbsp;&nbsp; "
                     "Unterschrift Auftraggeber: ____________________", st["body"])]
    el += fuss(ctx, st)
    return el, {"titel": "Aufmaßprotokoll", "betrag": None}


def d_terminplan(rng, ctx, st):
    p = ctx["projekt"]
    el = kopf(ctx, st, "Terminplan und Meilensteine", mit_adresse=False)
    lauf = (p["ende"] - p["start"]).days
    rows = [["Nr.", "Vorgang", "Start", "Ende", "Dauer", "Status", "Verantwortlich"]]
    vorgaenge = ["Baustelleneinrichtung", "Demontage Bestand", "Leitungsverlegung", "Montage Verteilungen",
                 "Kabelzug und Anschluss", "Inbetriebnahme", "Mängelbeseitigung", "Dokumentation und Abnahme"]
    for i, name in enumerate(vorgaenge[:rng.randint(5, 8)], 1):
        von = rng.randint(0, max(1, lauf - 20))
        bis = von + rng.randint(5, 30)
        status = "erledigt" if bis < (ctx["datum"] - p["start"]).days else rng.choice(["läuft", "offen", "kritisch"])
        rows.append([str(i), name, G.dt(p["start"] + timedelta(days=von)),
                     G.dt(p["start"] + timedelta(days=bis)), f"{bis - von} T", status,
                     rng.choice([p["bauleiter"], p["obermonteur"], "Nachunternehmer"])])
    el += [tabelle(rows, [10 * mm, 48 * mm, 24 * mm, 24 * mm, 16 * mm, 20 * mm, 33 * mm]), Spacer(1, 8),
           Paragraph(f"<b>Kritischer Pfad:</b> {rng.choice(vorgaenge)} &nbsp;\u00b7&nbsp; "
                     f"<b>Terminpuffer:</b> {rng.randint(0, 12)} Tage &nbsp;\u00b7&nbsp; "
                     f"<b>Letzte Fortschreibung:</b> {G.dt(ctx['datum'])}", st["body"])]
    el += fuss(ctx, st)
    return el, {"titel": "Terminplan", "betrag": None}


def d_maengelliste(rng, ctx, st):
    p = ctx["projekt"]
    el = kopf(ctx, st, "Mängelliste", mit_adresse=False)
    rows = [["Nr.", "Ort / Bauteil", "Mangel", "Kategorie", "Frist", "Status"]]
    for i in range(1, rng.randint(4, 12)):
        rows.append([str(i), rng.choice(["EG Flur", "OG 1 Bad", "Technikraum", "Außenanlage", "Dach", "Keller"]),
                     rng.choice(MAENGEL), rng.choice(["gering", "mittel", "erheblich"]),
                     G.dt(ctx["datum"] + timedelta(days=rng.choice([7, 14, 21]))),
                     rng.choice(["offen", "in Arbeit", "beseitigt"])])
    el += [tabelle(rows, [10 * mm, 28 * mm, 62 * mm, 22 * mm, 22 * mm, 22 * mm]), Spacer(1, 8),
           Paragraph(f"Erhebung durch {ctx['bearbeiter']} am {G.dt(ctx['datum'])}. "
                     "Fristen gelten ab Zugang dieser Liste. Nach Ablauf der Frist behält sich "
                     f"{P.SIM_FIRMA[0]} die Nachfristsetzung vor.", st["small"])]
    el += fuss(ctx, st)
    return el, {"titel": "Mängelliste", "betrag": None}


def d_abnahme(rng, ctx, st):
    p = ctx["projekt"]
    el = kopf(ctx, st, "Abnahmeprotokoll", mit_adresse=False)
    el.append(Paragraph(f"<b>Gegenstand:</b> {p['art']} — {p['objekt']} &nbsp;\u00b7&nbsp; "
                        f"<b>Gewerk:</b> {p['gewerk']} &nbsp;\u00b7&nbsp; "
                        f"<b>Abnahmetermin:</b> {G.dt(ctx['datum'])}", st["body"]))
    el.append(Paragraph(f"<b>Anwesend:</b> {p['bauleiter']} (Auftragnehmer), {p['obermonteur']}, "
                        f"{p['bauherr_ansprech']} (Auftraggeber)", st["body"]))
    el.append(Paragraph("<b>Feststellungen</b>", st["h2"]))
    for _ in range(rng.randint(2, 4)):
        el.append(Paragraph(f"\u2022 {rng.choice(P.BRIEF_ABSATZ)}", st["body"]))
    el.append(Paragraph("<b>Vorbehalte und Restpunkte</b>", st["h2"]))
    rows = [["Restpunkt", "Frist", "Kostenübernahme"]]
    for _ in range(rng.randint(1, 4)):
        rows.append([rng.choice(MAENGEL), G.dt(ctx["datum"] + timedelta(days=rng.choice([7, 14, 30]))),
                     rng.choice(["Auftragnehmer", "Auftraggeber", "geteilt"])])
    el += [tabelle(rows, [85 * mm, 40 * mm, 35 * mm]), Spacer(1, 8),
           Paragraph(rng.choice([
               "Die Abnahme erfolgt unter Vorbehalt der Beseitigung der genannten Restpunkte.",
               "Die Leistung wird ohne Vorbehalt abgenommen; die Gewährleistungsfrist beginnt mit heutigem Datum.",
               "Die Abnahme wird wegen der Restpunkte verweigert; ein neuer Termin wird vereinbart."]), st["body"]),
           Spacer(1, 14),
           Paragraph("Auftragnehmer: ____________________ &nbsp;&nbsp;&nbsp; Auftraggeber: "
                     "____________________", st["body"])]
    el += fuss(ctx, st)
    return el, {"titel": "Abnahmeprotokoll", "betrag": None}


def d_behinderung(rng, ctx, st):
    p = ctx["projekt"]
    grund = rng.choice(BEHINDERUNGEN)
    stunden = rng.choice([4, 8, 16, 24, 40])
    mehr = round(stunden * rng.uniform(52, 78), 2)
    el = kopf(ctx, st, "Behinderungsanzeige / Nachtrag", mit_adresse=False)
    el.append(Paragraph(f"<b>Sachverhalt:</b> {grund}. Die Arbeiten im Gewerk {p['gewerk']} konnten "
                        f"im genannten Umfang nicht ausgeführt werden.", st["body"]))
    el.append(Paragraph(f"<b>Auswirkung:</b> Stillstand von {stunden} Stunden; betroffen sind "
                        f"{rng.randint(1, 4)} Mitarbeiter. Auswirkung auf den Terminplan: "
                        f"{rng.randint(1, 10)} Arbeitstage.", st["body"]))
    rows = [["Pos.", "Position", "Menge", "Einheit", "Einzelpreis", "Betrag"]]
    for i in range(1, rng.randint(2, 5)):
        bez, einheit, preis = rng.choice(G.P.DIENSTLEISTUNGEN)
        menge = rng.choice([2, 4, 8, 12, 16])
        rows.append([str(i), bez, G.num(menge), einheit, G.eur(preis), G.eur(round(menge * preis, 2))])
    el += [Spacer(1, 4), tabelle(rows, [10 * mm, 70 * mm, 16 * mm, 16 * mm, 22 * mm, 24 * mm]), Spacer(1, 6),
           Paragraph(f"<b>Mehrkosten netto:</b> {G.eur(mehr)} zzgl. USt. Die Anzeige erfolgt unverzüglich "
                     f"nach Kenntnis; um Bestätigung wird gebeten.", st["body"])]
    el += fuss(ctx, st)
    return el, {"titel": "Behinderungsanzeige", "betrag": mehr}


def d_stunden(rng, ctx, st):
    p = ctx["projekt"]
    el = kopf(ctx, st, "Stundenaufstellung / Nachkalkulation", mit_adresse=False)
    rows = [["Mitarbeiter", "Funktion", "Stunden", "Stundensatz", "Betrag"]]
    summe = 0.0
    for person in p["team"] + [p["obermonteur"]]:
        h = round(rng.uniform(6, 48), 1)
        satz = rng.choice([48.5, 52.0, 58.5, 62.0, 68.5])
        summe += h * satz
        rows.append([person, rng.choice(["Monteur", "Helfer", "Obermonteur"]), G.num(h), G.eur(satz),
                     G.eur(round(h * satz, 2))])
    rows.append(["", "", "", "Summe netto", G.eur(round(summe, 2))])
    soll = round(p["summe"] * 0.32, 2)
    el += [tabelle(rows, [42 * mm, 30 * mm, 22 * mm, 28 * mm, 30 * mm]), Spacer(1, 8),
           Paragraph(f"<b>Kalkulation:</b> geplante Lohnkosten {G.eur(soll)} \u00b7 "
                     f"tatsächlich {G.eur(round(summe, 2))} \u00b7 Abweichung "
                     f"{G.eur(round(summe - soll, 2))} ({'Mehrkosten' if summe > soll else 'Einsparung'})",
                     st["body"]),
           Paragraph(f"Stand {G.dt(ctx['datum'])} · erfasst von {ctx['bearbeiter']}", st["small"])]
    el += fuss(ctx, st)
    return el, {"titel": "Stundenaufstellung", "betrag": round(summe, 2)}


def d_abschlag(rng, ctx, st):
    p = ctx["projekt"]
    anteil = rng.choice([0.15, 0.25, 0.3, 0.4])
    netto = round(p["summe"] * anteil, 2)
    ust = round(netto * 0.19, 2)
    el = kopf(ctx, st, f"Abschlagsrechnung Nr. {rng.randint(1, 4)}", mit_adresse=True)
    el.append(Paragraph(f"<b>Rechnungsnummer:</b> {ctx['rechnr']} &nbsp;\u00b7&nbsp; "
                        f"<b>Projekt:</b> {p['nummer']} &nbsp;\u00b7&nbsp; "
                        f"<b>Leistungsstand:</b> {int(anteil * 100)} %", st["body"]))
    rows = [["Pos.", "Leistung (Projektbezug)", "Anteil", "Betrag"]]
    for i in range(1, rng.randint(3, 6)):
        bez, _, _ = rng.choice(G.P.DIENSTLEISTUNGEN)
        rows.append([str(i), bez, f"{rng.randint(5, 60)} %", G.eur(round(netto / 3, 2))])
    rows += [["", "", "Zwischensumme netto", G.eur(netto)],
             ["", "", "Umsatzsteuer 19 %", G.eur(ust)],
             ["", "", "Rechnungsbetrag", G.eur(round(netto + ust, 2))]]
    el += [tabelle(rows, [12 * mm, 90 * mm, 33 * mm, 30 * mm]), Spacer(1, 6),
           Paragraph(f"Zahlbar innerhalb von {ctx['zahlungsziel']} Tagen ohne Abzug auf das bekannte Konto. "
                     f"Der Leistungsstand wurde am {G.dt(ctx['datum'])} gemeinsam festgestellt.", st["body"])]
    el += fuss(ctx, st)
    return el, {"titel": "Abschlagsrechnung", "betrag": round(netto + ust, 2)}


def d_fotoliste(rng, ctx, st):
    p = ctx["projekt"]
    el = kopf(ctx, st, "Fotodokumentation (Bildliste)", mit_adresse=False)
    rows = [["Nr.", "Datei", "Aufnahme", "Ort / Bereich", "Beschreibung"]]
    for i in range(1, rng.randint(6, 16)):
        rows.append([str(i), f"{G.nrm(p['objekt'])[:14].replace(' ', '_')}_{i:03d}.jpg",
                     G.dt(ctx["datum"] - timedelta(days=rng.randint(0, 30))),
                     rng.choice(["EG Flur", "OG 1", "Technikraum", "Außenwand", "Dach", "Zufahrt"]),
                     rng.choice(["Bestand vor Beginn", "Leitungsweg dokumentiert", "Montage Zustand",
                                 "Schaden festgehalten", "Fortschritt Wochenbericht", "Mangel dokumentiert"])])
    el += [tabelle(rows, [10 * mm, 48 * mm, 24 * mm, 30 * mm, 60 * mm]), Spacer(1, 8),
           Paragraph("Die Bilddateien liegen im Projektordner unter /bilder. Aufnahmen dienen der "
                     "Beweissicherung und dem Baufortschritt.", st["small"])]
    el += fuss(ctx, st)
    return el, {"titel": "Fotodokumentation", "betrag": None}


def d_gefaehrdung(rng, ctx, st):
    p = ctx["projekt"]
    el = kopf(ctx, st, "Gefährdungsbeurteilung / Sicherheitsunterweisung", mit_adresse=False)
    el.append(Paragraph(f"Tätigkeit: {rng.choice(ARBEITEN)} auf der Baustelle {p['objekt']}. "
                        f"Unterweisung am {G.dt(ctx['datum'])} durch {ctx['bearbeiter']}.", st["body"]))
    rows = [["Tätigkeit", "Gefährdung", "Maßnahme", "Restrisiko"]]
    for _ in range(rng.randint(4, 8)):
        rows.append([rng.choice(ARBEITEN),
                     rng.choice(["Stromschlag", "Sturz aus Höhe", "Schnittverletzung", "Staubbelastung",
                                 "Lärm", "Erdreich berühren", "Absturz auf Verkehrsweg"]),
                     rng.choice(["Freischalten und gegen Wiedereinschalten sichern", "PSAgA verwenden",
                                 "Absperrung und Sicherungsposten", "Absaugung nutzen",
                                 "Gehörschutz tragen", "Spannungsfreiheit messen"]),
                     rng.choice(["gering", "mittel", "hoch"])])
    el += [tabelle(rows, [42 * mm, 30 * mm, 65 * mm, 20 * mm]), Spacer(1, 10),
           Paragraph("<b>Teilnahme bestätigt:</b>", st["body"])]
    for person in p["team"]:
        el.append(Paragraph(f"\u2022 {person} — Datum/Unterschrift: ____________________", st["body"]))
    el += fuss(ctx, st)
    return el, {"titel": "Gefährdungsbeurteilung", "betrag": None}


def d_abschluss(rng, ctx, st):
    p = ctx["projekt"]
    el = kopf(ctx, st, "Projektabschlussbericht", mit_adresse=False)
    ist_tage = (p["ende"] - p["start"]).days + rng.randint(-12, 25)
    mehr = round(rng.uniform(-0.06, 0.14) * p["summe"], 2)
    el.append(Paragraph("<b>Zusammenfassung</b>", st["h2"]))
    el.append(Paragraph(f"Das Projekt {p['nummer']} ({p['art']}) wurde im Gewerk {p['gewerk']} für "
                        f"{p['bauherr'][0]} ausgeführt. Die Leistungen umfassten Planung, Montage und "
                        f"Inbetriebnahme gemäß Auftrag.", st["body"]))
    el.append(Paragraph("<b>Termine</b>", st["h2"]))
    el.append(tabelle([["", "Geplant", "Tatsächlich", "Abweichung"],
                       ["Baubeginn", G.dt(p["start"]), G.dt(p["start"] + timedelta(days=rng.randint(-3, 6))), ""],
                       ["Fertigstellung", G.dt(p["ende"]), G.dt(p["start"] + timedelta(days=ist_tage)),
                        f"{ist_tage - (p['ende'] - p['start']).days:+d} Tage"]],
                      [40 * mm, 35 * mm, 35 * mm, 30 * mm]))
    el.append(Paragraph("<b>Kosten</b>", st["h2"]))
    el.append(tabelle([["", "Betrag"],
                       ["Auftragssumme netto", G.eur(p["summe"])],
                       ["Nachträge", G.eur(round(max(0.0, mehr), 2))],
                       ["Endsumme netto", G.eur(round(p["summe"] + max(0.0, mehr), 2))]],
                      [100 * mm, 45 * mm]))
    el.append(Paragraph("<b>Bewertung und Restpunkte</b>", st["h2"]))
    el.append(Paragraph(rng.choice([
        "Das Projekt wurde termingerecht und zur Zufriedenheit des Auftraggebers abgeschlossen.",
        "Trotz terminkritischer Phasen konnte die Fertigstellung im vereinbarten Rahmen erreicht werden.",
        "Die Nachträge resultierten überwiegend aus unvorhergesehenem Bestand und wurden vorab angezeigt."]),
        st["body"]))
    for _ in range(rng.randint(1, 3)):
        el.append(Paragraph(f"\u2022 Offen: {rng.choice(MAENGEL)} — Nachbesserung bis "
                            f"{G.dt(ctx['datum'] + timedelta(days=rng.choice([14, 30, 60])))}", st["body"]))
    el += [Spacer(1, 10), Paragraph(f"Erstellt von {p['bauleiter']} am {G.dt(ctx['datum'])}", st["small"])]
    el += fuss(ctx, st)
    return el, {"titel": "Projektabschlussbericht", "betrag": round(p["summe"] + max(0.0, mehr), 2)}


TYPEN = [
    ("projektuebersicht", 1, d_uebersicht),
    ("projektskizze", 1, d_skizze),
    ("besprechungsnotiz", 4, d_notiz),
    ("bautagebuch", 6, d_bautagebuch),
    ("lieferschein", 4, d_lieferschein),
    ("aufmass", 2, d_aufmass),
    ("terminplan", 1, d_terminplan),
    ("maengelliste", 2, d_maengelliste),
    ("abnahme", 1, d_abnahme),
    ("behinderung", 1, d_behinderung),
    ("stunden", 2, d_stunden),
    ("abschlagsrechnung", 2, d_abschlag),
    ("fotoliste", 2, d_fotoliste),
    ("gefaehrdung", 1, d_gefaehrdung),
    ("abschlussbericht", 1, d_abschluss),
]
TYP_NAMEN = [n for n, _, _ in TYPEN]
TYP_GEWICHTE = [w for _, w, _ in TYPEN]
TYP_FUNCS = {n: f for n, _, f in TYPEN}


def name_fuer(prj, typ, datum, schema=None, nummer=1, gesamt=1):
    if schema:
        return G.make_name(random.Random(1), typ, dokument_ctx(prj, datum, random.Random(1)), nummer,
                           schema.replace("{projekt}", prj["nummer"]), gesamt)
    return f"{prj['nummer']}_{typ}_{datum.strftime('%Y-%m-%d')}.pdf"


def baue_projekt(job):
    """Erzeugt ein Projekt mit allen Dokumenten."""
    idx, seed, outdir, anzahl, schema, versch, flat = job
    rng = random.Random(seed)
    jahr = 2026
    prj = projekt(rng, jahr, rng.randint(1, 9999))
    st = G.basis_styles(rng.choice(["Helvetica", "Helvetica", "Times-Roman"]))
    ordner = outdir if flat else os.path.join(outdir, prj["nummer"])
    os.makedirs(ordner, exist_ok=True)

    # Jedes Projekt hat einen festen Rahmen: Planungspapiere am Anfang, Abnahme und
    # Abschlussbericht am Ende, dazwischen der gewichtete Mix aus dem Projektalltag.
    anfang = ["projektuebersicht", "projektskizze", "terminplan"]
    ende = ["abnahme", "abschlussbericht"]
    mitte_typen = [n for n in TYP_NAMEN[1:-1] if n not in ("abnahme", "abschlussbericht")]
    mitte_gewichte = [w for n, w, _ in TYPEN if n in mitte_typen]
    mitte = [rng.choices(mitte_typen, weights=mitte_gewichte, k=1)[0]
             for _ in range(max(0, anzahl - len(anfang) - len(ende)))]
    typen = (anfang + mitte + ende)[:max(3, anzahl)]
    lauf = max(1, (prj["ende"] - prj["start"]).days)
    termine = [prj["start"] - timedelta(days=rng.randint(10, 25)),
               prj["start"] - timedelta(days=rng.randint(2, 9)),
               prj["start"] + timedelta(days=rng.randint(0, 4))]
    termine += sorted(prj["start"] + timedelta(days=rng.randint(0, lauf))
                      for _ in typen[len(anfang):len(typen) - len(ende)])
    if len(typen) > len(anfang):
        termine += [prj["ende"] - timedelta(days=rng.randint(0, 10)),
                    prj["ende"] + timedelta(days=rng.randint(1, 21))]
    termine = termine[:len(typen)]
    while len(termine) < len(typen):
        termine.append(prj["start"] + timedelta(days=rng.randint(0, lauf)))

    zeilen, fehler, vergeben = [], [], set()
    for i, (typ, datum) in enumerate(zip(typen, termine)):
        absender = rng.choice(G.P.FIRMEN) if typ == "lieferschein" else P.SIM_FIRMA
        ctx = dokument_ctx(prj, datum, rng, absender)
        name = name_fuer(prj, typ, datum, schema, i + 1, len(typen))
        # gleiche Typ/Datum-Kombination kann doppelt vorkommen -> Durchnummerieren statt überschreiben
        stamm, endung = os.path.splitext(name)
        n = 2
        while name.lower() in vergeben:
            name = f"{stamm}_{n}{endung}"
            n += 1
        vergeben.add(name.lower())
        pfad = os.path.join(ordner, name)
        try:
            story, meta = TYP_FUNCS[typ](rng, ctx, st)
            seiten = G.write_pdf(pfad, story, ctx, typ, st, meta["titel"], versch)
        except Exception as exc:  # noqa: BLE001
            fehler.append(f"{name}: {type(exc).__name__}: {exc}")
            continue
        zeilen.append({"datei": name, "typ": typ, "titel": meta["titel"], "datum": G.dt(datum),
                       "verfasser": ctx["bearbeiter"], "betrag": meta["betrag"], "seiten": seiten,
                       "bytes": os.path.getsize(pfad),
                       "verschluesselt": "ja" if versch else ""})
    if zeilen:
        with open(os.path.join(ordner, "_index.csv"), "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(zeilen[0].keys()))
            w.writeheader()
            w.writerows(zeilen)
    return {"projekt": prj["nummer"], "objekt": prj["objekt"], "bauherr": prj["bauherr"][0],
            "art": prj["art"], "ordner": ordner, "dokumente": len(zeilen),
            "summe": prj["summe"], "bytes": sum(z["bytes"] for z in zeilen), "fehler": fehler}


def main():
    ap = argparse.ArgumentParser(description="Projektdokumentationen als PDF erzeugen")
    ap.add_argument("--out", required=True, help="Zielordner (je Projekt ein Unterordner)")
    ap.add_argument("--projekte", type=int, default=1, help="Anzahl Projekte (Standard 1)")
    ap.add_argument("--dokumente", type=int, default=15, help="Dokumente je Projekt (Standard 15)")
    ap.add_argument("--seed", type=int, default=20260927)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--flat", action="store_true", help="ohne Projekt-Unterordner ablegen")
    ap.add_argument("--namensschema", "--naming", dest="namensschema", default=None, metavar="MUSTER",
                    help='Muster für Dateinamen, z. B. "{projekt}_{typ}_{datum}.pdf"')
    ap.add_argument("--verschluesseln", "--encrypt", dest="verschluesseln", default=None, metavar="PASSWORT")
    ap.add_argument("--verschluesseln-owner", dest="verschluesseln_owner", default=None)
    ap.add_argument("--verschluesseln-rechte", dest="verschluesseln_rechte", default="drucken",
                    choices=["drucken", "alles", "nichts"])
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    versch = G.verschluesselung(a.verschluesseln, a.verschluesseln_owner, a.verschluesseln_rechte)
    os.makedirs(a.out, exist_ok=True)
    rng = random.Random(a.seed)
    jobs = [(i, rng.randint(1, 2 ** 31 - 1), a.out, a.dokumente, a.namensschema, versch, a.flat)
            for i in range(a.projekte)]

    t0 = time.time()
    ergebnisse = []
    if a.jobs > 1 and len(jobs) > 1:
        with Pool(min(a.jobs, len(jobs))) as pool:
            for erg in pool.imap_unordered(baue_projekt, jobs):
                ergebnisse.append(erg)
                if not a.quiet:
                    print(f"  fertig: {erg['projekt']} ({erg['dokumente']} Dokumente)", flush=True)
    else:
        for job in jobs:
            ergebnisse.append(baue_projekt(job))
            if not a.quiet:
                print(f"  fertig: {ergebnisse[-1]['projekt']} ({ergebnisse[-1]['dokumente']} Dokumente)",
                      flush=True)

    ergebnisse.sort(key=lambda e: e["projekt"])
    gesamt = sum(e["dokumente"] for e in ergebnisse)
    fehler = [f for e in ergebnisse for f in e["fehler"]]
    print(f"\n{len(ergebnisse)} Projekt(e) mit {gesamt} Dokumenten in {a.out} "
          f"({time.time()-t0:.1f}s, Fehler {len(fehler)})")
    for e in ergebnisse:
        print(f"  {e['projekt']}")
        print(f"     {e['art']} · {e['objekt']} · Bauherr {e['bauherr']} · "
              f"{e['dokumente']} Dokumente · {e['bytes']/1024:.0f} KB · {os.path.relpath(e['ordner'], a.out)}")
    for f in fehler[:10]:
        print("  FEHLER:", f)
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())