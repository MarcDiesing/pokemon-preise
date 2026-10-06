# pokemon-preise

Täglich aktualisierte Preisdatenbank aller deutschen Pokémon-Karten – Datenquelle für den
Claude-Skill „Pokemon-Auktion“.

- **Quellen:** [TCGdex](https://tcgdex.dev) (deutsche/englische Namen, Sets, Cardmarket-Produkt-ID)
  und der öffentliche Cardmarket-Preisguide (Trend, 30-Tage-Schnitt, Reverse Holo).
- **Ausgabe:** `pokemon_de.sqlite` und `pokemon_de.csv` als Anhang des Releases
  [`daten-aktuell`](../../releases/tag/daten-aktuell), täglich gegen 06:17 Uhr ersetzt.
- **Fester Download-Link:**
  `https://github.com/MarcDiesing/pokemon-preise/releases/download/daten-aktuell/pokemon_de.sqlite`

## Ablauf

`.github/workflows/daten.yml` baut die Datenbank mit `build_db.py` und lädt sie hoch.
Schlägt die Plausibilitätsprüfung fehl (zu wenige Karten, zu wenige Preise, Referenzkarte
Glurak Base Set fehlt), bricht der Lauf ab und die alte Datenbank bleibt online.
Manuell starten: Tab **Actions → Preisdatenbank aktualisieren → Run workflow**.

## Tabellen

- `karten`: name_de, name_en, set_id, set_de, set_en, set_kuerzel, nummer, seltenheit,
  tcgdex_id, cm_variante, cm_id, trend, avg30, low, trend_reverse, cm_url, preis_quelle, preis_stand
- `meta`: erstellt, preisguide_stand, karten, karten_mit_preis, pruefung, …

Hinweis: Cardmarket-Preise sind sprachübergreifende Durchschnittswerte, kein deutscher Marktpreis.
