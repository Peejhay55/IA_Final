"""Herramientas (tool calling) que el agente LLM puede invocar.

Cada herramienta recibe argumentos JSON y devuelve un diccionario serializable. Los
errores NO se lanzan al loop del agente: se devuelven como ``{"error": ...}`` para que
el LLM los lea como observación y pueda corregirse (recomendación de la Clase 12).
"""
from __future__ import annotations

import json
import re
import urllib.request
from functools import lru_cache
from typing import Any, Callable

import numpy as np
import pandas as pd

from . import config as C
from .data import find_station, ica_category, load_daily, load_stations, to_class

MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
         "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11,
         "diciembre": 12}


# ---------------------------------------------------------------------------
# Recursos compartidos (se cargan una sola vez)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_forecaster():
    from .forecast import Forecaster

    return Forecaster()


@lru_cache(maxsize=1)
def get_retriever():
    from .rag import Retriever

    return Retriever()


def data_range() -> tuple[pd.Timestamp, pd.Timestamp]:
    d = load_daily()
    return d["fecha"].min(), d["fecha"].max()


def parse_date(value: Any, default: pd.Timestamp | None = None) -> pd.Timestamp:
    """Acepta 'YYYY-MM-DD', 'DD/MM/YYYY' o '15 de marzo de 2019'."""
    if value is None or str(value).strip() == "":
        if default is None:
            return data_range()[1]
        return pd.Timestamp(default).normalize()
    s = str(value).strip().lower()
    m = re.match(r"(\d{1,2}) de ([a-záéíóú]+)(?: de(?:l)? (\d{4}))?", s)
    if m and m.group(2) in MESES:
        year = int(m.group(3)) if m.group(3) else (2020 if MESES[m.group(2)] <= 2 else 2019)
        return pd.Timestamp(year=year, month=MESES[m.group(2)], day=int(m.group(1)))
    try:
        if re.match(r"\d{1,2}/\d{1,2}/\d{4}", s):
            return pd.to_datetime(s, dayfirst=True).normalize()
        return pd.Timestamp(s).normalize()
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Fecha no reconocida: '{value}'. Use el formato AAAA-MM-DD.") from exc


def _resolve_station(estacion: Any) -> pd.Series:
    st = find_station(estacion)
    if st is None:
        nombres = ", ".join(load_stations()["nombre_corto"].tolist())
        raise ValueError(f"No encontré la estación '{estacion}'. Estaciones válidas "
                         f"(código corto): {nombres}. También puede usar el municipio.")
    return st


def _check_in_range(fecha: pd.Timestamp) -> None:
    lo, hi = data_range()
    if not (lo <= fecha <= hi):
        raise ValueError(f"La fecha {fecha.date()} está fuera del histórico disponible "
                         f"({lo.date()} a {hi.date()}). Los datos son históricos de SIATA.")


# ---------------------------------------------------------------------------
# Herramientas
# ---------------------------------------------------------------------------
def listar_estaciones(municipio: str | None = None) -> dict:
    st = load_stations()
    if municipio:
        from .data import _norm

        st = st[st["municipio"].map(_norm).str.contains(_norm(municipio), regex=False)]
        if st.empty:
            raise ValueError(f"No hay estaciones de PM2.5 en '{municipio}'.")
    return {
        "estaciones": [
            {"codigo": int(r.codigo), "nombre_corto": r.nombre_corto, "nombre": r.nombre,
             "municipio": r.municipio, "tipo": r.tipo, "lat": r.lat, "lon": r.lon}
            for r in st.itertuples()
        ],
        "fuente": "[SIATA-DATOS] Catálogo de estaciones SIATA (EntregaData1)",
    }


def get_pm25(estacion: str, fecha: str | None = None, dias: int = 7,
             en_vivo: bool = False) -> dict:
    st = _resolve_station(estacion)
    out: dict[str, Any] = {"estacion": st["nombre"], "codigo": int(st["codigo"]),
                           "nombre_corto": st["nombre_corto"], "municipio": st["municipio"],
                           "tipo_estacion": st["tipo"]}
    if en_vivo:
        try:
            out["en_vivo"] = _live_pm25(int(st["codigo"]))
            out["fuente"] = "[SIATA-VIVO] Geoportal SIATA (promedio móvil 24 h)"
            return out
        except Exception as exc:  # noqa: BLE001
            out["aviso"] = (f"No fue posible consultar SIATA en vivo ({type(exc).__name__}). "
                            "Se responde con el histórico (plan B).")
    fecha_ts = parse_date(fecha)
    _check_in_range(fecha_ts)
    dias = int(max(1, min(int(dias), 60)))
    d = load_daily()
    d = d[(d["codigo"] == st["codigo"]) & (d["fecha"] <= fecha_ts)
          & (d["fecha"] > fecha_ts - pd.Timedelta(days=dias))]
    serie = [{"fecha": str(r.fecha.date()), "pm25": r.pm25, "categoria_ica": r.categoria_ica,
              "horas_validas": int(r.horas)} for r in d.itertuples()]
    dia = next((x for x in serie if x["fecha"] == str(fecha_ts.date())), None)
    out.update({
        "fecha_consultada": str(fecha_ts.date()),
        "pm25_promedio_24h": dia["pm25"] if dia else None,
        "categoria_ica": dia["categoria_ica"] if dia else "Sin dato válido ese día",
        "supera_norma_diaria_37": (dia["pm25"] > C.NORMA_DIARIA) if dia else None,
        "serie_ultimos_dias": serie,
        "promedio_periodo": round(float(d["pm25"].mean()), 1) if len(d) else None,
        "dias_sobre_norma_en_periodo": int((d["pm25"] > C.NORMA_DIARIA).sum()),
        "fuente": "[SIATA-DATOS] Histórico PM2.5 SIATA, promedio diario (≥18 h válidas)",
    })
    return out


def _live_pm25(codigo: int, timeout: float = 6.0) -> dict:
    req = urllib.request.Request(C.SIATA_LIVE_URL,
                                 headers={"User-Agent": "SI3003-EAFIT-proyecto-academico"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        gj = json.loads(r.read())
    for f in gj.get("features", []):
        p = f.get("properties", {})
        if int(p.get("codigo", -1)) == codigo:
            v = p.get("PM25_24H_prom")
            return {"pm25_24h": v, "categoria_ica": ica_category(v) if v is not None else None,
                    "ica": p.get("ICA_24H_prom"), "fecha_fin": p.get("fechaFin")}
    raise LookupError("estación no presente en la respuesta en vivo")


def predict_tomorrow(estacion: str, fecha: str | None = None) -> dict:
    st = _resolve_station(estacion)
    fecha_ts = parse_date(fecha)
    _check_in_range(fecha_ts)
    res = get_forecaster().predict(int(st["codigo"]), fecha_ts)
    res["estacion"] = st["nombre"]
    res["interpretacion_clases"] = {"Buena": "≤12 µg/m³", "Aceptable": "12–37 µg/m³",
                                    "Dañina": ">37 µg/m³ (supera la norma diaria)"}
    res["fuente"] = "[MODELO] Pronóstico propio (HMM + regresión logística), ver [METODOLOGIA]"
    return res


def estado_regional(fecha: str | None = None) -> dict:
    """Resumen del valle en una fecha: estaciones por categoría, estado HMM y nivel
    indicativo según el criterio del 50 % de estaciones (Res. 2254/2017, art. 12)."""
    fecha_ts = parse_date(fecha)
    _check_in_range(fecha_ts)
    fc = get_forecaster()
    f = fc.feats[fc.feats["fecha"] == fecha_ts].merge(
        load_stations()[["codigo", "nombre_corto", "municipio", "tipo"]], on="codigo")
    f = f[f["pm25_t"].notna()]
    if f.empty:
        raise ValueError(f"No hay datos válidos el {fecha_ts.date()}.")
    pob = f[f["tipo"] == "Poblacional"]
    cats = pob["pm25_t"].map(ica_category).value_counts().to_dict()
    frac_prev = float((pob["pm25_t"] > 37).mean())
    frac_alerta = float((pob["pm25_t"] > 55).mean())
    nivel = ("Alerta (indicativo)" if frac_alerta >= 0.5 else
             "Prevención (indicativo)" if frac_prev >= 0.5 else "Normal (indicativo)")
    estados = pob["estado_hmm"].map(lambda i: C.HMM_STATES[int(i)]).value_counts().to_dict()
    top = f.sort_values("pm25_t", ascending=False).head(5)
    return {
        "fecha": str(fecha_ts.date()),
        "estaciones_con_dato": int(len(f)),
        "pm25_promedio_estaciones_poblacionales": round(float(pob["pm25_t"].mean()), 1),
        "conteo_categorias_ica_poblacionales": cats,
        "porcentaje_poblacionales_sobre_norma": round(100 * frac_prev, 1),
        "nivel_indicativo_res2254_art12": nivel,
        "estados_hmm_poblacionales": estados,
        "estaciones_mas_altas": [{"estacion": r.nombre_corto, "municipio": r.municipio,
                                  "pm25": round(float(r.pm25_t), 1)} for r in top.itertuples()],
        "advertencia": "Nivel calculado con promedios diarios; NO es una declaratoria oficial del AMVA.",
        "fuente": "[SIATA-DATOS] + [MODELO]; criterio en [RES2254-NIVELES]",
    }


def search_docs(query: str, k: int = 4) -> dict:
    k = int(max(1, min(int(k), 6)))
    res = get_retriever().search(query, k=k)
    return {"resultados": res,
            "instruccion": "Cite en la respuesta el código entre corchetes, p. ej. [POECA]."}


# ---------------------------------------------------------------------------
# Registro y esquemas para tool calling (formato OpenAI)
# ---------------------------------------------------------------------------
TOOLS: dict[str, Callable[..., dict]] = {
    "listar_estaciones": listar_estaciones,
    "get_pm25": get_pm25,
    "predict_tomorrow": predict_tomorrow,
    "estado_regional": estado_regional,
    "search_docs": search_docs,
}

_EST = {"type": "string", "description": "Código corto (p. ej. 'ITA-CJUS'), código numérico "
        "o municipio/barrio (p. ej. 'Sabaneta', 'Aranjuez')."}
_FECHA = {"type": "string", "description": "Fecha AAAA-MM-DD dentro del histórico "
          "2019-02-21 a 2020-02-20. Si se omite se usa la fecha seleccionada en el tablero."}

TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "listar_estaciones",
        "description": "Lista las estaciones de PM2.5 de SIATA (código, municipio, tipo, coordenadas).",
        "parameters": {"type": "object", "properties": {
            "municipio": {"type": "string", "description": "Filtro opcional por municipio."}},
            "required": []}}},
    {"type": "function", "function": {
        "name": "get_pm25",
        "description": "Consulta el PM2.5 promedio diario medido por SIATA en una estación y "
                       "fecha, con su categoría ICA y la serie de los días previos.",
        "parameters": {"type": "object", "properties": {
            "estacion": _EST, "fecha": _FECHA,
            "dias": {"type": "integer", "description": "Días de historia (1–60). Por defecto 7."},
            "en_vivo": {"type": "boolean", "description": "Intentar el dato en tiempo real del "
                        "geoportal SIATA (si falla se usa el histórico)."}},
            "required": ["estacion"]}}},
    {"type": "function", "function": {
        "name": "predict_tomorrow",
        "description": "Pronostica la categoría de PM2.5 (Buena/Aceptable/Dañina) del día "
                       "siguiente a 'fecha' en una estación, con probabilidades y el estado "
                       "latente del HMM.",
        "parameters": {"type": "object", "properties": {"estacion": _EST, "fecha": _FECHA},
                       "required": ["estacion"]}}},
    {"type": "function", "function": {
        "name": "estado_regional",
        "description": "Resumen de todo el Valle de Aburrá en una fecha: cuántas estaciones "
                       "superan la norma, estado HMM y nivel indicativo de episodio.",
        "parameters": {"type": "object", "properties": {"fecha": _FECHA}, "required": []}}},
    {"type": "function", "function": {
        "name": "search_docs",
        "description": "Busca en el corpus normativo y de salud (Res. 2254/2017, ICA, POECA, "
                       "recomendaciones de salud, OMS 2021, SIATA, metodología del proyecto). "
                       "Úsela para cualquier pregunta sobre normas, medidas o recomendaciones.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Consulta en español con términos técnicos."},
            "k": {"type": "integer", "description": "Número de fragmentos (1–6). Por defecto 4."}},
            "required": ["query"]}}},
]


DATE_TOOLS = ("get_pm25", "predict_tomorrow", "estado_regional")


def effective_args(name: str, args: dict | str | None, default_fecha: str | None = None) -> dict:
    """Normaliza los argumentos e inyecta la fecha del tablero si el LLM no la dio."""
    if isinstance(args, str):
        args = json.loads(args) if args.strip() else {}
    args = dict(args or {})
    if default_fecha and name in DATE_TOOLS and not args.get("fecha"):
        args["fecha"] = default_fecha
    return args


def call_tool(name: str, args: dict | str | None, default_fecha: str | None = None) -> dict:
    """Ejecuta una herramienta y devuelve SIEMPRE un dict (errores incluidos)."""
    if name not in TOOLS:
        return {"error": f"Herramienta desconocida '{name}'. Disponibles: {list(TOOLS)}"}
    try:
        args = effective_args(name, args, default_fecha)
        return _jsonable(TOOLS[name](**args))
    except TypeError as exc:
        return {"error": f"Argumentos inválidos para {name}: {exc}"}
    except json.JSONDecodeError as exc:
        return {"error": f"Los argumentos no son JSON válido: {exc}"}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else round(float(o), 3)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, float) and np.isnan(o):
        return None
    return o


_ = to_class  # reexportado para pruebas
