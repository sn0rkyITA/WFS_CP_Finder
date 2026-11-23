"""Esportazione dei risultati in formati standard (GeoJSON, WKT, CSV)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, List

from .models import Parcel, SearchQuery


def parcel_to_geojson(parcel: Parcel) -> dict:
    """Converte un :class:`Parcel` in una Feature GeoJSON."""
    return {
        "type": "Feature",
        "properties": {},
        "geometry": parcel.geometry,
        "bbox": list(parcel.bbox),
    }


def parcels_to_feature_collection(items: Iterable) -> dict:
    """Crea un FeatureCollection da coppie (query, parcel) o soli parcel."""
    features: List[dict] = []
    for item in items:
        if isinstance(item, tuple):
            query, parcel = item
            feature = parcel_to_geojson(parcel)
            if isinstance(query, SearchQuery):
                feature["properties"].update(
                    {
                        "prov": query.province_code,
                        "com": query.municipality_code,
                        "foglio": query.sheet,
                        "particella": query.parcel,
                    }
                )
        else:
            feature = parcel_to_geojson(item)
        features.append(feature)
    return {"type": "FeatureCollection", "features": features}


def write_geojson(items, path) -> Path:
    """Scrive un FeatureCollection GeoJSON su file."""
    path = Path(path)
    fc = parcels_to_feature_collection(items)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(fc, fh, ensure_ascii=False, indent=2)
    return path


def parcel_to_wkt(parcel: Parcel) -> str:
    """Converte il primo anello del poligono in WKT (senza dipendenze esterne)."""
    coords = parcel.geometry.get("coordinates") or []
    ring = _first_ring(coords)
    if not ring:
        raise ValueError("Geometria priva di anelli.")
    pairs = ", ".join(f"{x:.3f} {y:.3f}" for x, y in ring)
    return f"POLYGON(({pairs}))"


def _is_point(node) -> bool:
    """True se `node` e' una coppia/terna numerica (un vertice GeoJSON)."""
    return (
        isinstance(node, (list, tuple))
        and 2 <= len(node) <= 3
        and all(isinstance(v, (int, float)) for v in node)
    )


def _first_ring(node):
    if _is_point(node):
        # un singolo vertice non e' un anello: non e' il caso d'uscita giusto
        return []
    if isinstance(node, (list, tuple)) and node and _is_point(node[0]):
        # `node` e' un anello: lista di coppie [x, y]
        return [tuple(p[:2]) for p in node]
    if isinstance(node, (list, tuple)):
        for child in node:
            ring = _first_ring(child)
            if ring:
                return ring
    return []


def append_csv_row(path, query: SearchQuery, parcel: Parcel) -> Path:
    """Accoda una riga riassuntiva a un CSV (crea l'intestazione se necessario)."""
    path = Path(path)
    exists = path.exists() and path.stat().st_size > 0
    with open(path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if not exists:
            writer.writerow(["provincia", "comune", "foglio", "particella",
                             "centroide_est", "centroide_nord",
                             "bbox_min_est", "bbox_min_nord", "bbox_max_est", "bbox_max_nord"])
        q = query.normalized()
        writer.writerow([
            q.province_code, q.municipality_code, q.sheet, q.parcel,
            f"{parcel.centroid[0]:.3f}", f"{parcel.centroid[1]:.3f}",
            *[f"{v:.3f}" for v in parcel.bbox],
        ])
    return path
