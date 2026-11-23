# WFS_CP_Finder

Libreria Python **pura e indipendente da QGIS** per cercare particelle catastali italiane
mediante i servizi web dell'Agenzia delle Entrate (geoportale cartografia).

Dati necessari: **provincia, comune, foglio e particella**. Il progetto in origine era un
plugin QGIS (`__init__.py` con `QgsDockWidget`); ora la logica di rete, autenticazione CAPTCHA
e parsing è stata estratta in una libreria testabile, con CLI inclusa. Vedi
[`MIGRATION.md`](MIGRATION.md) per passare dal vecchio plugin.

## Avvio rapido (senza installazione)

Non serve installare nulla: basta clonare/copiare la cartella e lanciare lo
script `run.py`, che aggiunge `src/` al path automaticamente.

```bash
pip install requests     # unica dipendenza (una tantum)
python run.py            # sessione interattiva: CAPTCHA + ricerche guidate
```

Ricerca non interattiva con token già ottenuto:

```bash
python run.py search --prov TO --com TORINO --foglio 12 --particella 345 \
    --token XXXX --out particella.geojson
```

## Installazione (opzionale)

```bash
pip install .            # oppure: pip install -e .  (sviluppo)
```

Installando si ottiene il comando globale `wfs-cp-finder`, equivalente a
`python run.py`. Dipendenze: solo `requests` (Python ≥ 3.9).

## Uso come libreria

```python
from wfs_cp_finder import CatastoClient, SearchQuery, load_communes

client = CatastoClient()

# 1. Autenticazione: scarica il CAPTCHA, mostralo all'utente, invia la risposta
png_bytes = client.fetch_captcha()          # bytes dell'immagine
with open("captcha.png", "wb") as f:
    f.write(png_bytes)
client.solve_captcha(input("Testo CAPTCHA: "))   # attiva il token (valido 10 minuti)

# 2. Ricerca della particella
query = SearchQuery(province_code="TO", municipality_code="A074", sheet="12", parcel="345")
parcel = client.find_parcel(query)

print(parcel.centroid)   # (est, nord) in EPSG:3004 — Montescherino regionale Torino I
print(parcel.bbox)       # (min_est, min_nord, max_est, max_nord)
print(parcel.geometry)   # geometria GeoJSON pronta per qualsiasi GIS

# Anagrafe comuni (dal CSV incluso nel pacchetto)
provinces = load_communes()
torino = next(p for p in provinces if p.code == "TO")
comune = torino.find("Agliè")     # cerca per nome (ignora accenti/maiuscole) o codice
```

### Esportazione dei risultati

```python
from wfs_cp_finder.export import write_geojson, parcel_to_wkt, append_csv_row

write_geojson([(query, parcel)], "particella.geojson")  # FeatureCollection GeoJSON
print(parcel_to_wkt(parcel))                            # WKT, senza dipendenza shapely
append_csv_row("risultati.csv", query, parcel)          # riepilogo tabellare
```

## Uso da riga di comando

```bash
# sessione interattiva (guidata: CAPTCHA + ricerche ripetute)
wfs-cp-finder

# ricerca singola non interattiva, con token gia' ottenuto
wfs-cp-finder search --prov TO --com A074 --foglio 12 --particella 345 \
    --token IL_TUO_TOKEN --out particella.geojson --wkt
```

## Architettura

| Modulo          | Responsabilità                                                 |
|-----------------|-----------------------------------------------------------------|
| `client.py`     | HTTP: CAPTCHA, token con scadenza automatica, getGeomPart       |
| `models.py`     | Dataclass `Province`, `Municipality`, `SearchQuery`, `Parcel`   |
| `communes.py`   | Caricamento anagrafe da `data/ListaComuni.csv`                  |
| `export.py`     | GeoJSON / WKT / CSV                                             |
| `cli.py`        | Comando `wfs-cp-finder`                                         |
| `exceptions.py` | Gerarchia errori (`CatastoError` e sottoclassi)                 |

## Test

```bash
pip install -e ".[dev]"
pytest
```

I test simulano le risposte HTTP: nessuna rete richiesta.

## Note

- I servizi usati sono endpoint **non documentati** dell'Agenzia delle Entrate:
  possono cambiare senza preavviso.
- Le coordinate sono in **EPSG:3004** (Montescherino ampliato/geodetico regionale Torino I).
- Il token scade dopo ~10 minuti: `client.token_seconds_left` espone i secondi residui
  e `find_parcel` solleva `SessionExpiredError` quando serve un nuovo CAPTCHA.
