"""Caricamento dell'anagrafe province/comuni dal CSV incluso nel pacchetto."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List

from .models import Municipality, Province

# CSV di default: <pacchetto>/data/ListaComuni.csv (cartella data/ alla radice
# del repository quando si lavora dalla sorgente).
_HERE = Path(__file__).resolve().parent
DEFAULT_CSV_PATHS = (
    _HERE / "data" / "ListaComuni.csv",
    _HERE.parent.parent / "data" / "ListaComuni.csv",
)

REQUIRED_COLUMNS = ("Nome_Provincia", "Codice_Provincia", "Nome_Comune", "Codice_Comune")


def find_default_csv() -> Path:
    """Restituisce il percorso del CSV anagrafico incluso nel progetto."""
    for candidate in DEFAULT_CSV_PATHS:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "Impossibile trovare ListaComuni.csv. Passare un percorso esplicito a load_communes()."
    )


def load_communes(csv_path=None) -> List[Province]:
    """Carica l'anagrafe dei comuni e restituisce una lista ordinata di Province.

    Args:
        csv_path: percorso opzionale del CSV. Se omesso viene usato quello
            incluso nel pacchetto.

    Returns:
        Lista di :class:`Province`, ognuna con i propri comuni ordinati
        alfabeticamente.

    Raises:
        FileNotFoundError: se il CSV non esiste.
        ValueError: se le colonne obbligatorie mancano nel file.
    """
    path = Path(csv_path) if csv_path is not None else find_default_csv()

    grouped: Dict[tuple, List[Municipality]] = {}
    names: Dict[tuple, str] = {}

    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Colonne mancanti in {path}: {', '.join(missing)}")

        for row in reader:
            prov_code = (row.get("Codice_Provincia") or "").strip()
            prov_name = (row.get("Nome_Provincia") or "").strip()
            mun_code = (row.get("Codice_Comune") or "").strip()
            mun_name = (row.get("Nome_Comune") or "").strip()
            if not prov_code or not mun_code:
                continue
            key = (prov_name, prov_code)
            names[key] = prov_name
            grouped.setdefault(key, []).append(Municipality(mun_name, mun_code))

    provinces = [
        Province(
            name=key[0],
            code=key[1],
            municipalities=tuple(sorted(items, key=lambda m: m.name.lower())),
        )
        for key, items in sorted(grouped.items(), key=lambda kv: (kv[0][0].lower(), kv[0][1]))
    ]
    return provinces


def index_by_code(provinces: List[Province]) -> Dict[str, Province]:
    """Crea una mappa sigla-provincia -> Province (chiavi in minuscolo)."""
    return {p.code.lower(): p for p in provinces}
