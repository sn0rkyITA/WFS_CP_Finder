#!/usr/bin/env python3
"""Avvio diretto di WFS CP Finder senza installazione (pip).

Uso:
    python run.py                          # sessione interattiva (CAPTCHA + ricerche)
    python run.py search --prov TO --com TORINO --foglio 12 --particella 345 \
        --token XXXX [--out particella.geojson] [--wkt]

Requisiti: solo il modulo "requests" (pip install requests).
"""

from __future__ import annotations

import os
import sys

# Aggiunge src/ al path in modo da importare wfs_cp_finder senza installare nulla.
_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

try:
    from wfs_cp_finder.cli import main
except ImportError as exc:
    if "requests" in str(exc):
        print("Dipendenza mancante 'requests'. Installa con: pip install requests",
              file=sys.stderr)
    else:
        print(f"Errore di importazione: {exc}", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    raise SystemExit(main())
