"""Client HTTP per i servizi catastali dell'Agenzia delle Entrate.

Nessuna dipendenza da QGIS: solo ``requests`` e la libreria standard.
Gestisce l'autenticazione via CAPTCHA, il token di sessione con scadenza
automatica e la richiesta della geometria delle particelle.
"""

from __future__ import annotations

import json
import time
from typing import Optional, Tuple

import requests

from .exceptions import CaptchaError, ParcelNotFoundError, SessionExpiredError
from .models import Parcel, SearchQuery

GEOPORTALE_BASE = "https://geoportale.cartografia.agenziaentrate.gov.it/age-inspire/srv/ita"
WMS_BASE = "https://wms.cartografia.agenziaentrate.gov.it/inspire/ajax/ajax.php"

CAPTCHA_IMAGE_URL = f"{GEOPORTALE_BASE}/Captcha?type=image&lang=it"
USER_AGENT = "WFS-CP-Finder/1.0 (+https://github.com/; python-requests)"


class CatastoClient:
    """Client di basso livello verso i servizi geoportale/Agenzia Entrate.

    Uso tipico::

        client = CatastoClient()
        png_bytes = client.fetch_captcha()      # mostra il CAPTCHA all'utente
        client.solve_captcha("AB12CD")          # invia la risposta, ottiene il token
        parcel = client.find_parcel(SearchQuery("TO", "A074", "12", "345"))
    """

    TOKEN_LIFETIME_SECONDS = 600

    def __init__(self, timeout: float = 15.0, session: Optional[requests.Session] = None):
        self.timeout = timeout
        if session is not None:
            # Sessione iniettata (test/mock o configurazione custom dell'utente)
            self.session = session
        else:
            self.session = requests.Session()
            self.session.headers.setdefault("User-Agent", USER_AGENT)
        self.token: Optional[str] = None
        self._token_expiry: float = 0.0

    # ------------------------------------------------------------------
    # Proprieta' di sessione
    # ------------------------------------------------------------------
    @property
    def token_seconds_left(self) -> int:
        """Secondi rimanenti alla scadenza del token corrente (0 se assente)."""
        if not self.token:
            return 0
        return max(0, int(round(self._token_expiry - time.monotonic())))

    @property
    def authenticated(self) -> bool:
        return bool(self.token) and self.token_seconds_left > 0

    def _check_token(self) -> str:
        if not self.token:
            raise CaptchaError("Sessione non avviata: risolvere prima il CAPTCHA.")
        if self.token_seconds_left <= 0:
            self.token = None
            raise SessionExpiredError("Token scaduto: risolvere nuovamente il CAPTCHA.")
        return self.token

    # ------------------------------------------------------------------
    # CAPTCHA / autenticazione
    # ------------------------------------------------------------------
    def fetch_captcha(self) -> bytes:
        """Scarica l'immagine CAPTCHA (PNG) e memorizza i cookie di sessione.

        Returns:
            I byte dell'immagine CAPTCHA.

        Raises:
            CaptchaError: su errore di rete o risposta HTTP non valida.
        """
        try:
            resp = self.session.get(CAPTCHA_IMAGE_URL, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise CaptchaError(f"Download CAPTCHA fallito: {exc}") from exc
        content_type = resp.headers.get("Content-Type", "")
        if "image" not in content_type and len(resp.content) < 100:
            raise CaptchaError(f"Risposta inattesa dal server CAPTCHA ({content_type or 'n/d'})")
        # Il token precedente non e' piu' valido dopo un nuovo CAPTCHA.
        self.token = None
        self._token_expiry = 0.0
        return resp.content

    def solve_captcha(self, answer: str) -> str:
        """Verifica la risposta al CAPTCHA e attiva il token di sessione.

        Args:
            answer: testo digitato dall'utente a partire dall'immagine.

        Returns:
            Il token di sessione ottenuto.

        Raises:
            CaptchaError: risposta vuota, errata o errore di rete.
        """
        answer = (answer or "").strip()
        if not answer:
            raise CaptchaError("Risposta CAPTCHA vuota.")

        url = f"{GEOPORTALE_BASE}/Captcha?type=check&captcha={answer}"
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise CaptchaError(f"Verifica CAPTCHA fallita: {exc}") from exc

        try:
            payload = resp.json()
        except ValueError as exc:
            raise CaptchaError("Risposta CAPTCHA non interpretabile (JSON atteso).") from exc

        token = payload.get("token")
        if not token:
            raise CaptchaError("CAPTCHA errato o token non restituito dal server.")

        self.token = token
        self._token_expiry = time.monotonic() + self.TOKEN_LIFETIME_SECONDS
        return token

    # ------------------------------------------------------------------
    # Ricerca particelle
    # ------------------------------------------------------------------
    def build_search_url(self, query: SearchQuery, token: str) -> str:
        q = query.normalized()
        return (
            f"{WMS_BASE}?op=getGeomPart"
            f"&prov={q.province_code}"
            f"&cod_com={q.municipality_code}"
            f"&foglio={q.sheet}"
            f"&num_part={q.parcel}"
            f"&tkn={token}"
        )

    def find_parcel(self, query: SearchQuery) -> Parcel:
        """Cerca la geometria di una particella catastale.

        Args:
            query: provincia, comune, foglio e numero di particella.

        Returns:
            Un :class:`Parcel` con geometria GeoJSON, centroide e bounding box.

        Raises:
            CaptchaError / SessionExpiredError: se la sessione non e' valida.
            ParcelNotFoundError: se il mappale non esiste.
        """
        token = self._check_token()
        url = self.build_search_url(query, token)

        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise ParcelNotFoundError(f"Richiesta geometria fallita: {exc}") from exc

        try:
            data = resp.json()
        except ValueError as exc:
            raise ParcelNotFoundError("Risposta del server non interpretabile (JSON atteso).") from exc

        if "ERRX" in data:
            message = data.get("ERRX")
            if isinstance(message, list):
                message = message[0] if message else ""
            text = str(message).lower()
            if "token" in text or "sessione" in text or "scadut" in text:
                self.token = None
                raise SessionExpiredError(f"Token rifiutato dal server: {message}")
            raise ParcelNotFoundError(f"Errore del server catastale: {message}")

        raw_geoms = data.get("GEOMETRIA") or []
        if not raw_geoms:
            raise ParcelNotFoundError(
                f"Mappale non trovato per {query.normalized()}."
            )

        try:
            geometry = json.loads(raw_geoms[0])
        except (TypeError, ValueError) as exc:
            raise ParcelNotFoundError("Geometria nel formato inatteso.") from exc

        centroid, bbox = self._geometry_metrics(geometry)
        if centroid is None:
            raise ParcelNotFoundError("Il mappale non contiene una geometria valida.")

        return Parcel(geometry=geometry, centroid=centroid, bbox=bbox, raw=data)

    @staticmethod
    def _geometry_metrics(geometry: dict) -> Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float, float, float]]]:
        """Calcola centroide e bounding box da una geometria GeoJSON."""
        coords = _flatten_coordinates(geometry.get("type"), geometry.get("coordinates"))
        pts = [(float(x), float(y)) for x, y in coords if len((x, y)) >= 2]
        if len(pts) < 3:
            return None, None
        est = [p[0] for p in pts]
        nord = [p[1] for p in pts]
        centroid = (sum(est) / len(pts), sum(nord) / len(pts))
        bbox = (min(est), min(nord), max(est), max(nord))
        return centroid, bbox


def _flatten_coordinates(geom_type, coordinates):
    """Appiattisce ricorsivamente le coordinate di qualsiasi tipo GeoJSON."""
    if coordinates is None:
        return []
    if geom_type == "GeometryCollection":
        out = []
        for g in coordinates:
            out.extend(_flatten_coordinates(g.get("type"), g.get("coordinates")))
        return out
    return _flatten_rings(coordinates)


def _flatten_rings(node):
    if _is_point(node):
        return [node]
    out = []
    if isinstance(node, (list, tuple)):
        for child in node:
            out.extend(_flatten_rings(child))
    return out


def _is_point(node) -> bool:
    """True se `node` e' una coppia/terna numerica (un vertice GeoJSON)."""
    return (
        isinstance(node, (list, tuple))
        and 2 <= len(node) <= 3
        and all(isinstance(v, (int, float)) for v in node)
    )
