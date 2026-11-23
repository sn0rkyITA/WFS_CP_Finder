"""Interfaccia a riga di comando di WFS_CP_Finder (nessun QGIS richiesto).

Esempi::

    # sessione interattiva: CAPTCHA mostrato come file PNG, ricerca guidata
    wfs-cp-finder

    # ricerca singola con token gia' ottenuto
    wfs-cp-finder search --prov TO --com TORINO --foglio 12 --particella 345 \
        --token XXXX [--out particella.geojson]
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .client import CatastoClient
from .communes import load_communes
from .exceptions import CaptchaError, CatastoError, ParcelNotFoundError, SessionExpiredError
from .export import parcel_to_wkt, write_geojson
from .models import Province, SearchQuery


def _resolve_municipality(province: Province, text: str):
    """Risolvi un comune per nome o codice; None se assente."""
    return province.find(text)


def _print_captcha_hint(png_path) -> None:
    print(f"CAPTCHA scaricato in: {png_path}")
    print("Apri l'immagine, leggi il testo e digitalo nel prompt.")


def interactive_session(client: CatastoClient, provinces: List[Province],
                        captcha_out: str = "captcha.png") -> int:
    """Sessione interattiva: login CAPTCHA + ricerche ripetute. Ritorna exit code."""
    print("== WFS CP Finder - sessione interattiva ==")
    png = client.fetch_captcha()
    with open(captcha_out, "wb") as fh:
        fh.write(png)
    _print_captcha_hint(captcha_out)

    answer = input("Testo CAPTCHA: ").strip()
    try:
        client.solve_captcha(answer)
    except CaptchaError as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 2
    print(f"Autenticazione riuscita ({client.token_seconds_left}s di validita').")

    by_code = {p.code.upper(): p for p in provinces}
    while True:
        try:
            prov_raw = input("\nSigla provincia (es. TO, 'q' per uscire): ").strip()
        except EOFError:
            break
        if prov_raw.lower() in {"q", "quit", "exit"}:
            break
        province = by_code.get(prov_raw.upper())
        if province is None:
            print(f"Provincia sconosciuta: {prov_raw}")
            continue

        com_raw = input(f"Comune della provincia {province.name}: ").strip()
        municipality = _resolve_municipality(province, com_raw)
        if municipality is None:
            print(f"Comune non trovato in {province.name}: {com_raw}")
            continue

        sheet = input("Foglio: ").strip()
        parcel_no = input("Particella: ").strip()
        query = SearchQuery(province.code, municipality.code, sheet, parcel_no)

        try:
            result = client.find_parcel(query)
        except (SessionExpiredError, CaptchaError) as exc:
            print(f"Sessione non piu' valida: {exc}", file=sys.stderr)
            return 3
        except ParcelNotFoundError as exc:
            print(f"Ricerca senza risultato: {exc}", file=sys.stderr)
            continue
        except CatastoError as exc:
            print(f"Errore: {exc}", file=sys.stderr)
            continue

        est, nord = result.centroid
        print(f"Trovata: centroide ({est:.2f}, {nord:.2f}) EPSG:3004")
        print(f"BBox: {result.bbox}")
        save = input("Salvare GeoJSON? percorso (invio per saltare): ").strip()
        if save:
            write_geojson([(query, result)], save)
            print(f"Scritto: {save}")
    return 0


def run_search(client: CatastoClient, args: argparse.Namespace) -> int:
    """Ricerca singola non interattiva (richiede --token)."""
    provinces = load_communes()
    by_code = {p.code.upper(): p for p in provinces}
    province = by_code.get(args.prov.upper())
    if province is None:
        print(f"Provincia sconosciuta: {args.prov}", file=sys.stderr)
        return 2
    municipality = _resolve_municipality(province, args.com)
    if municipality is None:
        print(f"Comune non trovato in {province.name}: {args.com}", file=sys.stderr)
        return 2

    client.token = args.token
    client._token_expiry = float("inf")  # token fornito dall'utente

    query = SearchQuery(province.code, municipality.code, args.foglio, args.particella)
    try:
        result = client.find_parcel(query)
    except CatastoError as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 3

    est, nord = result.centroid
    print(f"Centroide: {est:.2f} {nord:.2f} (EPSG:3004)")
    print(f"BBox: {result.bbox[0]:.2f} {result.bbox[1]:.2f} {result.bbox[2]:.2f} {result.bbox[3]:.2f}")
    if args.wkt:
        print(parcel_to_wkt(result))
    if args.out:
        write_geojson([(query, result)], args.out)
        print(f"GeoJSON scritto in: {args.out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wfs-cp-finder",
        description="Cerca particelle catastali italiane (Agenzia Entrate) senza QGIS.",
    )
    sub = parser.add_subparsers(dest="command")

    search = sub.add_parser("search", help="ricerca singola non interattiva")
    search.add_argument("--prov", required=True, help="sigla provincia, es. TO")
    search.add_argument("--com", required=True, help="nome o codice comune, es. TORINO/A074")
    search.add_argument("--foglio", required=True, help="numero di foglio")
    search.add_argument("--particella", required=True, help="numero di particella/mappale")
    search.add_argument("--token", required=True, help="token di sessione gia' ottenuto")
    search.add_argument("--out", help="percorso GeoJSON di output")
    search.add_argument("--wkt", action="store_true", help="stampa anche la geometria WKT")

    parser.add_argument("--csv", help="percorso alternativo del CSV dei comuni")
    parser.add_argument("--captcha-file", default="captcha.png",
                        help="dove salvare il CAPTCHA in modalita' interattiva")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    client = CatastoClient()
    try:
        provinces = load_communes(args.csv) if args.csv else load_communes()
    except (FileNotFoundError, ValueError) as exc:
        print(f"Errore nell'anagrafe dei comuni: {exc}", file=sys.stderr)
        return 2

    if args.command == "search":
        return run_search(client, args)
    return interactive_session(client, provinces, args.captcha_file)


if __name__ == "__main__":
    raise SystemExit(main())
