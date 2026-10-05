# -*- coding: utf-8 -*-
"""Leitstand: kleine lokale Oberfläche für gen.py / mail.py / check.py / testrun.py.

    python panel.py                 # startet http://127.0.0.1:8765 und öffnet den Browser
    python panel.py --port 9000 --no-browser
    python panel.py --selftest      # Smoke-Test ohne Oberfläche (für CI)

Der Server läuft nur auf 127.0.0.1 und führt ausschließlich fest verdrahtete Kommandos aus
(keine Shell, keine freien Befehle): Aktionen werden als Argumentlisten zusammengesetzt,
Zahlenwerte geprüft, Pfade auf Steuerzeichen getestet.
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

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HIER = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
# Vorbelegung für alle Aktionen (per --ziel änderbar)
STANDARD_ZIEL = r"\\hellfire\PDF-TEst\test\TestEingang"

zustand = {
    "prozess": None,
    "aktion": None,
    "parameter": {},
    "start": None,
    "ende": None,
    "exit": None,
    "zeilen": deque(maxlen=3000),
    "historie": deque(maxlen=25),
}
sperre = threading.Lock()


# ------------------------------------------------------------------ Hilfsfunktionen
def zahl(wert, name, klein, gross, standard):
    if wert in (None, ""):
        return standard
    try:
        n = int(str(wert).strip())
    except ValueError:
        raise ValueError(f"{name}: bitte eine ganze Zahl angeben (erhalten: {wert!r})")
    if not klein <= n <= gross:
        raise ValueError(f"{name}: erlaubt sind {klein} bis {gross} (erhalten: {n})")
    return n


def pfad(wert, name, standard=None, muss_existieren=False):
    p = (wert or standard or "").strip().strip('"')
    if not p:
        raise ValueError(f"{name}: bitte einen Pfad angeben")
    if any(c in p for c in "\r\n\t\0"):
        raise ValueError(f"{name}: unzulässige Zeichen im Pfad")
    if muss_existieren and not os.path.isdir(p):
        raise ValueError(f"{name}: Ordner existiert nicht: {p}")
    return p


def auswahl(wert, name, erlaubt, standard=None):
    w = (wert or standard or "").strip()
    if w not in erlaubt:
        raise ValueError(f"{name}: erlaubt sind {', '.join(erlaubt)}")
    return w


def flag(wert):
    return str(wert).lower() in ("1", "true", "ja", "yes", "on", "an")


def zaehle(ordner):
    pdf = eml = unterordner = 0
    for dp, dirs, dateien in os.walk(ordner):
        if dp == ordner:
            unterordner = len(dirs)
        for f in dateien:
            if f.lower().endswith(".pdf"):
                pdf += 1
            elif f.lower().endswith(".eml"):
                eml += 1
    return {"pdf": pdf, "eml": eml, "unterordner": unterordner}


def mail_config():
    """Zeigt die wirksame mail.env-Konfiguration — Passwort nur als gesetzt/nicht gesetzt."""
    werte, quelle = {}, None
    for name in ("mail.env",):
        p = os.path.join(HIER, name)
        if os.path.exists(p):
            quelle = p
            for zeile in open(p, encoding="utf-8"):
                zeile = zeile.strip()
                if zeile and not zeile.startswith("#") and "=" in zeile:
                    k, v = zeile.split("=", 1)
                    k, v = k.strip(), v.strip()
                    werte[k] = ("•••••• (gesetzt)" if k.endswith("PASS") and v else v)
    return {"quelle": quelle, "werte": werte}


# ---------------------------------------------------------------------- Aktionen
def a_dateien(p):
    ziel = pfad(p.get("ordner"), "Zielordner", STANDARD_ZIEL)
    count = zahl(p.get("count"), "Anzahl", 1, 200000, 100)
    index_im_ziel = flag(p.get("index"))
    seed = zahl(p.get("seed"), "Seed", 0, 2 ** 31 - 1, 20260927)
    jobs = zahl(p.get("jobs"), "Parallelprozesse", 1, 64, max(1, (os.cpu_count() or 4) - 2))
    layout = auswahl(p.get("layout"), "Ablage", ["monat", "flach"], "monat")
    datum = auswahl(p.get("datum"), "Dokumentdatum", ["zeitraum", "heute"], "zeitraum")
    os.makedirs(ziel, exist_ok=True)
    argv = [PY, "gen.py", "--out", ziel, "--count", str(count), "--seed", str(seed), "--jobs", str(jobs)]
    if layout == "flach":
        argv.append("--flat")
    if datum == "heute":
        argv.append("--document-today")
    # Index liegt standardmäßig NICHT im Zielordner, damit überwachte Eingangsordner sauber bleiben
    if index_im_ziel:
        index_pfad = None
    else:
        index_ordner = os.path.join(HIER, "index")
        os.makedirs(index_ordner, exist_ok=True)
        index_pfad = os.path.join(index_ordner, f"lauf_{time.strftime('%Y%m%d_%H%M%S')}.csv")
    if index_pfad:
        argv += ["--index", index_pfad]
    schema = (p.get("schema") or "").strip()
    if schema:
        argv += ["--namensschema", schema]
    if flag(p.get("ver")):
        pw = (p.get("pw") or "").strip()
        if not pw:
            raise ValueError("Verschlüsselung: bitte ein Passwort angeben")
        argv += ["--verschluesseln", pw,
                 "--verschluesseln-rechte", auswahl(p.get("rechte"), "Rechte",
                                                    ["drucken", "alles", "nichts"], "drucken")]
    return argv, (f"{count} PDFs nach {ziel} ({layout}, {datum}"
                  + (f", Namen nach '{schema}'" if schema else "")
                  + (", verschlüsselt" if flag(p.get("ver")) else "")
                  + (", Index im Zielordner" if index_im_ziel else f", Index: {index_pfad}") + ")")


def a_pruefen(p):
    ziel = pfad(p.get("ordner"), "Ordner", STANDARD_ZIEL, muss_existieren=True)
    argv = [PY, "check.py", ziel]
    pw = (p.get("pw") or "").strip()
    if pw:
        argv += ["--passwort", pw]
    return argv, f"Bestand prüfen: {ziel}" + (" (mit Passwort für verschlüsselte PDFs)" if pw else "")


def a_mails(p):
    count = zahl(p.get("count"), "Anzahl", 1, 5000, 5)
    seed = zahl(p.get("seed"), "Seed", 0, 2 ** 31 - 1, 20260927)
    transport = auswahl(p.get("transport"), "Transport", ["file", "sink", "smtp"], "file")
    datum = auswahl(p.get("datum"), "Datum im Mail-Kopf", ["jetzt", "dokument"], "jetzt")
    ziel = pfad(p.get("mailordner"), "Ablage", os.path.join(HIER, "mails")) if transport != "smtp" else None
    argv = [PY, "mail.py", "--count", str(count), "--seed", str(seed), "--transport", transport]
    if ziel:
        argv += ["--mail-dir", ziel]
    if flag(p.get("dokument_heute")):
        argv.append("--document-today")
    if datum == "dokument":
        argv.append("--date-from-document")
    if flag(p.get("ver")):
        pw = (p.get("pw") or "").strip()
        if not pw:
            raise ValueError("Verschlüsselung: bitte ein Passwort angeben")
        argv += ["--verschluesseln", pw,
                 "--verschluesseln-rechte", auswahl(p.get("rechte"), "Rechte",
                                                    ["drucken", "alles", "nichts"], "drucken")]
    if transport == "smtp" and flag(p.get("verify_imap")):
        argv.append("--verify-imap")
    return argv, (f"{count} Mails über '{transport}' ({datum}"
                  + (", Dokument heute" if flag(p.get("dokument_heute")) else "")
                  + (", Anhang verschlüsselt" if flag(p.get("ver")) else "") + ")")


def a_mail_check(p):
    was = auswahl(p.get("was"), "Prüfung", ["anmeldung", "empfaenger"], "anmeldung")
    if was == "anmeldung":
        return [PY, "mail.py", "--check-connection"], "SMTP-Anmeldung prüfen (sendet nichts)"
    return [PY, "mail.py", "--check-recipient"], "Empfängeradresse prüfen (sendet nichts)"


def a_postfach(p):
    anzahl = zahl(p.get("anzahl"), "Anzahl Mails", 1, 200, 10)
    return [PY, "mail.py", "--imap-list", str(anzahl)], f"{anzahl} neueste Mails im Postfach ansehen"


def a_sink(p):
    sekunden = zahl(p.get("sekunden"), "Laufzeit", 0, 86400, 300)
    ziel = pfad(p.get("mailordner"), "Ablage", os.path.join(HIER, "mails"))
    argv = [PY, "mail.py", "--serve", "--mail-dir", ziel]
    if sekunden:
        argv += ["--serve-seconds", str(sekunden)]
    return argv, f"SMTP-Testserver auf 127.0.0.1:{os.environ.get('MAIL_SINK_PORT', 8026)} ({'dauerhaft' if not sekunden else str(sekunden) + ' s'})"


def a_testlauf(p):
    argv = [PY, "testrun.py"]
    ziel = (p.get("ordner") or "").strip()
    if ziel:
        argv += ["--out", pfad(ziel, "Arbeitsordner")]
    if flag(p.get("live")):
        argv.append("--live")
    if flag(p.get("keep")):
        argv.append("--keep")
    return argv, f"Kompletter Testlauf{' inkl. echter Testmail' if flag(p.get('live')) else ' ohne echten Versand'}"


def a_projekt(p):
    ziel = pfad(p.get("ordner"), "Zielordner", STANDARD_ZIEL)
    projekte = zahl(p.get("projekte"), "Anzahl Projekte", 1, 200, 1)
    dokumente = zahl(p.get("dokumente"), "Dokumente je Projekt", 3, 200, 15)
    seed = zahl(p.get("seed"), "Seed", 0, 2 ** 31 - 1, 20260927)
    jobs = zahl(p.get("jobs"), "Parallelprozesse", 1, 64, max(1, (os.cpu_count() or 4) - 2))
    os.makedirs(ziel, exist_ok=True)
    argv = [PY, "projekt.py", "--out", ziel, "--projekte", str(projekte), "--dokumente", str(dokumente),
            "--seed", str(seed), "--jobs", str(jobs)]
    if flag(p.get("flat")):
        argv.append("--flat")
    schema = (p.get("schema") or "").strip()
    if schema:
        argv += ["--namensschema", schema]
    if flag(p.get("index")):
        argv.append("--mit-projekt-index")
    else:
        # Index außerhalb der Projektordner halten, damit Testordner sauber bleiben
        index_ordner = os.path.join(HIER, "index")
        os.makedirs(index_ordner, exist_ok=True)
        argv += ["--index", os.path.join(index_ordner, f"projekte_{time.strftime('%Y%m%d_%H%M%S')}.csv")]
    if flag(p.get("ver")):
        pw = (p.get("pw") or "").strip()
        if not pw:
            raise ValueError("Verschlüsselung: bitte ein Passwort angeben")
        argv += ["--verschluesseln", pw,
                 "--verschluesseln-rechte", auswahl(p.get("rechte"), "Rechte",
                                                    ["drucken", "alles", "nichts"], "drucken")]
    return argv, (f"{projekte} Projekt(e) mit je {dokumente} Dokumenten nach {ziel}"
                  + (", verschlüsselt" if flag(p.get("ver")) else ""))


def a_entsperren(p):
    quelle = pfad(p.get("ordner"), "Ordner", STANDARD_ZIEL, muss_existieren=True)
    pw = (p.get("pw") or "").strip()
    if not pw:
        raise ValueError("Entsperren: bitte das Passwort der PDFs angeben")
    argv = [PY, "unlock.py", quelle, "--passwort", pw]
    ziel = (p.get("ziel") or "").strip()
    if ziel:
        argv += ["--ziel", pfad(ziel, "Zielordner")]
    return argv, f"Verschlüsselte PDFs in {quelle} entsperren (Kopien ohne Passwort)"


AKTIONEN = {
    "dateien": a_dateien,
    "pruefen": a_pruefen,
    "mails": a_mails,
    "mail_check": a_mail_check,
    "postfach": a_postfach,
    "sink": a_sink,
    "testlauf": a_testlauf,
    "entsperren": a_entsperren,
    "projekt": a_projekt,
}


# ------------------------------------------------------------------- Prozesslauf
def leser(prozess):
    for roh in prozess.stdout:
        with sperre:
            zustand["zeilen"].append(roh.rstrip("\r\n"))
    prozess.wait()
    with sperre:
        zustand["ende"] = time.time()
        zustand["exit"] = prozess.returncode
        zustand["historie"].appendleft({
            "aktion": zustand["aktion"], "parameter": zustand["parameter"],
            "exit": prozess.returncode, "sekunden": round(zustand["ende"] - (zustand["start"] or 0), 1),
            "zeit": time.strftime("%d.%m.%Y %H:%M:%S"),
            "kurz": (zustand["zeilen"][-1][:120] if zustand["zeilen"] else ""),
        })


def starte(aktion, parameter):
    with sperre:
        if zustand["prozess"] and zustand["prozess"].poll() is None:
            raise ValueError("Es läuft bereits ein Kommando — bitte erst stoppen oder abwarten.")
        if aktion not in AKTIONEN:
            raise ValueError(f"Unbekannte Aktion: {aktion}")
        argv, beschreibung = AKTIONEN[aktion](parameter)
        zustand.update({"zeilen": deque(maxlen=3000), "prozess": None, "exit": None, "ende": None,
                        "aktion": aktion, "parameter": parameter, "start": time.time()})
        zustand["argv"] = argv
        zustand["zeilen"].append(f"$ {' '.join(argv)}")
        zustand["zeilen"].append(f"# {beschreibung}")
        # PYTHONIOENCODING erzwingt UTF-8 auch in Kindprozessen (Windows-Pipe wäre sonst cp1252)
        umgebung = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        prozess = subprocess.Popen(argv, cwd=HIER, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding="utf-8", errors="replace", bufsize=1, env=umgebung)
        zustand["prozess"] = prozess
    threading.Thread(target=leser, args=(prozess,), daemon=True).start()
    return beschreibung


def beende_prozess(server=None):
    """Beendet laufende Kommandos und den Leitstand-Prozess zuverlässig.

    server.shutdown() allein genügt nicht: laufen noch Threads (Lesethread, HTTP-Threads)
    oder wurde das Skript über einen Launcher gestartet, bleibt der Python-Prozess stehen.
    Deshalb danach hart os._exit().
    """
    stoppe()
    if server is not None:
        try:
            server.shutdown()
        except Exception:  # noqa: BLE001
            pass
        try:
            server.server_close()
        except Exception:  # noqa: BLE001
            pass
    time.sleep(0.4)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


def stoppe():
    with sperre:
        p = zustand["prozess"]
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
            zustand["zeilen"].append("### Vom Leitstand abgebrochen")
            return True
    return False


def status():
    with sperre:
        p = zustand["prozess"]
        laeuft = bool(p and p.poll() is None)
        exit_code = zustand["exit"]
        # Wettlauf: der Prozess ist schon beendet, der Lesethread hat den Exit-Code aber
        # noch nicht eingetragen. Dann direkt den Rückgabecode des Prozesses melden.
        if not laeuft and exit_code is None and p is not None:
            exit_code = p.returncode
        return {
            "laeuft": laeuft,
            "aktion": zustand["aktion"],
            "exit": None if laeuft else exit_code,
            "dauer": round((zustand["ende"] or time.time()) - zustand["start"], 1) if zustand["start"] else None,
            "zeilen": list(zustand["zeilen"])[-400:],
            "historie": list(zustand["historie"])[:10],
        }


# ------------------------------------------------------------------------- HTTP
class Server(ThreadingHTTPServer):
    """HTTP-Server mit eindeutiger Portbindung.

    Windows erlaubt mit SO_REUSEADDR, dass ein zweiter Prozess denselben Port bindet — dann
    bedienen zwei Instanzen abwechselnd dieselben Anfragen und ein Beenden trifft nur eine davon.
    Deshalb auf Windows ohne Adresswiederverwendung starten; der zweite Start bricht dann mit
    klarer Meldung ab.
    """

    allow_reuse_address = os.name != "nt"
    daemon_threads = True


class Handler(BaseHTTPRequestHandler):
    server_version = "Leitstand/1.0"

    def log_message(self, fmt, *args):  # ruhig bleiben
        pass

    def _sende(self, code, typ, daten):
        self.send_response(code)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(daten)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(daten)

    def _json(self, code, objekt):
        self._sende(code, "application/json; charset=utf-8", json.dumps(objekt, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        pfad_url = urlparse(self.path)
        if pfad_url.path in ("/", "/index.html"):
            with open(os.path.join(HIER, "panel.html"), "rb") as fh:
                self._sende(200, "text/html; charset=utf-8", fh.read())
        elif pfad_url.path == "/api/status":
            self._json(200, status())
        elif pfad_url.path == "/api/config":
            q = pfad_url.query
            ordner = parse_qs(q).get("ordner", [STANDARD_ZIEL])[0] or STANDARD_ZIEL
            info = {"python": sys.version.split()[0], "repo": HIER, "standard_ziel": STANDARD_ZIEL,
                    "mail": mail_config(), "port": self.server.server_address[1]}
            try:
                info["ordner"] = {"pfad": ordner, "existiert": os.path.isdir(ordner)}
                if os.path.isdir(ordner):
                    info["ordner"].update(zaehle(ordner))
            except OSError as exc:
                info["ordner"] = {"pfad": ordner, "fehler": str(exc)}
            self._json(200, info)
        else:
            self._json(404, {"fehler": "unbekannter Pfad"})

    def do_POST(self):
        laenge = int(self.headers.get("Content-Length") or 0)
        try:
            daten = json.loads(self.rfile.read(laenge) or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"fehler": "ungültiges JSON"})
            return
        pfad_url = urlparse(self.path)
        try:
            if pfad_url.path == "/api/run":
                beschreibung = starte(daten.get("aktion"), daten.get("parameter") or {})
                with sperre:
                    argv = list(zustand.get("argv") or [])
                self._json(200, {"ok": True, "beschreibung": beschreibung, "argv": argv[1:]})
            elif pfad_url.path == "/api/stop":
                self._json(200, {"ok": stoppe()})
            elif pfad_url.path == "/api/open":
                ziel = pfad(daten.get("ordner"), "Ordner", STANDARD_ZIEL, muss_existieren=True)
                if sys.platform == "win32":
                    os.startfile(ziel)  # noqa: S606
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", ziel])
                else:
                    subprocess.Popen(["xdg-open", ziel])
                self._json(200, {"ok": True, "ordner": ziel})
            elif pfad_url.path == "/api/quit":
                # Beenden aus der Oberfläche: erst antworten, dann Kommando stoppen und Prozess beenden
                self._json(200, {"ok": True, "hinweis": "Leitstand wird beendet"})
                threading.Thread(target=beende_prozess, args=(self.server,), daemon=True).start()
            elif pfad_url.path == "/api/selftest":
                self._json(200, selftest())
            else:
                self._json(404, {"fehler": "unbekannter Pfad"})
        except ValueError as exc:
            self._json(400, {"fehler": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._json(500, {"fehler": f"{type(exc).__name__}: {exc}"})


def selftest():
    """Prüft die Leitstand-Mechanik ohne Browser: Aktion starten, Ausgabe verfolgen, Ergebnis."""
    ergebnisse = []
    try:
        starte("pruefen", {"ordner": os.path.join(HIER, "examples")})
    except ValueError as exc:
        return {"ok": False, "fehler": str(exc)}
    for _ in range(600):
        s = status()
        if not s["laeuft"]:
            break
        time.sleep(0.5)
    s = status()
    ergebnisse.append({"schritt": "pruefen auf examples/", "exit": s["exit"],
                       "zeilen": len(s["zeilen"])})
    # ungültige Parameter müssen abgewiesen werden
    probe_ordner = os.path.join(tempfile.gettempdir(), "leitstand_selftest")
    faelle = [("dateien", {"ordner": probe_ordner, "count": "abc"}, "ganze Zahl"),
              ("dateien", {"ordner": probe_ordner, "count": "999999"}, "erlaubt sind"),
              ("dateien", {"ordner": probe_ordner, "jobs": "0"}, "erlaubt sind"),
              ("dateien", {"ordner": probe_ordner, "layout": "quer"}, "erlaubt sind"),
              ("dateien", {"ordner": probe_ordner + chr(10) + "rm -rf", "count": "5"}, "unzulässige Zeichen"),
              ("mails", {"transport": "brieftaube"}, "erlaubt sind"),
              ("mail_check", {"was": "irgendwas"}, "erlaubt sind"),
              ("unbekannt", {}, "Unbekannte Aktion")]
    for aktion, parameter, erwartet in faelle:
        try:
            if aktion == "unbekannt":
                starte("gibt-es-nicht", {})
            else:
                AKTIONEN[aktion](parameter)
            ergebnisse.append({"schritt": f"{aktion}/{erwartet}", "abgewiesen": False})
        except ValueError as exc:
            ergebnisse.append({"schritt": f"{aktion}/{erwartet}",
                               "abgewiesen": erwartet.lower() in str(exc).lower(),
                               "meldung": str(exc)[:70]})
    ok = ergebnisse[0]["exit"] == 0 and all(e.get("abgewiesen") for e in ergebnisse[1:])
    return {"ok": ok, "ergebnisse": ergebnisse, "historie": list(zustand["historie"])[:3]}


def stoppe_ueber_api(host, port):
    """Beendet einen laufenden Leitstand über dessen API."""
    import json as _json
    import urllib.error
    import urllib.request
    adresse = f"http://{host}:{port}/api/quit"
    try:
        anfrage = urllib.request.Request(adresse, data=b"{}", method="POST",
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(anfrage, timeout=5) as antwort:
            _json.loads(antwort.read() or b"{}")
    except urllib.error.URLError as exc:
        print(f"Kein Leitstand auf {host}:{port} erreichbar ({exc.reason}).")
        return 0
    for _ in range(20):
        time.sleep(0.3)
        try:
            urllib.request.urlopen(f"http://{host}:{port}/api/status", timeout=2)
        except Exception:  # noqa: BLE001
            print(f"Leitstand auf {host}:{port} beendet.")
            return 0
    print(f"Leitstand auf {host}:{port} antwortet noch — bitte leitstand-stop.cmd {port} nutzen.",
          file=sys.stderr)
    return 1


def main():
    ap = argparse.ArgumentParser(description="Leitstand für den Fake-PDF-Generator")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--selftest", action="store_true", help="Smoke-Test ohne Server/Browser")
    ap.add_argument("--stop", action="store_true",
                    help="laufenden Leitstand über /api/quit beenden (auch aus einem Skript)")
    ap.add_argument("--ziel", default=None, help="Zielordner, der in der Oberfläche vorbelegt wird")
    a = ap.parse_args()
    global STANDARD_ZIEL
    if a.ziel:
        STANDARD_ZIEL = a.ziel

    if a.selftest:
        ergebnis = selftest()
        print(json.dumps(ergebnis, ensure_ascii=False, indent=2))
        return 0 if ergebnis["ok"] else 1

    if a.stop:
        return stoppe_ueber_api(a.host, a.port)

    try:
        server = Server((a.host, a.port), Handler)
    except OSError as exc:
        print(f"FEHLER: Port {a.port} ist belegt ({exc}).", file=sys.stderr)
        print(f"Läuft schon ein Leitstand? Beenden mit: leitstand-stop.cmd {a.port} "
              f"oder python panel.py --stop --port {a.port}", file=sys.stderr)
        return 2
    url = f"http://{a.host}:{a.port}/"
    print(f"Leitstand läuft: {url}\nArbeitsordner des Generators: {HIER}\nBeenden mit Strg-C")
    print(f"Aktionen: {', '.join(AKTIONEN)}")
    print("Beenden: Strg-C hier, der Knopf \"Beenden\" in der Oberfläche oder leitstand-stop.cmd")
    if not a.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nLeitstand beendet.")
    finally:
        stoppe()
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
