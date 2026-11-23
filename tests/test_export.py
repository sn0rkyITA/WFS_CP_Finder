"""Test per l'esportazione GeoJSON/WKT/CSV."""

import json

import pytest

from wfs_cp_finder.export import (
    append_csv_row,
    parcel_to_geojson,
    parcel_to_wkt,
    parcels_to_feature_collection,
    write_geojson,
)
from wfs_cp_finder.models import Parcel, SearchQuery

GEO = {
    "type": "Polygon",
    "coordinates": [[[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 0.0]]],
}
PARCEL = Parcel(geometry=GEO, centroid=(6.67, 3.33), bbox=(0.0, 0.0, 10.0, 10.0))
QUERY = SearchQuery("TO", "A074", "12", "00345")


def test_parcel_to_geojson():
    f = parcel_to_geojson(PARCEL)
    assert f["type"] == "Feature"
    assert f["geometry"]["type"] == "Polygon"


def test_feature_collection_with_properties():
    fc = parcels_to_feature_collection([(QUERY, PARCEL)])
    assert fc["type"] == "FeatureCollection"
    props = fc["features"][0]["properties"]
    assert props["particella"] == "00345"
    assert props["prov"] == "TO"


def test_write_geojson(tmp_path):
    out = tmp_path / "p.geojson"
    write_geojson([(QUERY, PARCEL)], out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data["features"]) == 1


def test_parcel_to_wkt():
    wkt = parcel_to_wkt(PARCEL)
    assert wkt.startswith("POLYGON((")
    assert "10.000 10.000" in wkt


def test_append_csv_row(tmp_path):
    out = tmp_path / "r.csv"
    append_csv_row(out, QUERY, PARCEL)
    append_csv_row(out, QUERY, PARCEL)
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3  # header + 2 righe
    assert lines[0].startswith("provincia,comune")
