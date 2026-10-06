#!/usr/bin/env python3
"""
Baut die Preisdatenbank aller deutschen Pokémon-Karten für den Skill "Pokemon-Auktion".

Quellen
  - TCGdex (api.tcgdex.net): deutsche Sets/Karten, englische Namen, Cardmarket-Produkt-ID
    und (Fallback) Cardmarket-Preise
  - Cardmarket-Preisguide (downloads.s3.cardmarket.com, Spiel-ID 6 = Pokémon): aktuelle
    Trend-/Durchschnittspreise je Produkt-ID – hat Vorrang vor den TCGdex-Preisen

Ausgabe
  dist/pokemon_de.sqlite   Tabellen karten + meta (Schema wie von cm_preise.py erwartet)
  dist/pokemon_de.csv      gleiche Daten als CSV (Semikolon, UTF-8)

Aufruf
  python3 build_db.py                    # normal (Netzwerk)
  python3 build_db.py --fixture DIR      # offline mit gespeicherten JSON-Antworten (Test)

Exit-Code 1, wenn die Plausibilitätsprüfung fehlschlägt – dann wird nichts veröffentlicht
und die zuletzt veröffentlichte Datenbank bleibt bestehen.
"""
import argparse
import csv
import json
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

TCGDEX = "https://api.tcgdex.net/v2"
PREISGUIDE = "https://downloads.s3.cardmarket.com/productCatalog/priceGuide/price_guide_6.json"
UA = {"User-Agent": "pokemon-preise/1.0 (github.com/MarcDiesing/pokemon-preise)"}
WORKERS = 12

# Plausibilitätsgrenzen
MIN_KARTEN = 10000
MIN_ANTEIL_PREIS = 0.5
REFERENZ = ("base1-4", 20.0)  # Glurak Base Set: Trend muss über diesem Wert liegen

FIXTURE = None


def hole(url, versuche=4):
    if FIXTURE:
        datei = FIXTURE / (urllib.parse.quote(url, safe="") + ".json")
        return json.loads(datei.read_text()) if datei.exists() else None
    for i in range(versuche):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            fehler = e
        except Exception as e:  # Netzwerk, Timeout, JSON
            fehler = e
        time.sleep(2 ** i)
    print(f"WARNUNG: {url} nicht ladbar ({fehler})", file=sys.stderr)
    return None


def zahl(v):
    try:
        f = float(v)
        return round(f, 2) if f > 0 else None
    except (TypeError, ValueError):
        return None


def lade_preisguide():
    d = hole(PREISGUIDE)
    if not d:
        return {}, None
    pg = {int(p["idProduct"]): p for p in d.get("priceGuides", []) if p.get("idProduct")}
    return pg, d.get("createdAt")


def lade_set(set_id):
    de = hole(f"{TCGDEX}/de/sets/{set_id}")
    en = hole(f"{TCGDEX}/en/sets/{set_id}")
    return de, en


def lade_karte(card_id):
    return hole(f"{TCGDEX}/de/cards/{card_id}")


def cm_url(name_en, name_de):
    q = name_en or name_de or ""
    return "https://www.cardmarket.com/de/Pokemon/Products/Search?searchString=" + urllib.parse.quote(q)


# Felder ohne Bedeutung für die Druckvariante (Metadaten der TCGdex-API)
STANDARD_FELDER = {"type", "subtype", "thirdParty", "size", "variantId", "id", "pricing", "languages"}


def variante_name(v):
    """z. B. 'Normal', 'Holo-schattenlos', 'Stempel Normal [pokemon-center]', 'Folie Reverse [cosmos]'.
    Das Sondermerkmal steht vorne, weil cm_preise.py die Variante auf 12 Zeichen kürzt."""
    name = v.get("type") or "?"
    if v.get("subtype"):
        name += "-" + str(v["subtype"])
    tags, details = [], []
    if v.get("size") and v["size"] not in ("standard", "Standard"):
        tags.append("Größe")
        details.append(str(v["size"]))
    if v.get("foil"):
        tags.append("Folie")
        details.append(str(v["foil"]))
    if v.get("stamp"):
        s = v["stamp"]
        tags.append("Stempel")
        details.append(", ".join(map(str, s)) if isinstance(s, list) else str(s))
    for k, w in v.items():  # unbekannte Merkmale nicht verschlucken
        if k not in STANDARD_FELDER | {"foil", "stamp"} and w not in (None, "", [], False):
            tags.append("Sonder")
            details.append(f"{k}: {w}")
    if not tags:
        return name
    return f"{'+'.join(dict.fromkeys(tags))} {name} [{'; '.join(details)}]"


def baue_zeilen(karte, set_de, set_en, en_namen, pg):
    sid = set_de.get("id")
    abk = (set_de.get("abbreviation") or {})
    basis = dict(
        name_de=karte.get("name"),
        name_en=en_namen.get(karte.get("localId")),
        set_id=sid,
        set_de=set_de.get("name"),
        set_en=(set_en or {}).get("name"),
        set_kuerzel=abk.get("official") or abk.get("localized"),
        nummer=str(karte.get("localId") or ""),
        seltenheit=karte.get("rarity"),
        tcgdex_id=karte.get("id"),
    )
    # Varianten mit eigener Cardmarket-ID. Gleiche ID (typisch: Normal + Reverse) = eine Zeile;
    # Sonderdrucke (Stempel, Spezialfolie, Größe, Fehldruck …) werden im Namen markiert.
    gruppen = {}
    for v in karte.get("variants_detailed") or []:
        vid = ((v.get("thirdParty") or {}).get("cardmarket"))
        if not vid:
            continue
        name = variante_name(v)
        g = gruppen.setdefault(int(vid), [])
        if name not in g:
            g.append(name)
    # Standarddrucke zuerst; teilt sich ein Standarddruck die ID mit einem Sonderdruck,
    # ist der Preis der des Standardprodukts (sondervariante = 0)
    varianten = [("/".join(sorted(n, key=lambda x: x.endswith("]"))), vid) for vid, n in gruppen.items()]
    haupt = (karte.get("thirdParty") or {}).get("cardmarket")
    if not varianten:
        varianten = [(None, int(haupt) if haupt else None)]

    tcg_cm = ((karte.get("pricing") or {}).get("cardmarket") or {})
    zeilen = []
    for variante, cid in varianten:
        p = pg.get(cid) if cid else None
        if p:
            trend, avg30, low = zahl(p.get("trend")), zahl(p.get("avg30")), zahl(p.get("low"))
            trend_rev = zahl(p.get("trend-holo"))
            quelle, stand = "cardmarket-preisguide", None
        elif tcg_cm and (cid is None or cid == haupt):
            trend, avg30, low = zahl(tcg_cm.get("trend")), zahl(tcg_cm.get("avg30")), zahl(tcg_cm.get("low"))
            trend_rev = zahl(tcg_cm.get("trend-holo"))
            quelle, stand = "tcgdex", tcg_cm.get("updated")
            cid = cid or tcg_cm.get("idProduct")
        else:
            trend = avg30 = low = trend_rev = None
            quelle, stand = None, None
        zeilen.append(dict(basis, cm_variante=variante, cm_id=cid, trend=trend, avg30=avg30,
                           low=low, trend_reverse=trend_rev,
                           sondervariante=1 if variante and all(
                               t.endswith("]") for t in variante.split("/")) else 0,
                           cm_url=cm_url(basis["name_en"], basis["name_de"]),
                           preis_quelle=quelle, preis_stand=stand))
    return zeilen


SCHEMA = """
CREATE TABLE karten (
  name_de TEXT, name_en TEXT, set_id TEXT, set_de TEXT, set_en TEXT, set_kuerzel TEXT,
  nummer TEXT, seltenheit TEXT, tcgdex_id TEXT, cm_variante TEXT, cm_id INTEGER,
  trend REAL, avg30 REAL, low REAL, trend_reverse REAL, sondervariante INTEGER, cm_url TEXT,
  preis_quelle TEXT, preis_stand TEXT
);
CREATE INDEX ix_name ON karten(name_de);
CREATE INDEX ix_set ON karten(set_id);
CREATE TABLE meta (schluessel TEXT PRIMARY KEY, wert TEXT);
"""
SPALTEN = ["name_de", "name_en", "set_id", "set_de", "set_en", "set_kuerzel", "nummer",
           "seltenheit", "tcgdex_id", "cm_variante", "cm_id", "trend", "avg30", "low",
           "trend_reverse", "sondervariante", "cm_url", "preis_quelle", "preis_stand"]


def pruefe(zeilen):
    probleme = []
    n = len(zeilen)
    mit_preis = sum(1 for z in zeilen if z["trend"] or z["trend_reverse"])
    if n < MIN_KARTEN:
        probleme.append(f"nur {n} Karten (< {MIN_KARTEN})")
    if n and mit_preis / n < MIN_ANTEIL_PREIS:
        probleme.append(f"nur {mit_preis}/{n} Karten mit Preis")
    ref_id, ref_min = REFERENZ
    ref = [z for z in zeilen if z["tcgdex_id"] == ref_id and (z["trend"] or 0) > ref_min]
    if not ref:
        probleme.append(f"Referenzkarte {ref_id} fehlt oder Trend ≤ {ref_min} €")
    return probleme, mit_preis


def main():
    global FIXTURE
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", type=Path)
    ap.add_argument("--out", type=Path, default=Path("dist"))
    a = ap.parse_args()
    FIXTURE = a.fixture
    start = time.time()

    pg, pg_stand = lade_preisguide()
    print(f"Preisguide: {len(pg)} Produkte, Stand {pg_stand}")

    sets = hole(f"{TCGDEX}/de/sets") or []
    print(f"TCGdex: {len(sets)} deutsche Sets")
    with ThreadPoolExecutor(WORKERS) as ex:
        set_daten = list(ex.map(lambda s: lade_set(s["id"]), sets))

    jobs = []  # (karten_id, set_de, set_en, en_namen)
    for de, en in set_daten:
        if not de:
            continue
        en_namen = {c.get("localId"): c.get("name") for c in (en or {}).get("cards", [])}
        for c in de.get("cards", []):
            jobs.append((c["id"], de, en, en_namen))
    print(f"Lade {len(jobs)} Karten …")
    with ThreadPoolExecutor(WORKERS) as ex:
        karten = list(ex.map(lambda j: lade_karte(j[0]), jobs))

    zeilen, fehlend = [], 0
    for (cid, de, en, en_namen), k in zip(jobs, karten):
        if not k:
            fehlend += 1
            continue
        zeilen.extend(baue_zeilen(k, de, en, en_namen, pg))

    probleme, mit_preis = pruefe(zeilen)
    jetzt = datetime.now(timezone.utc).isoformat(timespec="seconds")
    meta = {
        "erstellt": jetzt,
        "preisguide_stand": pg_stand or "nicht geladen (nur TCGdex-Preise)",
        "karten": str(len(zeilen)),
        "karten_mit_preis": str(mit_preis),
        "karten_nicht_ladbar": str(fehlend),
        "sets": str(len(sets)),
        "quellen": "TCGdex (de/en) + Cardmarket-Preisguide",
        "hinweis": "Cardmarket-Preise sind sprachübergreifend, nicht speziell für deutsche Karten",
        "pruefung": "OK" if not probleme else "FEHLER: " + "; ".join(probleme),
        "laufzeit_s": str(int(time.time() - start)),
    }

    a.out.mkdir(parents=True, exist_ok=True)
    db = a.out / "pokemon_de.sqlite"
    db.unlink(missing_ok=True)
    con = sqlite3.connect(db)
    con.executescript(SCHEMA)
    con.executemany(f"INSERT INTO karten ({','.join(SPALTEN)}) VALUES ({','.join('?' * len(SPALTEN))})",
                    [[z[s] for s in SPALTEN] for z in zeilen])
    con.executemany("INSERT INTO meta VALUES (?, ?)", meta.items())
    con.commit()
    con.execute("VACUUM")
    con.close()

    with open(a.out / "pokemon_de.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, SPALTEN, delimiter=";")
        w.writeheader()
        w.writerows(zeilen)

    for k, v in meta.items():
        print(f"{k:20} {v}")
    if probleme:
        sys.exit(1)


if __name__ == "__main__":
    main()
