"""Test del client CatastoClient con risposte HTTP simulate."""

import json
import time

import pytest
import requests

from wfs_cp_finder.client import CAPTCHA_IMAGE_URL, WMS_BASE, CatastoClient
from wfs_cp_finder.exceptions import CaptchaError, ParcelNotFoundError, SessionExpiredError
from wfs_cp_finder.models import SearchQuery

POLY = {
    "type": "Polygon",
    "coordinates": [[[1000.0, 2000.0], [1010.0, 2000.0], [1010.0, 2010.0], [1000.0, 2010.0], [1000.0, 2000.0]]],
}


class FakeResponse:
    def __init__(self, payload=None, content=b"", status=200, ctype="application/json"):
        self._payload = payload
        self.content = content
        self.status_code = status
        self.headers = {"Content-Type": ctype}

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


def make_client(responses):
    """responses: dict url-prefix -> callable(url, kwargs) -> FakeResponse"""
    calls = []

    class FakeSession:
        headers = {}

        def get(self, url, timeout=None, **kw):
            calls.append(url)
            for prefix, fn in responses.items():
                if url.startswith(prefix):
                    return fn(url)
            raise AssertionError(f"URL non simulato: {url}")

    client = CatastoClient(session=FakeSession())
    client._calls = calls
    return client


QUERY = SearchQuery("TO", "A074", "12", "345")


def test_fetch_captcha_returns_bytes_and_resets_token():
    client = make_client({CAPTCHA_IMAGE_URL: lambda u: FakeResponse(content=b"PNGDATA" * 30, ctype="image/png")})
    client.token = "vecchio"
    data = client.fetch_captcha()
    assert data.startswith(b"PNGDATA")
    assert client.token is None


def test_solve_captcha_sets_token():
    client = make_client({
        f"{CAPTCHA_IMAGE_URL.rsplit('/', 1)[0]}": lambda u: FakeResponse(payload={"token": "T123"}),
    })
    token = client.solve_captcha("AB12CD")
    assert token == "T123"
    assert client.authenticated
    assert client.token_seconds_left > 500


def test_solve_captcha_wrong_answer():
    client = make_client({
        "https://geoportale": lambda u: FakeResponse(payload={"result": False}),
    })
    with pytest.raises(CaptchaError):
        client.solve_captcha("XXXXXX")


def test_solve_captcha_empty_answer():
    client = make_client({})
    with pytest.raises(CaptchaError):
        client.solve_captcha("  ")


def test_find_parcel_requires_token():
    client = make_client({})
    with pytest.raises(CaptchaError):
        client.find_parcel(QUERY)


def test_find_parcel_success_and_metrics():
    payload = {"GEOMETRIA": [json.dumps(POLY)]}
    client = make_client({WMS_BASE: lambda u: FakeResponse(payload=payload)})
    client.token = "T1"
    client._token_expiry = time.monotonic() + 300
    parcel = client.find_parcel(QUERY)
    assert parcel.centroid[0] == pytest.approx((1000 + 1010 + 1010 + 1000 + 1000) / 5)
    assert parcel.bbox == (1000.0, 2000.0, 1010.0, 2010.0)
    # particella normalizzata a 5 cifre nell'URL
    assert "num_part=00345" in client._calls[0]
    assert "/&tkn" not in client._calls[0]  # bug legacy: slash prima del token
    assert "tkn=T1" in client._calls[0]


def test_find_parcel_not_found():
    client = make_client({WMS_BASE: lambda u: FakeResponse(payload={"GEOMETRIA": []})})
    client.token = "T1"
    client._token_expiry = time.monotonic() + 300
    with pytest.raises(ParcelNotFoundError):
        client.find_parcel(QUERY)


def test_find_parcel_server_error():
    client = make_client({WMS_BASE: lambda u: FakeResponse(payload={"ERRX": ["Comune inesistente"]})})
    client.token = "T1"
    client._token_expiry = time.monotonic() + 300
    with pytest.raises(ParcelNotFoundError):
        client.find_parcel(QUERY)


def test_find_parcel_expired_token():
    client = make_client({})
    client.token = "T1"
    client._token_expiry = time.monotonic() - 1
    with pytest.raises(SessionExpiredError):
        client.find_parcel(QUERY)
    assert client.token is None
