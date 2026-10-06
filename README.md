# pokemon-preise

Täglich aktualisierte Preisdatenbank aller deutschen Pokémon-Karten – Datenquelle für den
Claude-Skill „Pokemon-Auktion“.

- **Quellen:** [TCGdex](https://tcgdex.dev) (deutsche/englische Namen, Sets, Cardmarket-Produkt-ID)
  und der öffentliche Cardmarket-Preisguide (Trend, 30-Tage-Schnitt, Reverse Holo).
- **Ausgabe:** `pokemon_de.sqlite` und `pokemon_de.csv` als Anhang des Releases
  [`daten-aktuell`](../../releases/tag/daten-aktuell), täglich gegen 06:17 Uhr ersetzt.
- **Fester Download-Link:**
  `https://github.com/MarcDiesing/pokemon-preise/releases/download/daten-aktuell/pokemon_de.sqlite`
- **Webseite (durchsuchbar):** https://marcdiesing.github.io/pokemon-preise/  
  Direktlinks: `#q=<Name>&set=<Set-ID oder Kürzel>&nr=<Nr.>&std=1`, z. B.
  `https://marcdiesing.github.io/pokemon-preise/#q=Glurak&set=base1&nr=4`

## Ablauf

`.github/workflows/daten.yml` baut die Datenbank mit `build_db.py`, lädt sie hoch und
erzeugt mit `build_html.py` die Webseite (GitHub Pages).
Schlägt die Plausibilitätsprüfung fehl (zu wenige Karten, zu wenige Preise, Referenzkarte
Glurak Base Set fehlt), bricht der Lauf ab und die alte Datenbank bleibt online.
Manuell starten: Tab **Actions → Preisdatenbank aktualisieren → Run workflow**.

## Tabellen

- `karten`: name_de, name_en, set_id, set_de, set_en, set_kuerzel, nummer, seltenheit,
  tcgdex_id, cm_variante, cm_id, trend, avg30, low, trend_reverse, sondervariante, cm_url,
  preis_quelle, preis_stand
- `cm_variante`: Standarddruck z. B. `Normal/Reverse`, `Holo-schattenlos`; Sonderdrucke beginnen mit
  `Stempel`, `Folie`, `Größe` oder `Sonder` (Details in eckigen Klammern). `sondervariante = 1`
  nur, wenn alle Drucke dieser Cardmarket-ID Sonderdrucke sind; teilt sich ein Standarddruck die
  ID (z. B. `Normal/Stempel Normal [1. Auflage]`), steht er vorne und `sondervariante = 0`.
- `meta`: erstellt, preisguide_stand, karten, karten_mit_preis, pruefung, …

## Letzte Auktionssuche (`suche.json`)

Die Webseite zeigt oben, welche Karten der Datenbank bei der letzten Auktionssuche berücksichtigt
wurden, und hebt sie in der Tabelle hervor. Format:

```json
{"datum": "2026-10-06", "beschreibung": "…", "db_genutzt": true, "hinweis": "…",
 "karten": [{"tcgdex_id": "base1-4", "cm_id": 273699, "auktion": "267798660274", "notiz": "Glurak Base Set"}]}
```

Ohne `cm_id` gelten alle Varianten der Karte als berücksichtigt. Die Datei wird nach einer Suche
ersetzt; die Seite übernimmt sie beim nächsten Lauf.

Hinweis: Cardmarket-Preise sind sprachübergreifende Durchschnittswerte, kein deutscher Marktpreis.
