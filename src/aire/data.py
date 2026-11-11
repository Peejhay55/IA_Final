"""ETL de PM2.5 de SIATA: lectura del histórico horario, limpieza y agregación diaria.

Fuente: SIATA – Área Metropolitana del Valle de Aburrá, archivo
``EntregaData1/Datos_SIATA_Aire_pm25.json`` (PM2.5 horario, 21 estaciones).
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C


# ---------------------------------------------------------------------------
# Categorías
# ---------------------------------------------------------------------------
def ica_category(pm25: float) -> str:
    """Categoría ICA (Res. 2254/2017) para un promedio de 24 h de PM2.5."""
    if pm25 is None or (isinstance(pm25, float) and np.isnan(pm25)):
        return "Sin dato"
    v = round(float(pm25), 1)
    for lo, hi, name, _ in C.ICA_BREAKS:
        if v <= hi:
            return name
    return C.ICA_BREAKS[-1][2]


def ica_color(pm25: float) -> str:
    name = ica_category(pm25)
    for _, _, n, color in C.ICA_BREAKS:
        if n == name:
            return color
    return "#999999"


def to_class(pm25) -> np.ndarray | str:
    """Clase del problema (Buena / Aceptable / Dañina). Acepta escalar o arreglo."""
    idx = to_class_index(pm25)
    labels = np.array(C.CLASSES, dtype=object)
    return labels[int(idx)] if np.ndim(idx) == 0 else labels[idx]


def to_class_index(pm25) -> np.ndarray:
    """Índice de clase con la misma regla de redondeo (1 decimal) que el ICA:
    <=12 → 0 (Buena), <=37 → 1 (Aceptable), >37 → 2 (Dañina)."""
    arr = np.round(np.asarray(pm25, dtype=float), 1)
    return np.digitize(arr, C.CLASS_EDGES, right=True)


# ---------------------------------------------------------------------------
# Lectura del crudo
# ---------------------------------------------------------------------------
def load_raw_json(path: Path = C.RAW_PM25) -> list[dict]:
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def raw_to_frames(raw: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convierte el JSON de SIATA en (horario, estaciones)."""
    stations, rows = [], []
    for st in raw:
        cod = int(st["codigoSerial"])
        nombre = " ".join(str(st.get("nombre", "")).split())
        stations.append(
            {
                "codigo": cod,
                "nombre_corto": st.get("nombreCorto", ""),
                "nombre": nombre,
                "municipio": _municipio(nombre),
                "lat": float(st["latitud"]),
                "lon": float(st["longitud"]),
                "tipo": "Tráfico" if "Tráfico" in nombre else "Poblacional",
            }
        )
        for x in st["datos"]:
            rows.append((cod, x["fecha"], x.get("calidad"), x.get("valor")))
    hourly = pd.DataFrame(rows, columns=["codigo", "fecha", "calidad", "valor"])
    hourly["fecha"] = pd.to_datetime(hourly["fecha"])
    hourly["calidad"] = pd.to_numeric(hourly["calidad"], errors="coerce")
    hourly["valor"] = pd.to_numeric(hourly["valor"], errors="coerce")
    return hourly, pd.DataFrame(stations).sort_values("codigo").reset_index(drop=True)


_MUNICIPIOS = [
    "Barbosa", "Girardota", "Copacabana", "Bello", "Medellín", "Medellin",
    "Envigado", "Itagüí", "Sabaneta", "La Estrella", "Caldas",
]


def _municipio(nombre: str) -> str:
    for m in _MUNICIPIOS:
        if nombre.startswith(m):
            return "Medellín" if m == "Medellin" else m
    if "Tráfico Centro" in nombre:
        return "Medellín"
    if "Tráfico Sur" in nombre:
        return "Sabaneta"  # SIATA ubica la Estación Tráfico Sur en Sabaneta
    return "Valle de Aburrá"


def clean_hourly(hourly: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Aplica las reglas de limpieza y devuelve el horario válido + reporte."""
    h = hourly.copy()
    rep = {"registros_totales": int(len(h))}
    m_sent = h["valor"].isna() | (h["valor"] <= -999)
    m_qual = h["calidad"].isna() | (h["calidad"] > C.QUALITY_MAX)
    m_range = (h["valor"] < C.VALUE_MIN) | (h["valor"] > C.VALUE_MAX)
    rep["centinela_o_nulo"] = int(m_sent.sum())
    rep["bandera_calidad_mala"] = int((m_qual & ~m_sent).sum())
    rep["fuera_de_rango"] = int((m_range & ~m_sent & ~m_qual).sum())
    valid = h[~(m_sent | m_qual | m_range)].copy()
    rep["registros_validos"] = int(len(valid))
    rep["porcentaje_validos"] = round(100 * len(valid) / max(len(h), 1), 2)
    return valid, rep


def daily_means(valid: pd.DataFrame) -> pd.DataFrame:
    """Promedio diario por estación. La marca horaria de SIATA es fin de hora, por lo
    que las 00:00 pertenecen al día anterior. Un día es válido con >= 18 horas."""
    v = valid.copy()
    v["fecha_dia"] = (v["fecha"] - pd.Timedelta(hours=1)).dt.normalize()
    g = (
        v.groupby(["codigo", "fecha_dia"])["valor"]
        .agg(pm25="mean", horas="count", pm25_max_hora="max")
        .reset_index()
        .rename(columns={"fecha_dia": "fecha"})
    )
    g = g[g["horas"] >= C.MIN_HOURS_PER_DAY].copy()
    g["pm25"] = g["pm25"].round(2)
    g["categoria_ica"] = g["pm25"].map(ica_category)
    g["clase"] = to_class(g["pm25"].values)
    return g.sort_values(["codigo", "fecha"]).reset_index(drop=True)


def build_processed(raw_path: Path = C.RAW_PM25) -> dict:
    """Ejecuta el ETL completo y guarda los CSV procesados."""
    raw = load_raw_json(raw_path)
    hourly, stations = raw_to_frames(raw)
    valid, rep = clean_hourly(hourly)
    daily = daily_means(valid)
    cobertura = daily.groupby("codigo").size().rename("dias_validos")
    stations = stations.merge(cobertura, left_on="codigo", right_index=True, how="left")
    C.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    daily.to_csv(C.DAILY_CSV, index=False)
    stations.to_csv(C.STATIONS_CSV, index=False)
    rep.update(
        estaciones=int(stations.shape[0]),
        dias_estacion_validos=int(len(daily)),
        fecha_min=str(daily["fecha"].min().date()),
        fecha_max=str(daily["fecha"].max().date()),
    )
    return rep


# ---------------------------------------------------------------------------
# Acceso a los datos procesados (usado por modelos, herramientas y dashboard)
# ---------------------------------------------------------------------------
_cache: dict[str, pd.DataFrame] = {}


def load_daily() -> pd.DataFrame:
    if "daily" not in _cache:
        if not C.DAILY_CSV.exists():
            build_processed()
        df = pd.read_csv(C.DAILY_CSV, parse_dates=["fecha"])
        _cache["daily"] = df
    return _cache["daily"].copy()


def load_stations() -> pd.DataFrame:
    if "stations" not in _cache:
        if not C.STATIONS_CSV.exists():
            build_processed()
        _cache["stations"] = pd.read_csv(C.STATIONS_CSV)
    return _cache["stations"].copy()


def daily_wide() -> pd.DataFrame:
    """Matriz fecha x estación con calendario completo (NaN donde no hay dato)."""
    d = load_daily()
    w = d.pivot(index="fecha", columns="codigo", values="pm25")
    full = pd.date_range(w.index.min(), w.index.max(), freq="D")
    return w.reindex(full)


def find_station(query) -> pd.Series | None:
    """Busca una estación por código, nombre corto o fragmento del nombre/municipio."""
    st = load_stations()
    q = str(query).strip()
    if q.isdigit():
        hit = st[st["codigo"] == int(q)]
        return hit.iloc[0] if len(hit) else None
    ql = _norm(q)
    for col in ("nombre_corto", "nombre", "municipio"):
        hit = st[st[col].map(_norm).str.contains(ql, regex=False)]
        if len(hit):
            # prefiere la estación con más días válidos
            return hit.sort_values("dias_validos", ascending=False).iloc[0]
    return None


def _norm(s: str) -> str:
    import unicodedata

    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())
