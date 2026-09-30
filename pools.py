# -*- coding: utf-8 -*-
"""Datenpools für realistische deutsche Fake-Dokumente (kein Personenbezug, alles fiktiv)."""

FIRMEN = [
    ("Nordlicht Elektrotechnik GmbH", "Elektrotechnik", "Hafenstraße 14", "24103", "Kiel", "0431 55 91 20", "info@nordlicht-et.de"),
    ("Bäckerei Sonnenschein e.K.", "Bäckerei", "Rosenweg 3", "79098", "Freiburg", "0761 22 18 40", "kontakt@baeckerei-sonnenschein.de"),
    ("Müller & Söhne Spedition GmbH", "Spedition", "Industriepark 27", "90402", "Nürnberg", "0911 44 87 65", "dispo@mueller-soehne.de"),
    ("Hausverwaltung Lehmann KG", "Immobilien", "Kaiserstraße 88", "60313", "Frankfurt am Main", "069 13 55 02", "service@hv-lehmann.de"),
    ("Stadtwerke Grünberg AöR", "Versorger", "Marktplatz 1", "35390", "Gießen", "0641 8 82 20", "kundenservice@sw-gruenberg.de"),
    ("Zahnarztpraxis Dr. Nowak & Kollegen", "Praxis", "Lindenallee 42", "20095", "Hamburg", "040 33 21 77", "praxis@dr-nowak-dental.de"),
    ("Bürobedarf Kessler GmbH", "Handel", "Gewerbepark 9", "04103", "Leipzig", "0341 90 44 10", "bestellung@kessler-office.de"),
    ("Sonnentaler Landtechnik e.K.", "Landtechnik", "Feldweg 6", "84347", "Pfarrkirchen", "08561 9 13 40", "werkstatt@sonnentaler-lt.de"),
    ("IT-Systemhaus Ravenstein GmbH", "IT", "Technologieallee 5", "76131", "Karlsruhe", "0721 47 90 33", "support@ravenstein-it.de"),
    ("Schreinerei Holzapfel GmbH & Co. KG", "Handwerk", "Am Sägewerk 11", "86150", "Augsburg", "0821 55 62 08", "info@holzapfel-schreinerei.de"),
    ("Autohaus Wolkenstein GmbH", "Kfz", "Ringstraße 120", "44135", "Dortmund", "0231 77 41 09", "service@wolkenstein-auto.de"),
    ("Reinigungsservice Blank & Partner", "Gebäudereinigung", "Südring 34", "28195", "Bremen", "0421 33 90 11", "objekte@blank-partner.de"),
    ("Getränkegroßhandel Dornfelder GmbH", "Großhandel", "Depotstraße 2", "55116", "Mainz", "06131 22 90 55", "auftrag@dornfelder-getraenke.de"),
    ("Physiotherapie am Stadtpark", "Praxis", "Parkstraße 19", "14467", "Potsdam", "0331 70 12 88", "termin@physio-stadtpark.de"),
    ("Werbeagentur Blaufuchs GmbH", "Agentur", "Kreativquartier 8", "50667", "Köln", "0221 91 20 34", "projekt@blaufuchs-werbe.de"),
    ("Chemikalien Voigtländer GmbH", "Chemie", "Industriestraße 55", "67059", "Ludwigshafen", "0621 44 12 90", "bestellung@voigtlaender-chem.de"),
    ("Garten- und Landschaftsbau Bertram", "GaLaBau", "Wiesenweg 21", "99084", "Erfurt", "0361 22 44 09", "info@galabau-bertram.de"),
    ("Medizintechnik Pfeiffersberg AG", "Medizintechnik", "Forschungsring 3", "52062", "Aachen", "0241 88 12 44", "sales@pfeiffersberg-med.de"),
    ("Druckerei Buchheim KG", "Druckerei", "Papiergasse 7", "01067", "Dresden", "0351 44 90 21", "auftrag@druckerei-buchheim.de"),
    ("Rechtsanwälte Hartung & Wiese", "Kanzlei", "Justizplatz 4", "70173", "Stuttgart", "0711 20 55 90", "kanzlei@hartung-wiese.de"),
    ("Elektro Ostrand GmbH", "Elektro", "Greifswalder Straße 88", "17489", "Greifswald", "03834 55 12 90", "info@elektro-ostrand.de"),
    ("Kfz-Werkstatt Grubmüller", "Kfz", "Zur Alten Mühle 2", "94032", "Passau", "0851 33 90 77", "werkstatt@grubmueller-kfz.de"),
    ("Textilpflege Wunderlich GmbH", "Wäscherei", "Waschstraße 8", "58095", "Hagen", "02331 22 40 19", "annahme@wunderlich-textil.de"),
    ("Tischlerei & Innenausbau Sommer", "Tischlerei", "Feldmark 15", "38100", "Braunschweig", "0531 70 90 33", "werkstatt@tischlerei-sommer.de"),
    ("Versicherungsmakler Kranich & Co.", "Versicherung", "Kontorhaus 6", "20354", "Hamburg", "040 35 90 12", "service@kranich-makler.de"),
    ("Maschinenbau Schwarzwald AG", "Maschinenbau", "Werkstraße 100", "78056", "Villingen-Schwenningen", "07720 60 12 90", "einkauf@mb-schwarzwald.de"),
    ("Sanitär & Heizung Kirchner GmbH", "SHK", "Kupferschmiedweg 3", "96047", "Bamberg", "0951 33 12 44", "service@kirchner-shk.de"),
    ("Fernseh- & Radiohaus Auerbach", "Elektrohandel", "Ladengasse 12", "34117", "Kassel", "0561 44 90 02", "verkauf@auerbach-tv.de"),
    ("Logistik Center Rotbach GmbH", "Logistik", "Am Umschlagplatz 40", "47051", "Duisburg", "0203 55 12 90", "lager@rotbach-logistik.de"),
    ("Baustoffe Ellenbogen KG", "Baustoffe", "Kiesgrube 1", "56068", "Koblenz", "0261 33 90 44", "verkauf@ellenbogen-baustoffe.de"),
]

KUNDEN_PERSONEN = [
    ("Andreas Kirchner", "Bergstraße"), ("Sabine Wolf", "Gartenweg"), ("Thomas Brandner", "Schulstraße"),
    ("Petra Lindqvist", "Ahornweg"), ("Michael Ostermann", "Kirchplatz"), ("Julia Behrens", "Uferstraße"),
    ("Stefan Grasmück", "Birkenallee"), ("Kerstin Adler", "Am Sportplatz"), ("Ralf Kienzler", "Talstraße"),
    ("Nadine Voß", "Mühlenweg"), ("Holger Zeitler", "Waldstraße"), ("Simone Rademacher", "Lindenweg"),
    ("Frank Ostermann", "Feldstraße"), ("Ulrike Steinbrenner", "Sonnenhang"), ("Matthias Grunewald", "Eichenweg"),
    ("Claudia Rehm", "Rosenstraße"), ("Bernd Neuhäuser", "Bachgasse"), ("Anja Kowalczyk", "Hauptstraße"),
    ("Oliver Schwandt", "Erlenweg"), ("Martina Preißler", "Am Weiher"),
]
KUNDEN_FIRMEN = [
    ("Stadtverwaltung Mühlbach", "Rathausplatz 1", "84453", "Mühlbach"),
    ("Kath. Kirchengemeinde St. Kilian", "Kirchenstraße 4", "97421", "Schweinfurt"),
    ("Wohnbaugenossenschaft Adlerhorst eG", "Genossenschaftsweg 22", "39104", "Magdeburg"),
    ("Grundschule Am Lindenhof", "Schulweg 9", "36037", "Fulda"),
    ("Sportverein Blau-Weiß Talheim e.V.", "Vereinsstraße 18", "74072", "Heilbronn"),
    ("Pflegeheim Sonnenhof gGmbH", "Seniorenweg 5", "63450", "Hanau"),
    ("Autoteile Großmann GmbH", "Ersatzteilstraße 30", "45879", "Gelsenkirchen"),
    ("Pension Zur Linde", "Gaststättenweg 2", "82467", "Garmisch-Partenkirchen"),
    ("Fitnessstudio PulsePoint GmbH", "Trainingsplatz 7", "44263", "Dortmund"),
    ("Immobilien Küstenblick GmbH", "Strandpromenade 14", "18209", "Bad Doberan"),
    ("Metallbau Wetterau GmbH", "Werkstattring 12", "61169", "Friedberg"),
    ("Biolandhof Rauschenbach", "Hofweg 3", "34613", "Schwalmstadt"),
]

# Institutionen, Behörden, Banken und Versicherer, die einer Firma Post schicken
INSTITUTIONEN = [
    ("Finanzamt Rostock", "Behörde", "Steuerstraße 3", "18057", "Rostock", "0381 44 12 90", "poststelle@fa-rostock.de"),
    ("Handwerkskammer Ostmecklenburg", "Kammer", "Alter Markt 8", "18055", "Rostock", "0381 45 90 10", "info@hwk-ost.de"),
    ("Berufsgenossenschaft BGHM", "BG", "Prüfweg 12", "44805", "Bochum", "0234 33 90 12", "service@bghm.de"),
    ("IHK zu Rostock", "Kammer", "Ernst-Barlach-Straße 1", "18055", "Rostock", "0381 33 88 20", "service@ihk-rostock.de"),
    ("Sparkasse Vorpommern", "Bank", "Kröpeliner Straße 22", "18055", "Rostock", "0381 22 90 00", "beratung@spk-vorpommern.de"),
    ("Deutsche Rentenversicherung Nord", "Behörde", "Ziegelstraße 15", "23556", "Lübeck", "0451 44 90 11", "post@drv-nord.de"),
    ("Agentur für Arbeit Rostock", "Behörde", "Kopernikusstraße 5", "18057", "Rostock", "0381 44 90 55", "rostock@arbeitsagentur.de"),
    ("Steuerkanzlei Wendt & Kollegen", "Steuerberatung", "Am Vögenteich 14", "18055", "Rostock", "0381 70 12 33", "kanzlei@wendt-steuer.de"),
    ("Kfz-Zulassungsstelle Rostock", "Behörde", "Holbeinplatz 11", "18055", "Rostock", "0381 45 12 88", "zulassung@rostock.de"),
    ("Gothaer Versicherung AG", "Versicherung", "Gothaer Allee 1", "50969", "Köln", "0221 30 80 12", "service@gothaer.de"),
    ("Amtsgericht Rostock", "Gericht", "Zochstraße 13", "18055", "Rostock", "0381 44 90 99", "poststelle@ag-rostock.de"),
    ("Zollamt Rostock", "Behörde", "Hafenstraße 41", "18055", "Rostock", "0381 33 12 90", "zollamt-rostock@zoll.de"),
]

# Die simulierte Firma: Empfängerin aller Eingangsdokumente
SIM_FIRMA = ("Vollmer Elektrotechnik GmbH", "Elektrohandwerk", "Bahnhofstraße 61", "18055", "Rostock",
             "0381 45 90 12", "info@vollmer-elektro.de")

STRASSEN = ["Hauptstraße", "Bahnhofstraße", "Lindenweg", "Am Anger", "Gartenstraße", "Schulstraße",
            "Ringstraße", "Mühlenweg", "Feldstraße", "Birkenweg", "Talstraße", "Wiesenweg",
            "Industriestraße", "Am Hafen", "Kirchgasse", "Blumenstraße", "Poststraße", "Ahornweg"]

ARTIKEL = [
    ("Schraubendreher-Set 12-tlg.", "Stk", 12.90), ("Kupferkabel NYM-J 3x1,5", "m", 1.45),
    ("Arbeitshandschuhe Gr. 10", "Paar", 4.75), ("LED-Leuchtmittel 4000K 9W", "Stk", 6.20),
    ("Schleifpapier K120", "Bogen", 0.85), ("Kabelbinder 200mm", "Pkt", 3.40),
    ("Hydrauliköl HLP 46", "l", 4.10), ("Bohrersatz HSS 19-tlg.", "Set", 34.50),
    ("Handwaschpaste 3l", "Stk", 11.90), ("Warnweste EN ISO 20471", "Stk", 8.30),
    ("Batterie AA Alkaline", "Pkt", 5.60), ("Schutzbrille klar", "Stk", 7.15),
    ("Klebeband Paketband 50m", "Rolle", 2.30), ("Ersatzfilter für Absauganlage", "Stk", 48.00),
    ("Werbeplakette Fenster", "Stk", 22.00), ("Ordner A4 breit", "Stk", 3.95),
    ("Mehl Type 550 25kg", "Sack", 24.50), ("Hefe frisch 500g", "Stk", 2.10),
    ("Kaffee Bohnen Espresso 1kg", "kg", 14.80), ("Mineralwasser 12x0,75l", "Kasten", 7.90),
]
DIENSTLEISTUNGEN = [
    ("Wartung und Inspektion nach DGUV V3", "Std", 78.50),
    ("Montage vor Ort", "Std", 62.00),
    ("Anfahrt und Rüstzeit", "Pauschale", 89.00),
    ("Erstellung Wartungsprotokoll", "Pauschale", 45.00),
    ("Reparatur Steuerungseinheit", "Std", 96.00),
    ("Objektbetreuung Unterhaltsreinigung", "Std", 32.50),
    ("Fensterreinigung Glasfassade", "m²", 3.20),
    ("Transportleistung bis 20 km", "km", 1.85),
    ("Entsorgung von Bauschutt", "t", 145.00),
    ("Supportstunde nach Aufwand", "Std", 110.00),
    ("Jahreslizenz Softwaremodul", "Lizenz", 480.00),
    ("Fortbildung Tagespauschale", "Tag", 690.00),
    ("Beratungsleistung projektbezogen", "Std", 125.00),
    ("Druckleistung Digitaldruck A4 4/4", "Stk", 0.28),
    ("Verteilung Flyer im Zielgebiet", "Stk", 0.06),
    ("Leihgerät für die Übergangszeit", "Tag", 18.50),
]

BETREFFZEILEN = [
    "Ihre Anfrage vom {d} — Angebot über Ersatzbeschaffung",
    "Bestellung {nr} — Auftragsbestätigung",
    "Rückfrage zu Liefertermin {nr}",
    "Ihr Schreiben vom {d}",
    "Rechnungsprüfung {nr} — Klärung der Position 4",
    "Terminabsprache für die Jahresunterweisung",
    "Mängelanzeige nach Abnahme {nr}",
    "Übersendung der vertragsrelevanten Unterlagen",
    "Kündigung des Wartungsvertrages zum Jahresende",
    "Angebotsnachverfolgung — technische Klärung",
    "Vorschlag zur Terminverschiebung der Lieferung",
    "Datenschutzinformation nach Art. 13 DSGVO",
    "Erinnerung an die Nachreichung der Rechnung {nr}",
    "Ihre Lieferung vom {d} — Transportschaden",
]

BRIEF_ABSATZ = [
    "vielen Dank für Ihre Nachricht und die damit verbundenen Informationen. Wir haben den Sachverhalt aufgenommen und die zuständigen Stellen informiert.",
    "nach Durchsicht der Unterlagen können wir den Vorgang in weiten Teilen nachvollziehen. Für zwei Positionen besteht jedoch weiterhin Klärungsbedarf, den wir im Folgenden darstellen.",
    "gerne bestätigen wir Ihnen, dass der genannte Termin von unserer Seite gehalten werden kann. Sollten sich Änderungen ergeben, melden wir uns rechtzeitig vorab.",
    "wir bitten um Ihr Verständnis, dass die Bearbeitung aufgrund der aktuellen Auftragslage einige Tage in Anspruch nehmen kann. Selbstverständlich halten wir Sie über jeden Zwischenstand informiert.",
    "die Maßnahme wurde am genannten Tag vollständig ausgeführt und von der verantwortlichen Person abgenommen. Das Protokoll liegt dieser Nachricht bei.",
    "leider müssen wir Ihnen mitteilen, dass wir den gewünschten Liefertermin nicht halten können. Als Alternative schlagen wir die in der Anlage genannte Woche vor.",
    "für Rückfragen stehen wir Ihnen selbstverständlich jederzeit gerne zur Verfügung. Wir danken Ihnen für die vertrauensvolle Zusammenarbeit.",
    "wir weisen vorsorglich darauf hin, dass die vereinbarte Zahlungsfrist in wenigen Tagen abläuft. Bei bereits erfolgter Überweisung bitten wir Sie, dieses Schreiben als gegenstandslos zu betrachten.",
    "nach Rücksprache mit den Kolleginnen und Kollegen vor Ort können wir Ihnen folgende Lösung anbieten, die für beide Seiten tragfähig sein dürfte.",
    "wir bedauern die entstandenen Unannehmlichkeiten und versichern Ihnen, dass die internen Abläufe entsprechend angepasst wurden, um dies künftig zu vermeiden.",
]
VERTRAG_ABSATZ = [
    "Der Auftragnehmer verpflichtet sich, die vereinbarten Leistungen nach den anerkannten Regeln der Technik, den einschlägigen gesetzlichen Vorschriften sowie den schriftlich fixierten Vorgaben des Auftraggebers zu erbringen.",
    "Änderungen oder Ergänzungen dieses Vertrages bedürfen der Schriftform. Dies gilt auch für die Aufhebung dieser Klausel. Mündliche Nebenabreden bestehen nicht.",
    "Die Vergütung erfolgt auf Grundlage der vereinbarten Preise zuzüglich der gesetzlichen Umsatzsteuer. Reisekosten werden nur nach vorheriger schriftlicher Zustimmung vergütet.",
    "Der Auftraggeber ist berechtigt, die Leistungen während der Ausführung angemessen kontrollieren zu lassen, sofern hierdurch der Betriebsablauf des Auftragnehmers nicht unverhältnismäßig beeinträchtigt wird.",
    "Befindet sich der Auftraggeber mit fälligen Zahlungen in Verzug, ist der Auftragnehmer berechtigt, die weitere Ausführung der Leistungen nach vorheriger Ankündigung einzustellen.",
    "Die Parteien verpflichten sich zur Vertraulichkeit über alle betrieblichen und technischen Informationen, die im Rahmen der Zusammenarbeit bekannt werden, auch über die Laufzeit hinaus.",
    "Ansprüche wegen Sach- und Rechtsmängeln sind gemäß den gesetzlichen Bestimmungen innerhalb der vereinbarten Verjährungsfrist geltend zu machen.",
    "Erfüllungsort und Gerichtsstand ist, soweit gesetzlich zulässig, der Sitz des Auftragnehmers. Es gilt ausschließlich deutsches Recht unter Ausschluss des UN-Kaufrechts.",
    "Die Haftung für leichte Fahrlässigkeit wird auf die vertragstypischen, vorhersehbaren Schäden begrenzt. Die Haftung nach dem Produkthaftungsgesetz bleibt unberührt.",
    "Der Auftragnehmer wird für die Dauer des Einsatzes eine Betriebshaftpflichtversicherung mit einer Deckungssumme von mindestens 3.000.000 € unterhalten und auf Verlangen nachweisen.",
    "Beide Parteien benennen jeweils eine Ansprechperson für die Abwicklung des Vertragsverhältnisses. Wechsel werden unverzüglich schriftlich mitgeteilt.",
    "Nach Abnahme ist die Leistung vom Auftraggeber zu vergüten, soweit keine berechtigten Mängelrügen vorliegen. Eine Abnahme gilt als erteilt, wenn nicht innerhalb von zwölf Werktagen begründete Einwände erhoben werden.",
    "Personenbezogene Daten werden ausschließlich zur Vertragsdurchführung verarbeitet und nach Ablauf der gesetzlichen Aufbewahrungsfristen gelöscht.",
    "Für Wartungsarbeiten gilt eine Reaktionszeit von achtundvierzig Stunden nach Meldung. Wochenenden und Feiertage bleiben dabei unberücksichtigt.",
]
FORMULAR_FELDER = [
    ("Personalnummer", "PersNr"), ("Kostenstelle", "KST"), ("Nachname, Vorname", "Name"),
    ("Abteilung", "Abt"), ("Eintrittsdatum", "Datum"), ("Vorgesetzte Person", "Vorgesetzter"),
    ("Art der Maßnahme", "Maßnahme"), ("Kontonummer / IBAN", "IBAN"), ("Zahlungsgrund", "Zweck"),
    ("Betrag in EUR", "Betrag"), ("Beleg-Nr.", "Beleg"), ("Unterschrift Antragsteller", "Unterschrift"),
]
RUNDSCHREIBEN_THEMEN = [
    "Neue Öffnungszeiten der Annahme ab dem kommenden Monat",
    "Betriebsausflug — Anmeldung bis Ende der Woche",
    "Umstellung auf das neue Zeiterfassungssystem",
    "Inventur: Ablauf und Ansprechpersonen",
    "Geänderte Zuständigkeiten im Einkauf",
    "Hinweise zum Arbeitsschutz in den Sommermonaten",
    "Weihnachtsfeier und Jahresabschlussbesprechung",
    "Einführung eines Ticketsystems für interne Anfragen",
]
ABTEILUNGEN = ["Einkauf", "Verkauf", "Produktion", "Buchhaltung", "Lager", "Technik", "Personal",
               "Vertrieb Innendienst", "Qualitätssicherung", "Fuhrpark"]
BANKEN = [("Sparkasse Vorpommern", "NOLADE21xxx"), ("Volksbank Rhein-Neckar eG", "GENODE61xxx"),
          ("Commerzbank Filiale Nord", "COBADEFFxxx"), ("Deutsche Bank PGK", "DEUTDEFFxxx"),
          ("Postbank Hamburg", "PBNKDEFFxxx")]
ARTIKEL_KURZ = ["Büromaterial", "Werkzeug", "Reinigungsmittel", "Ersatzteile", "Verbrauchsmaterial",
                "Getränke", "Arbeitskleidung", "Elektromaterial", "Papierwaren", "Sanitärbedarf"]


def iban(rng):
    return "DE" + str(rng.randint(10, 99)) + " " + " ".join(
        str(rng.randint(1000, 9999)) for _ in range(4)) + " " + str(rng.randint(10, 99))


def plz(rng):
    return str(rng.randint(10000, 99999))


def telefon(rng):
    return f"0{rng.randint(200, 999)} {rng.randint(10, 99)} {rng.randint(10, 99)} {rng.randint(10, 99)}"


def ust_id(rng):
    return "DE" + str(rng.randint(100000000, 999999999))

import zlib as _zlib


def _norm(t):
    """Verkürzte Adresstupel deterministisch auf das 7er-Format der FIRMEN bringen."""
    if len(t) == 7:
        return t
    name, strasse, plz, ort = t
    c = _zlib.crc32(name.encode("utf-8"))
    tel = f"0{200 + c % 800} {10 + c % 89} {10 + (c // 7) % 89} {10 + (c // 13) % 89}"
    mail = ("info@" + "".join(ch for ch in name.lower().replace("\u00e4", "ae").replace("\u00f6", "oe")
                              .replace("\u00fc", "ue").replace("\u00df", "ss") if ch.isalnum())[:18] + ".de")
    return (name, "Kunde", strasse, plz, ort, tel, mail)


KUNDEN_FIRMEN = [_norm(t) for t in KUNDEN_FIRMEN]
