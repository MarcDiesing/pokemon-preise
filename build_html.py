#!/usr/bin/env python3
"""
Erzeugt aus pokemon_de.sqlite eine durchsuchbare HTML-Seite (eine Datei, keine externen Abhängigkeiten).

Aufruf
  python3 build_html.py dist/pokemon_de.sqlite site/index.html [--suche suche.json]

suche.json (optional) beschreibt die letzte Auktionssuche und welche DB-Karten dabei
berücksichtigt wurden:
  {"datum": "2026-10-06", "beschreibung": "...", "db_genutzt": true, "hinweis": "...",
   "karten": [{"tcgdex_id": "base1-4", "cm_id": 273699, "auktion": "267798660274",
               "notiz": "Glurak Base Set, unlimitiert"}]}
Ist "cm_id" weggelassen, gelten alle Varianten der Karte als berücksichtigt.
"""
import argparse
import html
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SPALTEN = ["name_de", "name_en", "set_id", "set_de", "set_en", "set_kuerzel", "nummer",
           "seltenheit", "tcgdex_id", "cm_variante", "cm_id", "trend", "avg30", "low",
           "trend_reverse", "sondervariante"]


def lokal(iso):
    try:
        return datetime.fromisoformat(iso).astimezone(ZoneInfo("Europe/Berlin")).strftime("%d.%m.%Y, %H:%M Uhr")
    except Exception:
        return iso or "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("db", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--suche", type=Path)
    a = ap.parse_args()

    con = sqlite3.connect(a.db)
    meta = dict(con.execute("SELECT schluessel, wert FROM meta"))
    rows = con.execute(f"SELECT {','.join(SPALTEN)} FROM karten").fetchall()
    # Sets in Erscheinungsreihenfolge der DB (TCGdex liefert chronologisch)
    sets = []
    for sid, sde, sen in con.execute("SELECT set_id, set_de, set_en FROM karten GROUP BY set_id ORDER BY MIN(rowid)"):
        sets.append([sid, sde or sen or sid])

    suche = {}
    if a.suche and a.suche.exists():
        suche = json.loads(a.suche.read_text(encoding="utf-8"))

    # kompakt: Set-Index statt Setname je Zeile
    set_idx = {s[0]: i for i, s in enumerate(sets)}
    kuerzel = {}
    daten = []
    for r in rows:
        d = dict(zip(SPALTEN, r))
        kuerzel.setdefault(d["set_id"], d["set_kuerzel"])
        daten.append([d["name_de"] or "", d["name_en"] or "", set_idx[d["set_id"]], d["nummer"] or "",
                      d["seltenheit"] or "", d["cm_variante"] or "", d["cm_id"], d["trend"], d["avg30"],
                      d["low"], d["trend_reverse"], d["sondervariante"] or 0, d["tcgdex_id"]])
    for s in sets:
        s.append(kuerzel.get(s[0]) or "")

    payload = json.dumps({"meta": meta, "sets": sets, "k": daten, "suche": suche},
                         ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(SEITE.replace("__DATEN__", payload)
                     .replace("__STAND__", html.escape(lokal(meta.get("erstellt")))), encoding="utf-8")
    print(f"{a.out}: {len(daten)} Einträge, {a.out.stat().st_size/1e6:.1f} MB")


SEITE = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pokémon-Preise DE</title>
<style>
:root{--bg:#f6f5f2;--fl:#fff;--tx:#1d1c1a;--dim:#6b6862;--ln:#e3e0da;--ak:#b4361f;--ak2:#fbe9e5;--ok:#2f6b3a;--okbg:#e5f1e6;--warn:#8a5a00;--warnbg:#fdf3dc;--mark:#fff4c2}
@media (prefers-color-scheme:dark){:root{--bg:#161614;--fl:#1f1e1c;--tx:#ecebe7;--dim:#9c988f;--ln:#34322e;--ak:#ef8a72;--ak2:#3a221c;--ok:#8fd19a;--okbg:#1f3323;--warn:#f0c46a;--warnbg:#3a2f15;--mark:#4a3f12}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1280px;margin:0 auto;padding:20px 16px 60px}
h1{font-size:22px;margin:0 0 2px}
.dim{color:var(--dim)}.small{font-size:13px}
.kpis{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}
.kpi{background:var(--fl);border:1px solid var(--ln);border-radius:10px;padding:8px 12px;min-width:140px}
.kpi b{display:block;font-size:18px;font-variant-numeric:tabular-nums}
.box{border-radius:10px;padding:12px 14px;margin:14px 0;border:1px solid var(--ln);background:var(--fl)}
.box.warn{background:var(--warnbg);border-color:transparent}
.box.ok{background:var(--okbg);border-color:transparent}
.box h2{font-size:15px;margin:0 0 4px}
.filter{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;background:var(--fl);border:1px solid var(--ln);border-radius:10px;padding:10px 12px;position:sticky;top:0;z-index:2}
.filter input[type=search]{flex:1 1 220px;min-width:0;padding:7px 10px;border:1px solid var(--ln);border-radius:7px;background:var(--bg);color:var(--tx);font:inherit}
.filter select,.filter input[type=number]{padding:6px 8px;border:1px solid var(--ln);border-radius:7px;background:var(--bg);color:var(--tx);font:inherit;max-width:100%}
.filter input[type=number]{width:80px}
.filter label{white-space:nowrap;font-size:14px}
.tw{overflow-x:auto;margin-top:10px;background:var(--fl);border:1px solid var(--ln);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{padding:6px 9px;border-bottom:1px solid var(--ln);text-align:left;white-space:nowrap}
th{position:sticky;top:0;background:var(--fl);cursor:pointer;user-select:none;font-weight:600}
th.r,td.r{text-align:right;font-variant-numeric:tabular-nums}
th[data-dir=asc]::after{content:" ▲"}th[data-dir=desc]::after{content:" ▼"}
td.var{max-width:260px;overflow:hidden;text-overflow:ellipsis}
tr.sonder td.var{color:var(--ak)}
tr.in td{background:var(--mark)}
.tag{display:inline-block;font-size:11px;padding:1px 6px;border-radius:9px;background:var(--ak2);color:var(--ak);margin-left:4px}
.tag.in{background:var(--okbg);color:var(--ok)}
a{color:var(--ak)}
.pager{display:flex;gap:8px;align-items:center;justify-content:space-between;flex-wrap:wrap;margin-top:10px}
button{font:inherit;padding:6px 12px;border-radius:7px;border:1px solid var(--ln);background:var(--fl);color:var(--tx);cursor:pointer}
button:disabled{opacity:.4;cursor:default}
footer{margin-top:24px}
</style>
</head>
<body>
<div class="wrap">
<h1>Pokémon-Preise (deutsche Karten)</h1>
<div class="dim small">Cardmarket-Preisguide + TCGdex · Datenbank erstellt __STAND__ · täglich aktualisiert</div>
<div class="kpis" id="kpis"></div>
<div id="suche"></div>
<div class="filter">
  <input type="search" id="q" placeholder="Name (deutsch oder englisch), z. B. Glurak, Charizard, Pikachu ex" autocomplete="off">
  <select id="set"><option value="">Alle Sets</option></select>
  <label>Trend ab <input type="number" id="min" min="0" step="0.5" placeholder="€"></label>
  <label><input type="checkbox" id="std"> nur Standarddruck</label>
  <label><input type="checkbox" id="preis" checked> nur mit Preis</label>
  <label id="inLbl" hidden><input type="checkbox" id="nurIn"> nur in Suche berücksichtigt</label>
</div>
<div class="pager"><span class="dim small" id="anz"></span><span><button id="zur">‹ zurück</button> <span class="small" id="seite"></span> <button id="vor">weiter ›</button></span></div>
<div class="tw"><table>
<thead><tr>
<th data-k="0">Name</th><th data-k="1">Englisch</th><th data-k="2">Set</th><th data-k="3" class="r">Nr.</th>
<th data-k="4">Seltenheit</th><th data-k="5">Variante</th><th data-k="7" class="r">Trend</th><th data-k="10" class="r">Reverse</th>
<th data-k="8" class="r">Ø 30 T.</th><th data-k="9" class="r">ab</th><th>Cardmarket</th>
</tr></thead><tbody id="tb"></tbody></table></div>
<footer class="dim small">
<p><b>Variante:</b> „Normal/Reverse“, „Holo“, „Holo-schattenlos“ usw. = Standarddruck. Rot markiert = Sonderdruck (beginnt mit Stempel, Folie, Größe oder Sonder) – nur ansetzen, wenn das Merkmal auf der Karte erkennbar ist. „Trend“ gilt für den normalen Druck, „Reverse“ für die Reverse-Holo-Version derselben Cardmarket-ID.</p>
<p>Cardmarket-Preise sind sprachübergreifende Durchschnittswerte (alle Sprachen und Zustände), kein deutscher Marktpreis. Bei manchen älteren Sets teilen sich Standarddruck und 1. Auflage eine Cardmarket-ID – dort ist der Preis nicht nach Edition getrennt. Quelle: <a href="https://github.com/MarcDiesing/pokemon-preise">github.com/MarcDiesing/pokemon-preise</a></p>
</footer>
</div>
<script id="daten" type="application/json">__DATEN__</script>
<script>
const D=JSON.parse(document.getElementById('daten').textContent);
const K=D.k, S=D.sets, M=D.meta, SU=D.suche||{};
const eur=v=>v==null?'–':v.toLocaleString('de-DE',{minimumFractionDigits:2,maximumFractionDigits:2})+' €';
const zahl=v=>Number(v).toLocaleString('de-DE');
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

// Kennzahlen
const pg=(M.preisguide_stand||'').slice(0,10);
document.getElementById('kpis').innerHTML=[
 ['Einträge',zahl(M.karten)],['mit Preis',zahl(M.karten_mit_preis)],['Sets',zahl(M.sets)],
 ['Preisguide',pg?pg.split('-').reverse().join('.'):'–'],['Prüfung',M.pruefung||'–']
].map(([a,b])=>`<div class="kpi"><span class="dim small">${a}</span><b>${esc(b)}</b></div>`).join('');

// letzte Suche
const inSet=new Map(); // "tcgdex|cm" oder "tcgdex|*" -> Einträge
(SU.karten||[]).forEach(c=>{const key=c.tcgdex_id+'|'+(c.cm_id??'*');(inSet.get(key)||inSet.set(key,[]).get(key)).push(c);});
const inSuche=r=>inSet.get(r[12]+'|'+r[6])||inSet.get(r[12]+'|*');
if(SU.datum){
 const n=(SU.karten||[]).length, dat=SU.datum.split('-').reverse().join('.');
 let h=`<h2>Letzte Auktionssuche: ${esc(dat)}${SU.beschreibung?' – '+esc(SU.beschreibung):''}</h2>`;
 if(!n){h+=`<div><b>Keine Karte aus dieser Datenbank berücksichtigt.</b> ${esc(SU.hinweis||'')}</div>`;}
 else{h+=`<div>${n} Karte(n) aus der Datenbank berücksichtigt – in der Tabelle gelb hinterlegt. ${esc(SU.hinweis||'')}</div>`;
  document.getElementById('inLbl').hidden=false;}
 const box=document.getElementById('suche');box.className='box '+(n?'ok':'warn');box.innerHTML=h;
}

// Set-Auswahl
const sel=document.getElementById('set');
S.forEach((s,i)=>{const o=document.createElement('option');o.value=i;o.textContent=s[1]+(s[2]?' ('+s[2]+')':'');sel.appendChild(o);});

// Filter, Sortierung, Seiten
const PRO=100;let seite=0,sortK=7,sortDir='desc',liste=[];
const norm=s=>s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'');
const NAME=K.map(r=>norm(r[0]+' '+r[1]));
function filtern(){
 const q=norm(document.getElementById('q').value.trim()), st=sel.value, mn=parseFloat(document.getElementById('min').value),
  std=document.getElementById('std').checked, pr=document.getElementById('preis').checked, ni=document.getElementById('nurIn').checked;
 const teile=q?q.split(/\s+/):[];
 liste=[];
 for(let i=0;i<K.length;i++){const r=K[i];
  if(st!==''&&r[2]!=+st)continue;
  if(std&&r[11])continue;
  if(pr&&r[7]==null&&r[10]==null)continue;
  if(!isNaN(mn)&&Math.max(r[7]||0,r[10]||0)<mn)continue;
  if(ni&&!inSuche(r))continue;
  if(teile.length&&!teile.every(t=>NAME[i].includes(t)))continue;
  liste.push(i);}
 sortieren();seite=0;zeigen();
}
function wert(r,k){if(k==2)return r[2];if(k==3){const n=parseInt(r[3]);return isNaN(n)?1e9:n;}
 if(k==7)return r[7]??(sortDir=='desc'?-1:1e9);if([8,9,10].includes(k))return r[k]??(sortDir=='desc'?-1:1e9);return r[k]||'';}
function sortieren(){const f=sortDir=='asc'?1:-1;
 liste.sort((a,b)=>{const x=wert(K[a],sortK),y=wert(K[b],sortK);
  return (typeof x=='string'?x.localeCompare(y,'de'):x-y)*f||K[a][2]-K[b][2]||(parseInt(K[a][3])||0)-(parseInt(K[b][3])||0);});
 document.querySelectorAll('th[data-k]').forEach(t=>t.dataset.dir=(+t.dataset.k==sortK)?sortDir:'');}
function cm(r){const q=encodeURIComponent(r[1]||r[0]);return `<a href="https://www.cardmarket.com/de/Pokemon/Products/Search?searchString=${q}" target="_blank" rel="noopener">suchen</a>`+(r[6]?` <span class="dim small">#${r[6]}</span>`:'');}
function zeigen(){
 const seiten=Math.max(1,Math.ceil(liste.length/PRO));seite=Math.min(seite,seiten-1);
 const html=liste.slice(seite*PRO,(seite+1)*PRO).map(i=>{const r=K[i],s=S[r[2]],u=inSuche(r);
  const cls=(r[11]?'sonder ':'')+(u?'in':'');
  const tagIn=u?`<span class="tag in" title="${esc(u.map(c=>(c.notiz||'')+(c.auktion?' – Auktion '+c.auktion:'')).join('; '))}">in Suche</span>`:'';
  return `<tr class="${cls}"><td>${esc(r[0])}${tagIn}</td><td class="dim">${esc(r[1])}</td><td>${esc(s[1])}${s[2]?' <span class="dim small">'+esc(s[2])+'</span>':''}</td>
<td class="r">${esc(r[3])}</td><td>${esc(r[4])}</td><td class="var" title="${esc(r[5])}">${esc(r[5]||'–')}${r[11]?'<span class="tag">Sonderdruck</span>':''}</td>
<td class="r">${eur(r[7])}</td><td class="r">${eur(r[10])}</td><td class="r">${eur(r[8])}</td><td class="r">${eur(r[9])}</td><td>${cm(r)}</td></tr>`;}).join('');
 document.getElementById('tb').innerHTML=html||'<tr><td colspan="11" class="dim">Keine Treffer.</td></tr>';
 document.getElementById('anz').textContent=zahl(liste.length)+' Treffer';
 document.getElementById('seite').textContent=`Seite ${seite+1} / ${seiten}`;
 document.getElementById('zur').disabled=seite==0;document.getElementById('vor').disabled=seite>=seiten-1;
}
let t;document.getElementById('q').addEventListener('input',()=>{clearTimeout(t);t=setTimeout(filtern,200);});
['set','min','std','preis','nurIn'].forEach(id=>document.getElementById(id).addEventListener('change',filtern));
document.getElementById('min').addEventListener('input',()=>{clearTimeout(t);t=setTimeout(filtern,300);});
document.getElementById('zur').onclick=()=>{seite--;zeigen();scrollTo(0,0);};
document.getElementById('vor').onclick=()=>{seite++;zeigen();scrollTo(0,0);};
document.querySelectorAll('th[data-k]').forEach(th=>th.onclick=()=>{const k=+th.dataset.k;
 if(sortK==k)sortDir=sortDir=='asc'?'desc':'asc';else{sortK=k;sortDir=[7,8,9,10].includes(k)?'desc':'asc';}sortieren();seite=0;zeigen();});
filtern();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
