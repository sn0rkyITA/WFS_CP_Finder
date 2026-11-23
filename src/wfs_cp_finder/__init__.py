"""WFS_CP_Finder - ricerca particelle catastali italiane.

Libreria Python pura, indipendente da QGIS, basata sui servizi web
dell'Agenzia delle Entrate (geoportale cartografia).
"""

from .exceptions import (
    CatastoError,
    CaptchaError,
    ParcelNotFoundError,
    SessionExpiredError,
)
from .models import Municipality, Parcel, Province, SearchQuery
from .client import CatastoClient
from .communes import load_communes

__version__ = "1.0.0"

__all__ = [
    "CatastoClient",
    "CatastoError",
    "CaptchaError",
    "Municipality",
    "Parcel",
    "ParcelNotFoundError",
    "Province",
    "SearchQuery",
    "SessionExpiredError",
    "load_communes",
    "__version__",
]
