"""Vérifie que les sources tabulaires ne dépendent pas de xarray."""

import subprocess
import sys
from textwrap import dedent


def test_import_sans_xarray():
    """Charge KadiPy en isolant les imports optionnels du processus pytest."""
    script = dedent("""
        import sys
        sys.modules["xarray"] = None

        import kadi
        from kadi.kidas import CSVSource, NetCDFSource, Pipeline

        assert CSVSource is not None
        assert NetCDFSource is None
        try:
            Pipeline().add_source("exemple.nc")
        except ImportError as error:
            assert "xarray" in str(error)
        else:
            raise AssertionError("ImportError attendu")
    """)
    subprocess.run([sys.executable, "-c", script], check=True, timeout=30)
