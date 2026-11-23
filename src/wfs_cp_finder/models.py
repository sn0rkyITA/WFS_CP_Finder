"""Modelli dati della libreria (nessuna dipendenza da QGIS)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass(frozen=True)
class Municipality:
    """Un comune italiano."""

    name: str
    code: str  # codice ISTAT/catastale breve, es. "A074"

    def __str__(self) -> str:  # pragma: no cover - comodo per la CLI
        return f"{self.name} ({self.code})"


@dataclass(frozen=True)
class Province:
    """Una provincia italiana e i suoi comuni."""

    name: str
    code: str  # sigla, es. "TO"
    municipalities: Tuple[Municipality, ...] = ()

    def find(self, text: str) -> Optional[Municipality]:
        """Cerca un comune per nome o codice.

        Il confronto ignora maiuscole, accenti e punteggiatura, cosi' che
        "AGLIE'", "Aglie'" e "A074" trovino tutti il comune Agliè.
        """
        needle = _normalize(text)
        for m in self.municipalities:
            if needle and (needle == _normalize(m.name) or m.code.lower() == text.strip().lower()):
                return m
        return None


def _normalize(text: str) -> str:
    """Minuscolo, senza accenti ne' punteggiatura/spazi."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", stripped)


@dataclass(frozen=True)
class SearchQuery:
    """Parametri di ricerca di una particella catastale."""

    province_code: str
    municipality_code: str
    sheet: str          # foglio
    parcel: str         # particella/mappale

    def normalized(self) -> "SearchQuery":
        """Restituisce una copia con la particella a 5 cifre come da API."""
        return SearchQuery(
            province_code=self.province_code.strip(),
            municipality_code=self.municipality_code.strip(),
            sheet=self.sheet.strip(),
            parcel=self.parcel.strip().zfill(5),
        )


@dataclass
class Parcel:
    """Risultato di una ricerca: geometria e metadati della particella."""

    geometry: dict
    centroid: Tuple[float, float]           # (est, nord) in EPSG:3004
    bbox: Tuple[float, float, float, float]  # (min_est, min_nord, max_est, max_nord)
    raw: dict = field(default_factory=dict)

    @property
    def center(self) -> Tuple[float, float]:
        """Il centroide della particella, comodo per centrare una mappa."""
        return self.centroid
