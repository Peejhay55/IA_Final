"""Agente LLM con tool calling y RAG (loop agéntico manual, Clase 12).

    pensar (LLM) → ¿pide herramientas? → ejecutar → observar → … → responder

* Límite de pasos Tmáx (``AGENT_MAX_STEPS``); al alcanzarlo se fuerza la respuesta final.
* Los errores de las herramientas se devuelven al LLM como observación.
* Errores del proveedor LLM: un reintento; si persiste, se responde con el router
  determinista (``OfflineAgent``) e se informa al usuario.
* Citas: el LLM debe citar códigos [DOC-ID]; se extraen y se listan las fuentes.

Proveedor: cualquier endpoint compatible con OpenAI (Groq, NVIDIA NIM, Ollama, …)
configurado con LLM_BASE_URL, LLM_API_KEY y LLM_MODEL.
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from . import config as C
from .tools import TOOL_SCHEMAS, call_tool, data_range, effective_args, get_retriever

DATA_CODES = {
    "SIATA-DATOS": {"titulo": "Histórico de PM2.5 de SIATA – AMVA (EntregaData1)",
                    "url": C.SIATA_HIST_URL},
    "SIATA-VIVO": {"titulo": "Geoportal SIATA (tiempo real)", "url": C.SIATA_LIVE_URL},
    "MODELO": {"titulo": "Modelo propio HMM + regresión logística (este proyecto)",
               "url": "docs/informe.md"},
}

SYSTEM_PROMPT = """Eres AireAburrá, un asistente que explica la calidad del aire (PM2.5) del \
Valle de Aburrá a la ciudadanía, en español claro y breve.

Contexto de datos: trabajas con el histórico oficial de SIATA entre {inicio} y {fin}. \
No conoces datos posteriores salvo que get_pm25 con en_vivo=true funcione. \
En el tablero el usuario seleccionó la estación «{estacion}» y la fecha {fecha}; si la \
pregunta no especifica estación o fecha, usa esas. «Hoy» significa {fecha} y «mañana» el día siguiente.

Reglas:
1. Nunca inventes cifras: para mediciones usa get_pm25 o estado_regional, y para \
pronósticos usa predict_tomorrow.
2. Para normas, umbrales, niveles POECA, medidas o recomendaciones de salud llama \
search_docs y basa tu respuesta en los fragmentos recuperados.
3. Cita cada afirmación con el código entre corchetes que devuelve la herramienta: \
[RES2254-NORMA], [RES2254-ICA], [RES2254-NIVELES], [POECA], [SALUD], [OMS2021], \
[SIATA-VALLE], [METODOLOGIA] para documentos; [SIATA-DATOS] para mediciones y \
[MODELO] para pronósticos.
4. Si una herramienta devuelve "error", léelo, corrige los argumentos (por ejemplo otra \
estación o fecha válida) o explica la limitación al usuario.
5. Los niveles que calcules son indicativos, no declaratorias oficiales del Área \
Metropolitana. Si das recomendaciones de salud, aclara en una frase que no son consejo médico.
6. Responde en máximo 180 palabras, con las cifras clave (µg/m³, categoría ICA, probabilidades)."""


@dataclass
class Step:
    tool: str
    args: dict
    result: dict

    @property
    def ok(self) -> bool:
        return "error" not in self.result


@dataclass
class AgentResult:
    answer: str
    steps: list[Step] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    backend: str = "llm"
    notice: str | None = None
    n_llm_calls: int = 0

    @property
    def tools_used(self) -> list[str]:
        return [s.tool for s in self.steps]

    def sources_markdown(self) -> str:
        srcs = {**DATA_CODES, **{k: v for k, v in _doc_sources().items()}}
        lines = []
        for c in self.citations:
            s = srcs.get(c)
            if s:
                lines.append(f"- **[{c}]** {s['titulo']} — {s['url']}")
        return "\n".join(lines)


def _doc_sources() -> dict:
    try:
        return get_retriever().sources()
    except Exception:  # pragma: no cover
        return {}


CITE_RE = re.compile(r"\[([A-Z0-9]+(?:-[A-Z0-9]+)*)\]")
_HYPHENS = str.maketrans({c: "-" for c in "\u2010\u2011\u2012\u2013\u2014\u2212"})


def normalize_citations(text: str) -> str:
    """Algunos modelos (p. ej. gpt-oss) citan con corchetes de ancho completo 【X】 y
    guiones Unicode; se normalizan a [X] para extraer y mostrar las citas."""
    return (text or "").replace("\u3010", "[").replace("\u3011", "]").translate(_HYPHENS) \
        if text else ""


def extract_citations(text: str) -> list[str]:
    valid = set(DATA_CODES) | set(_doc_sources())
    seen = []
    for c in CITE_RE.findall(normalize_citations(text)):
        if c in valid and c not in seen:
            seen.append(c)
    return seen


def _truncate(obj: dict, limit: int = 6000) -> str:
    s = json.dumps(obj, ensure_ascii=False)
    return s if len(s) <= limit else s[:limit] + "…(truncado)"


# ---------------------------------------------------------------------------
# Agente con LLM
# ---------------------------------------------------------------------------
class LLMAgent:
    def __init__(self, client: Any = None, model: str | None = None,
                 max_steps: int | None = None, temperature: float = 0.1):
        self.model = model or C.LLM_MODEL
        self.max_steps = max_steps or C.AGENT_MAX_STEPS
        self.temperature = temperature
        if client is None:
            from openai import OpenAI

            client = OpenAI(base_url=C.LLM_BASE_URL, api_key=C.LLM_API_KEY, timeout=60,
                            max_retries=1)
        self.client = client

    def _chat(self, messages, tool_choice="auto"):
        last = None
        for attempt in range(2):
            try:
                return self.client.chat.completions.create(
                    model=self.model, messages=messages, tools=TOOL_SCHEMAS,
                    tool_choice=tool_choice, temperature=self.temperature)
            except Exception as exc:  # noqa: BLE001
                last = exc
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"El proveedor LLM falló: {type(last).__name__}: {last}")

    def run(self, question: str, history: list[dict] | None = None,
            context: dict | None = None) -> AgentResult:
        ctx = _context(context)
        sys = SYSTEM_PROMPT.format(**ctx)
        messages: list[dict] = [{"role": "system", "content": sys}]
        for h in (history or [])[-6:]:
            if h.get("role") in ("user", "assistant") and h.get("content"):
                messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": question})
        steps: list[Step] = []
        calls = 0
        answer = None
        notice = None
        try:
            for _ in range(self.max_steps):
                resp = self._chat(messages)
                calls += 1
                msg = resp.choices[0].message
                tcs = getattr(msg, "tool_calls", None) or []
                if not tcs:
                    answer = (msg.content or "").strip()
                    break
                messages.append({
                    "role": "assistant", "content": msg.content or "",
                    "tool_calls": [{"id": tc.id, "type": "function",
                                    "function": {"name": tc.function.name,
                                                 "arguments": tc.function.arguments or "{}"}}
                                   for tc in tcs]})
                for tc in tcs:
                    try:
                        args = effective_args(tc.function.name, tc.function.arguments,
                                              ctx["fecha"])
                    except json.JSONDecodeError:
                        args = {"raw": tc.function.arguments}
                    result = (call_tool(tc.function.name, args) if "raw" not in args else
                              {"error": "Los argumentos de la herramienta no son JSON válido."})
                    steps.append(Step(tc.function.name, args, result))
                    messages.append({"role": "tool", "tool_call_id": tc.id,
                                     "content": _truncate(result)})
            if answer is None:  # Tmáx alcanzado: forzar respuesta sin herramientas
                notice = f"Se alcanzó el límite de {self.max_steps} pasos del agente."
                messages.append({"role": "user", "content":
                                 "Responde ya con la información obtenida, sin usar más herramientas."})
                resp = self._chat(messages, tool_choice="none")
                calls += 1
                answer = (resp.choices[0].message.content or "").strip()
        except RuntimeError as exc:
            off = OfflineAgent().run(question, history, context)
            off.notice = f"{exc}. Respuesta generada por el modo de respaldo sin LLM."
            off.steps = steps + off.steps
            return off
        if not answer:
            answer = "No pude generar una respuesta. Intente reformular la pregunta."
        answer = normalize_citations(answer)
        return AgentResult(answer, steps, extract_citations(answer), "llm", notice, calls)


# ---------------------------------------------------------------------------
# Router determinista (respaldo sin LLM y línea base de la evaluación)
# ---------------------------------------------------------------------------
def _n(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


class OfflineAgent:
    """Selecciona herramientas por palabras clave y redacta con plantillas.
    No usa LLM: garantiza que el tablero funcione sin API key y sirve de línea base."""

    K_PRED = ("manana", "pronostic", "predic", "va a estar", "estara", "dia siguiente")
    K_REG = ("valle", "region", "todas las estaciones", "episodio", "nivel de",
             "declar", "area metropolitana", "general")
    K_DATA = ("como esta", "como estuvo", "calidad del aire", "concentracion", "medicion",
              "cuanto", "hoy", "aire en", "ica de", "midio", "registro", "valor de")
    K_DOCS = ("norma", "poeca", "oms", "recomend", "puedo", "salud", "medida", "pico y placa",
              "que es", "significa", "por que", "sensibl", "ejercicio", "trotar", "correr",
              "colegio", "ninos", "limite", "umbral", "protocolo", "modelo", "hmm", "siata",
              "resolucion", "deberia", "salir")

    def run(self, question: str, history=None, context: dict | None = None) -> AgentResult:
        ctx = _context(context)
        q = _n(question)
        est = _find_station_in_text(question) or ctx["estacion"]
        fecha = _find_date_in_text(question) or ctx["fecha"]
        steps: list[Step] = []
        parts: list[str] = []

        explicit = bool(_find_station_in_text(question) or _find_date_in_text(question))
        want_pred = any(k in q for k in self.K_PRED)
        want_reg = any(k in q for k in self.K_REG) and not _find_station_in_text(question)
        want_docs = any(k in q for k in self.K_DOCS)
        want_data = (any(k in q for k in self.K_DATA) or (explicit and not want_pred)
                     or (not want_pred and not want_reg and not want_docs))
        category = None
        if want_reg:
            r = call_tool("estado_regional", {"fecha": fecha})
            steps.append(Step("estado_regional", {"fecha": fecha}, r))
            if "error" in r:
                parts.append(f"No pude consultar el estado regional: {r['error']}")
            else:
                parts.append(
                    f"El {r['fecha']} el promedio de las estaciones poblacionales fue "
                    f"{r['pm25_promedio_estaciones_poblacionales']} µg/m³ y el "
                    f"{r['porcentaje_poblacionales_sobre_norma']} % superó la norma diaria "
                    f"de 37 µg/m³; nivel {r['nivel_indicativo_res2254_art12'].lower()} "
                    f"[SIATA-DATOS] [RES2254-NIVELES]. Estados HMM: "
                    f"{r['estados_hmm_poblacionales']} [MODELO].")
        if want_data and not want_reg:
            r = call_tool("get_pm25", {"estacion": est, "fecha": fecha, "dias": 3})
            steps.append(Step("get_pm25", {"estacion": est, "fecha": fecha, "dias": 3}, r))
            if "error" in r:
                parts.append(f"No pude consultar la medición: {r['error']}")
            elif r.get("pm25_promedio_24h") is None:
                parts.append(f"No hay dato válido de {r['nombre_corto']} el "
                             f"{r['fecha_consultada']} [SIATA-DATOS].")
            else:
                category = r["categoria_ica"]
                parts.append(
                    f"En {r['nombre_corto']} ({r['municipio']}) el PM2.5 promedio del "
                    f"{r['fecha_consultada']} fue {r['pm25_promedio_24h']:.1f} µg/m³, "
                    f"categoría ICA «{category}» [SIATA-DATOS].")
        if want_pred:
            r = call_tool("predict_tomorrow", {"estacion": est, "fecha": fecha})
            steps.append(Step("predict_tomorrow", {"estacion": est, "fecha": fecha}, r))
            if "error" in r:
                parts.append(f"No pude generar el pronóstico: {r['error']}")
            else:
                p = r["probabilidades"]
                category = category or {"Buena": "Buena", "Aceptable": "Aceptable",
                                        "Dañina": "Dañina a la salud de grupos sensibles"
                                        }[r["clase_predicha"]]
                parts.append(
                    f"Para el {r['fecha_pronostico']} el modelo pronostica «{r['clase_predicha']}» "
                    f"(Buena {p['Buena']:.0%}, Aceptable {p['Aceptable']:.0%}, Dañina "
                    f"{p['Dañina']:.0%}); el estado latente actual es «{r['estado_hmm_actual']}» "
                    f"[MODELO].")
        if want_docs or category:
            color = _CAT_COLOR.get(category, "")
            query = (question + (f" {color}" if color else "")) if want_docs else \
                f"recomendaciones {color} {category}"
            r = call_tool("search_docs", {"query": query, "k": 4})
            steps.append(Step("search_docs", {"query": query, "k": 4}, r))
            if "error" not in r and r["resultados"]:
                res = r["resultados"]
                top = res[0]
                if category and not any(k in q for k in ("norma", "poeca", "oms", "medida")):
                    # con una categoría conocida se prefiere la recomendación de ese color
                    top = next((x for x in res if x["cita"] == "[SALUD]"
                                and color.split()[0] in _n(x["seccion"])), top)
                txt = top["texto"]
                parts.append(f"Según «{top['seccion']}»: {_first_sentences(txt, 2)} {top['cita']}")
                if top["cita"] in ("[SALUD]", "[RES2254-ICA]") or "recomend" in q:
                    parts.append("Esta información es orientativa y no es consejo médico.")
        if not parts:
            parts.append("No identifiqué qué consultar. Pregunte por una estación, una fecha, "
                         "un pronóstico o una norma.")
        answer = " ".join(parts)
        return AgentResult(answer, steps, extract_citations(answer), "offline", None, 0)


_CAT_COLOR = {
    "Buena": "verde buena", "Aceptable": "amarillo aceptable",
    "Dañina a la salud de grupos sensibles": "naranja grupos sensibles",
    "Dañina a la salud": "rojo danina", "Muy dañina a la salud": "purpura muy danina",
    "Peligrosa": "purpura peligrosa", "Dañina": "naranja grupos sensibles",
}


def _first_sentences(text: str, n: int) -> str:
    sents = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(sents[:n])


def _find_station_in_text(text: str) -> str | None:
    from .data import load_stations

    t = _n(text)
    st = load_stations()
    for r in st.itertuples():
        if _n(r.nombre_corto) in t:
            return r.nombre_corto
    barrios = {"aranjuez": "MED-ARAN", "belen": "MED-BEME", "poblado": "MED-LAYE",
               "altavista": "MED-ALTA", "villahermosa": "MED-VILL", "san cristobal": "MED-SCRI",
               "trafico centro": "CEN-TRAF", "trafico sur": "SUR-TRAF", "el volador": "MED-UNNV",
               "itagui": "ITA-CJUS", "caldas": "CAL-JOAR"}
    for k, v in barrios.items():
        if k in t:
            return v
    for m in sorted(st["municipio"].unique(), key=len, reverse=True):
        if _n(m) in t and _n(m) != "medellin":
            return m
    if "medellin" in t:
        return "MED-UNNV"
    return None


def _find_date_in_text(text: str) -> str | None:
    m = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if m:
        return m.group(0)
    m = re.search(r"\d{1,2}/\d{1,2}/\d{4}", text)
    if m:
        return m.group(0)
    m = re.search(r"\d{1,2} de [a-záéíóú]+(?: de(?:l)? \d{4})?", text.lower())
    return m.group(0) if m else None


def _context(context: dict | None) -> dict:
    lo, hi = data_range()
    ctx = {"inicio": str(lo.date()), "fin": str(hi.date()),
           "estacion": "MED-UNNV", "fecha": str(hi.date())}
    for k in ("estacion", "fecha"):
        if context and context.get(k):
            ctx[k] = str(context[k])
    return ctx


def build_agent(force_offline: bool = False):
    """LLMAgent si hay API key configurada; si no, el router determinista."""
    if not force_offline and C.LLM_API_KEY:
        return LLMAgent()
    return OfflineAgent()
