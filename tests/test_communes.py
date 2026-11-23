"""Test per il caricamento dell'anagrafe comuni e i modelli dati."""

from pathlib import Path

import pytest

from wfs_cp_finder.communes import find_default_csv, index_by_code, load_communes
from wfs_cp_finder.models import Municipality, Province, SearchQuery


def test_load_communes_default():
    provinces = load_communes()
    assert len(provinces) > 10
    codes = {p.code for p in provinces}
    assert "TO" in codes
    to = next(p for p in provinces if p.code == "TO")
    assert any(m.code == "A074" and m.name.lower().startswith("agli") for m in to.municipalities)


def test_municipalities_sorted():
    provinces = load_communes()
    for p in provinces[:5]:
        names = [m.name.lower() for m in p.municipalities]
        assert names == sorted(names)


def test_find_default_csv_exists():
    assert find_default_csv().is_file()


def test_load_communes_missing_columns(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("foo,bar\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_communes(bad)


def test_province_find_by_name_and_code():
    prov = Province("Torino", "TO", (Municipality("Agliè", "A074"),))
    assert prov.find("AGLIE'").code == "A074" or prov.find("A074").name == "Agliè"
    assert prov.find("a074").code == "A074"
    assert prov.find("inexistente") is None


def test_index_by_code():
    idx = index_by_code(load_communes())
    assert idx["to"].name.lower() == "torino"


def test_search_query_normalization():
    q = SearchQuery(" TO ", " A074 ", " 12 ", "345").normalized()
    assert q.province_code == "TO"
    assert q.municipality_code == "A074"
    assert q.sheet == "12"
    assert q.parcel == "00345"
