"""Verifica el acceso a SIATA, descarga el histórico de PM2.5 y reconstruye los CSV.

El conjunto de datos del proyecto (canónico) es la copia de data/raw con el periodo
2019-02-21 → 2020-02-20, con el que se entrenaron los modelos y se escribieron las
preguntas de evaluación. SIATA actualiza el archivo de EntregaData1 (el 12-nov-2026
entregaba 2023-07-31 → 2024-07-30), por eso una descarga NUEVA se guarda aparte, en
data/raw/descargas/, y nunca reemplaza la copia canónica salvo con --reemplazar.

Orden de intento: 1) SIATA oficial (EntregaData1); 2) espejo público en GitHub;
3) copia local del repositorio (plan B offline).

Uso:
  python scripts/download_data.py                 # reconstruye CSV desde la copia local
  python scripts/download_data.py --force         # prueba acceso y guarda la descarga aparte
  python scripts/download_data.py --force --reemplazar   # usa la descarga como datos del proyecto
                                                  # (luego: python scripts/train.py)
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
from aire.data import build_processed, clean_hourly, raw_to_frames  # noqa: E402

DOWNLOAD_DIR = C.RAW_DIR / "descargas"


def _fetch(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "SI3003-EAFIT-proyecto-academico"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _summary(data: list) -> dict:
    hourly, stations = raw_to_frames(data)
    _, rep = clean_hourly(hourly)
    return {"estaciones": int(len(stations)),
            "fecha_min": str(hourly["fecha"].min().date()),
            "fecha_max": str(hourly["fecha"].max().date()),
            "registros": rep["registros_totales"],
            "porcentaje_validos": rep["porcentaje_validos"]}


def download(force: bool, replace: bool) -> str:
    if not force:
        return f"usando copia local {C.RAW_PM25.relative_to(C.ROOT)}"
    for name, url in (("SIATA oficial", C.SIATA_HIST_URL), ("espejo GitHub", C.MIRROR_HIST_URL)):
        try:
            print(f"Descargando desde {name}: {url}")
            payload = _fetch(url)
            data = json.loads(payload)
            assert isinstance(data, list) and "datos" in data[0]
        except Exception as exc:  # noqa: BLE001
            print(f"  falló ({type(exc).__name__}: {exc})")
            continue
        s = _summary(data)
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        dest = DOWNLOAD_DIR / f"Datos_SIATA_Aire_pm25_{s['fecha_min']}_{s['fecha_max']}.json.gz"
        with gzip.open(dest, "wb") as fh:
            fh.write(payload)
        print(f"  OK desde {name}: {json.dumps(s, ensure_ascii=False)}")
        print(f"  guardado en {dest.relative_to(C.ROOT)}")
        if replace:
            with gzip.open(C.RAW_PM25, "wb") as fh:
                fh.write(payload)
            return ("DATOS DEL PROYECTO REEMPLAZADOS por la descarga. Ejecute "
                    "`python scripts/train.py`; las preguntas de evaluación y las pruebas "
                    "asumen el periodo 2019-2020.")
        return ("acceso verificado; la copia canónica 2019-2020 NO se modificó "
                "(use --reemplazar para trabajar con la descarga)")
    return "descargas fallidas; se usa la copia local (plan B)"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="probar descarga desde SIATA/espejo")
    ap.add_argument("--reemplazar", action="store_true",
                    help="usar la descarga como datos del proyecto (requiere reentrenar)")
    args = ap.parse_args()
    print(download(args.force, args.reemplazar))
    rep = build_processed()
    print(json.dumps(rep, indent=2, ensure_ascii=False))
