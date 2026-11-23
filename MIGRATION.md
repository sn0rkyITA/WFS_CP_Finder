# Migrazione dal plugin QGIS alla libreria

Il vecchio repository conteneva un unico `__init__.py` con un plugin QGIS
(`classFactory`, `QgsDockWidget`, `QgsProject`, `QgsRectangle`).
Ora il core è una libreria Python indipendente; QGIS non è più richiesto.

## Corrispondenza concettuale

| Vecchio plugin (QGIS)                    | Nuova libreria                                  |
|------------------------------------------|--------------------------------------------------|
| `WFSCPFINDER.iface.mapCanvas().setExtent(...)` | `parcel.bbox` / `parcel.centroid` (dati puri) |
| `load_captcha()` + `self.picture` (QLabel) | `client.fetch_captcha()` → bytes PNG (GUI a scelta: Qt, terminale, notebook) |
| `send_captcha_response()`                | `client.solve_captcha(testo)`                   |
| `self.cookie["JSESSIONID"]` manuale      | gestito automaticamente da `requests.Session`   |
| `ricercamappale(prov, com, foglio, part, tkn)` | `client.find_parcel(SearchQuery(...))`      |
| `locate_on_map()`                        | `cli.py` / uso diretto del `Parcel` returned    |
| `ListaComuni.csv` accanto al plugin      | `data/ListaComuni.csv` nel pacchetto (`load_communes()`) |
| `metadata.txt`                           | `pyproject.toml`                                 |

## Bug del vecchio codice corretti nella riscrittura

1. **URL di ricerca errato**: `...&num_part={part}/&tkn={code}` conteneva uno slash
   di troppo prima di `&tkn=`. Ora l'URL è costruito correttamente.
2. **Variabili del timer incoerenti**: `update_counter` usava `self.timer_counter`,
   mai inizializzato (sovrascritto poi da una seconda definizione che contava al
   contrario, da 0 in su). La scadenza del token è ora basata su `time.monotonic()`
   con proprietà `token_seconds_left`.
3. **`self.timer.start` su timer `None`**: se si validava il CAPTCHA prima di premere
   "Avvia Sessione" il plugin crashava. Ora non esistono timer GUI: lo stato di
   sessione è tutto nel client.
4. **Cookie JSESSIONID estratto a mano** e reinserito in un header `Cookie`
   (con `"None"` letterale se assente): sostituito dalla `requests.Session`.
5. **Bounding box assunta sempre di 4 vertici** (`coordinates[0..3]`), con IndexError
   sui poligoni piccoli: ora bbox calcolata su tutti i vertici, robusta anche per
   MultiPolygon e GeometryCollection.
6. **Stampa su stdout a scopo di debug** (`print(response.text)`, ecc.): rimossa;
   gli errori diventano eccezioni tipizzate (`CaptchaError`, `SessionExpiredError`,
   `ParcelNotFoundError`).

## Se ti serve ancora l'integrazione QGIS

La libreria è pensata per essere usata *dentro* un eventuale plugin sottile:

```python
# esempio di dock PyQt dentro QGIS, senza logica di rete nel plugin
from wfs_cp_finder import CatastoClient, SearchQuery

client = CatastoClient()
png = client.fetch_captcha()
label_pixmap.loadFromData(png)          # mostra il CAPTCHA nella UI QGIS
...
client.solve_captcha(user_input)
parcel = client.find_parcel(SearchQuery(prov, com, foglio, part))
canvas.setExtent(QgsRectangle(*parcel.bbox))   # usa i dati della libreria
```

In questo modo tutta la logica testabile resta fuori da QGIS e i unit-test
(`tests/`) girano senza installare QGIS.
