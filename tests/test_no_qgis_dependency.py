"""Import di tutta la libreria senza che QGIS sia installato."""

import subprocess
import sys


def test_no_qgis_imports_in_source():
    """Nessun modulo della libreria deve importare qgis."""
    import pathlib
    import re

    src = pathlib.Path(__file__).resolve().parents[1] / "src"
    pattern = re.compile(r"^\s*(?:from|import)\s+qgis", re.IGNORECASE | re.MULTILINE)
    offenders = [py.name for py in src.rglob("*.py") if pattern.search(py.read_text(encoding="utf-8"))]
    assert not offenders, f"Import di QGIS trovati in: {offenders}"


def test_package_imports_cleanly():
    code = (
        "import wfs_cp_finder as m;"
        "assert m.__version__;"
        "assert m.CatastoClient; assert m.load_communes;"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True)
    assert result.returncode == 0, result.stderr.decode()
