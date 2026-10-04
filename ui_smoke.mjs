// Headless-Test der Leitstand-Oberfläche.
//   node ui_smoke.mjs
//
// Lädt world das echte panel.html, baut daraus einen DOM-Shim und führt das
// Oberflächen-JavaScript gegen einen selbst gestarteten panel.py aus. Damit fallen
// Fehler wie "null.value" (Feld im Formular fehlt) und falsch zusammengesetzte
// Aufträge auf, ohne dass ein Browser nötig ist.
import { existsSync, readFileSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { setTimeout as schlaf } from 'node:timers/promises';

const PORT = 8799;
const BASIS = `http://127.0.0.1:${PORT}`;
// In einer venv-Installation liegt Python dort, in CI (systemweite Installation) im PATH
const PY = process.platform === 'win32'
  ? (existsSync('.venv/Scripts/python.exe') ? '.venv/Scripts/python.exe' : 'python')
  : (existsSync('.venv/bin/python') ? '.venv/bin/python' : 'python3');
const ZIEL = (process.env.TMPDIR || process.env.TEMP || '/tmp').replace(/\\/g, '/') + '/leitstand_ui_smoke';

const html = readFileSync('panel.html', 'utf8');
const appJs = html.split('<script>')[1].split('</script>')[0];

// ------------------------------------------------------------------ DOM-Shim
const treffer = [...html.matchAll(/<(?:input|select|textarea|button|pre|div|span|h1|tbody)\b([^>]*?)id="([^"]+)"([^>]*)>/g)];
const elemente = {};
for (const m of treffer) {
  const attrs = m[1] + ' ' + m[3];
  elemente[m[2]] = {
    id: m[2],
    type: (attrs.match(/type="([^"]+)"/) || [, 'text'])[1],
    value: (attrs.match(/value="([^"]*)"/) || [, ''])[1],
    checked: /\bchecked\b/.test(attrs),
    disabled: false, textContent: '', innerHTML: '', className: '',
    scrollTop: 0, scrollHeight: 0, clientHeight: 0, style: {},
    dataset: Object.fromEntries([...attrs.matchAll(/data-([a-z]+)="([^"]*)"/g)].map((x) => [x[1], x[2]])),
    handlers: {},
    addEventListener(art, fn) { (this.handlers[art] ||= []).push(fn); },
    dispatchEvent(ev) { return Promise.all((this.handlers[ev.type] || []).map((f) => f(ev))); },
    click() { return this.dispatchEvent({ type: 'click' }); },
  };
}
const knoepfe = [...html.matchAll(/<button([^>]*data-aktion[^>]*)>/g)].map((m) => {
  const attrs = m[1];
  return {
    dataset: Object.fromEntries([...attrs.matchAll(/data-([a-z]+)="([^"]*)"/g)].map((x) => [x[1], x[2]])),
    handlers: {}, disabled: false,
    addEventListener(art, fn) { (this.handlers[art] ||= []).push(fn); },
    click() { return Promise.all((this.handlers.click || []).map((f) => f({ type: 'click' }))); },
  };
});
const speicher = new Map();
const document = {
  getElementById(id) {
    if (!elemente[id]) throw new Error(`Feld "${id}" gibt es in panel.html nicht`);
    return elemente[id];
  },
  querySelectorAll(sel) {
    if (sel.includes('data-aktion')) return knoepfe;
    if (sel.includes('historie')) {
      const n = (elemente['historie']?.innerHTML.match(/<tr/g) || []).length;
      return Array.from({ length: n }, () => ({}));
    }
    return [];
  },
};
const localStorage = { getItem: (k) => (speicher.has(k) ? speicher.get(k) : null), setItem: (k, v) => speicher.set(k, v) };
const Event = class { constructor(type) { this.type = type; } };

const abrufe = [];
async function fetchEcht(url, optionen) {
  const voll = url.startsWith('http') ? url : BASIS + url;
  const antwort = await globalThis.fetch(voll, optionen);
  const eintrag = { url: voll, optionen };
  try { eintrag.antwort = await antwort.clone().json(); } catch { /* kein JSON */ }
  abrufe.push(eintrag);
  return antwort;
}

const tests = [];
const pruefe = (name, ok, detail = '') => tests.push({ name, ok: !!ok, detail });

// ------------------------------------------------------------------ Testablauf
const testJs = `
return (async () => {
  const erwartet = {
    dateien: ['ordner', 'count', 'seed', 'jobs', 'layout', 'datum', 'index', 'ver', 'pw', 'rechte'],
    pruefen: ['ordner', 'pw'],
    mails: ['count', 'seed', 'transport', 'datum', 'mailordner', 'dokument_heute', 'ver', 'pw', 'rechte'],
    mail_check: ['was'],
    postfach: ['anzahl'],
    sink: ['sekunden', 'mailordner'],
    testlauf: ['ordner', 'live', 'keep'],
    entsperren: ['ordner', 'pw', 'ziel'],
  };
  const ziel = ${JSON.stringify(ZIEL)};
  await umgebung();
  const cfg0 = await (await fetch('/api/config')).json();
  pruefe('Zielordner mit Server-Standard vorbelegt',
    document.getElementById('d-ordner').value.trim() === cfg0.standard_ziel.trim(),
    'Feld: ' + document.getElementById('d-ordner').value);
  $('d-ordner').value = ziel;

  // 1) Jeder Knopf setzt genau die erwarteten Felder ab (kein null.value, keine Lücken)
  for (const knopf of document.querySelectorAll('button[data-aktion]')) {
    const aktion = knopf.dataset.aktion;
    const vorher = abrufe.length;
    try {
      await knopf.click();
    } catch (e) {
      pruefe('Knopf ' + aktion, false, 'Ausnahme: ' + e.message);
      continue;
    }
    const neu = abrufe.slice(vorher).filter((a) => a.url.endsWith('/api/run'));
    if (neu.length !== 1) { pruefe('Knopf ' + aktion, false, 'kein /api/run abgesetzt'); continue; }
    const koerper = JSON.parse(neu[0].optionen.body);
    const fehlend = (erwartet[aktion] || []).filter((f) => !(f in (koerper.parameter || {})));
    pruefe('Knopf ' + aktion, koerper.aktion === aktion && fehlend.length === 0,
      fehlend.length ? 'fehlende Felder: ' + fehlend.join(',') : Object.keys(koerper.parameter).length + ' Felder');
    await fetch('/api/stop', { method: 'POST', body: '{}' });
    await new Promise((r) => setTimeout(r, 400));
  }

  // 2) Echter Durchlauf über die Oberfläche
  const stellen = (id, wert) => { const e = document.getElementById(id); e.value = wert; };
  await fetch('/api/run', { method: 'POST', body: JSON.stringify({ aktion: 'dateien', parameter: {
    ordner: ziel, count: '6', seed: '4711', jobs: '2', layout: 'flach', datum: 'heute' } }) });
  for (let i = 0; i < 80; i++) {
    await aktualisiere();
    if (document.getElementById('status-pill').textContent !== 'läuft') break;
    await new Promise((r) => setTimeout(r, 400));
  }
  // Der Server muss den Index außerhalb des Zielordners ablegen
  const ruf = abrufe.filter((a) => a.url.endsWith('/api/run') && (a.optionen?.body || '').includes('"dateien"')
    && a.antwort && a.antwort.argv).pop();
  const argv = ruf ? ruf.antwort.argv : [];
  const idx = argv.indexOf('--index');
  pruefe('Index wird außerhalb des Zielordners abgelegt',
    idx > 0 && !argv[idx + 1].startsWith(ziel), idx > 0 ? argv[idx + 1] : 'kein --index in der Argumentliste');

  pruefe('Statuspill nach Lauf = fertig', document.getElementById('status-pill').textContent === 'fertig',
    'Pill: ' + document.getElementById('status-pill').textContent);
  pruefe('Konsole zeigt Ergebnis', /Fertig: 6 PDFs/.test(document.getElementById('konsole').textContent),
    document.getElementById('konsole').textContent.slice(-90).replace(/\\n/g, ' '));
  pruefe('Historie gefüllt', document.querySelectorAll('#historie tr').length >= 1);
  pruefe('Umgebungsanzeige gefüllt', /Python/.test(document.getElementById('umgebung').innerHTML));

  // 3) Ungültige Eingabe muss abgewiesen werden (Server antwortet 400, Oberfläche zeigt es an)
  stellen('d-count', '0');
  await knoepfe[0].click();
  pruefe('ungültige Anzahl abgewiesen', /erlaubt sind|Zahl/.test(document.getElementById('d-fehler').textContent),
    document.getElementById('d-fehler').textContent);
})().catch((e) => pruefe('Testablauf', false, 'Ausnahme: ' + e.message));
`;

const server = spawn(PY, ['panel.py', '--no-browser', '--port', String(PORT)],
  { stdio: 'ignore', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
try {
  let bereit = false;
  for (let i = 0; i < 40 && !bereit; i++) {
    try { await globalThis.fetch(BASIS + '/api/status'); bereit = true; } catch { await schlaf(250); }
  }
  pruefe('Leitstand erreichbar', bereit, BASIS);
  pruefe('alle Knöpfe haben data-aktion und data-form',
    knoepfe.every((k) => k.dataset.aktion && k.dataset.form),
    knoepfe.map((k) => k.dataset.aktion).join(','));

  const lauf = new Function('document', 'localStorage', 'setInterval', 'fetch', 'Event', 'pruefe',
    'abrufe', 'knoepfe', appJs + '\n' + testJs);
  await lauf(document, localStorage, () => 0, fetchEcht, Event, pruefe, abrufe, knoepfe);
} finally {
  server.kill();
}

let fehler = 0;
for (const t of tests) {
  if (!t.ok) fehler++;
  console.log(`${t.ok ? '  OK  ' : ' FEHL '} ${t.name}${t.detail ? ' — ' + t.detail : ''}`);
}
console.log(`\n${tests.length - fehler}/${tests.length} Oberflächenprüfungen bestanden`);
process.exit(fehler ? 1 : 0);
