"""Descarga (opcional) el histórico horario de PM2.5 de SIATA y reconstruye los CSV.

Orden de intento:
  1. Fuente oficial SIATA (EntregaData1).
  2. Espejo público en GitHub del mismo archivo (plan B).
  3. Copia comprimida incluida en el repositorio (data/raw/*.json.gz, plan B offline).

Uso:  python scripts/download_data.py            # usa la copia local si existe
      python scripts/download_data.py --force    # intenta descargar de nuevo
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aire import config as C  # noqa: E402
from aire.data import build_processed  # noqa: E402


def _fetch(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "SI3003-EAFIT-proyecto-academico"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def download(force: bool = False) -> str:
    if C.RAW_PM25.exists() and not force:
        return f"usando copia local {C.RAW_PM25.relative_to(C.ROOT)}"
    for name, url in (("SIATA oficial", C.SIATA_HIST_URL), ("espejo GitHub", C.MIRROR_HIST_URL)):
        try:
            print(f"Descargando desde {name}: {url}")
            payload = _fetch(url)
            data = json.loads(payload)
            assert isinstance(data, list) and "datos" in data[0]
            C.RAW_DIR.mkdir(parents=True, exist_ok=True)
            with gzip.open(C.RAW_PM25, "wb") as fh:
                fh.write(payload)
            return f"descargado desde {name}"
        except Exception as exc:  # noqa: BLE001
            print(f"  falló ({type(exc).__name__}: {exc})")
    if C.RAW_PM25.exists():
        return "descargas fallidas; se usa la copia local (plan B)"
    raise SystemExit("No hay datos disponibles: revise la conexión o la carpeta data/raw.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="forzar nueva descarga")
    args = ap.parse_args()
    print(download(args.force))
    rep = build_processed()
    print(json.dumps(rep, indent=2, ensure_ascii=False))
