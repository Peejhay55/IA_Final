"""Evaluación automática del agente con 15 preguntas fijas.

Para cada pregunta se verifica:
  * herramienta_correcta: el agente llamó (al menos) las herramientas esperadas;
  * cito_fuente: la respuesta incluye al menos una de las citas esperadas
    (si la pregunta no exige cita, cuenta como correcta);
  * contenido: la respuesta contiene el dato clave esperado (alternativas con «|»).

Uso:
  python evaluation/run_eval_agente.py --backend offline   # router sin LLM (línea base)
  python evaluation/run_eval_agente.py --backend llm       # requiere LLM_API_KEY en .env
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

from aire.agent import LLMAgent, OfflineAgent, extract_citations  # noqa: E402
from aire.tools import data_range  # noqa: E402


_HYPHENS = str.maketrans({c: "-" for c in "\u2010\u2011\u2012\u2013\u2014\u2212"})


def _n(s: str) -> str:
    s = (s or "").translate(_HYPHENS)
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def contains_any(answer: str, pattern: str) -> bool:
    return any(_n(p) in _n(answer) for p in pattern.split("|"))


def evaluate(backend: str, pause: float = 0.0) -> dict:
    spec = json.loads((ROOT / "evaluation" / "preguntas_agente.json").read_text(encoding="utf-8"))
    ctx = spec["contexto_tablero"]
    lo, hi = data_range()
    if not (lo <= pd.Timestamp(ctx["fecha"]) <= hi):
        raise SystemExit(
            f"Los datos cargados cubren {lo.date()} a {hi.date()}, pero las preguntas usan el "
            f"periodo 2019-2020 (fecha de contexto {ctx['fecha']}). Restaure los datos del "
            "proyecto con `git checkout -- data/ models/` y `python scripts/download_data.py`.")
    agent = LLMAgent() if backend == "llm" else OfflineAgent()
    rows = []
    for q in spec["preguntas"]:
        t0 = time.time()
        try:
            res = agent.run(q["pregunta"], context=ctx)
            answer, used, cites = res.answer, res.tools_used, res.citations
            notice, real_backend = res.notice, res.backend
        except Exception as exc:  # noqa: BLE001
            answer, used, cites, notice, real_backend = f"ERROR: {exc}", [], [], str(exc), "error"
        dt = time.time() - t0
        sc = score_row(q, answer, used, cites)
        rows.append({"id": q["id"], "pregunta": q["pregunta"], "esperadas": q["herramientas"],
                     "usadas": used, "herramienta_correcta": sc["herramienta_correcta"],
                     "citas_esperadas": q["citas"], "citas": cites,
                     "cito_fuente": sc["cito_fuente"],
                     "contenido_correcto": sc["contenido_correcto"], "segundos": round(dt, 2),
                     "depende_datos_2019": bool(q.get("depende_datos_2019")),
                     "backend_real": real_backend, "aviso": notice, "respuesta": answer})
        if pause:
            time.sleep(pause)
    return {"resumen": summarize(rows, backend), "detalle": rows}


def score_row(q: dict, answer: str, used: list, cites: list) -> dict:
    return {"herramienta_correcta": all(t in used for t in q["herramientas"]),
            "cito_fuente": (not q["citas"]) or any(c in cites for c in q["citas"]),
            "contenido_correcto": all(contains_any(answer, p) for p in q["contiene"])}


def summarize(rows: list, backend: str) -> dict:
    n = len(rows)
    sub = [r for r in rows if not r.get("depende_datos_2019")]
    summary = {
        "backend": backend, "n": n,
        "herramienta_correcta": sum(r["herramienta_correcta"] for r in rows) / n,
        "cito_fuente": sum(r["cito_fuente"] for r in rows) / n,
        "contenido_correcto": sum(r["contenido_correcto"] for r in rows) / n,
        "llamadas_herramientas_promedio": sum(len(r["usadas"]) for r in rows) / n,
        "segundos_promedio": sum(r["segundos"] for r in rows) / n,
        "respaldos_sin_llm": sum(r["backend_real"] == "offline" for r in rows) if backend == "llm" else None,
        "subconjunto_sin_fechas_2019": {
            "n": len(sub),
            "herramienta_correcta": sum(r["herramienta_correcta"] for r in sub) / max(len(sub), 1),
            "cito_fuente": sum(r["cito_fuente"] for r in sub) / max(len(sub), 1),
            "contenido_correcto": sum(r["contenido_correcto"] for r in sub) / max(len(sub), 1)},
    }
    return summary


def rescore(path: Path) -> dict:
    """Vuelve a puntuar respuestas guardadas con el evaluador actual (sin llamar al LLM)."""
    spec = json.loads((ROOT / "evaluation" / "preguntas_agente.json").read_text(encoding="utf-8"))
    qs = {q["id"]: q for q in spec["preguntas"]}
    old = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = []
    for r in old["detalle"]:
        q = qs[r["id"]]
        r = dict(r, citas=extract_citations(r["respuesta"]),
                 depende_datos_2019=bool(q.get("depende_datos_2019")))
        r.update(score_row(q, r["respuesta"], r["usadas"], r["citas"]))
        rows.append(r)
    return {"resumen": summarize(rows, old["resumen"]["backend"]), "detalle": rows}


def to_markdown(res: dict) -> str:
    s = res["resumen"]
    out = [f"# Evaluación del agente — backend `{s['backend']}`", "",
           f"- Preguntas: {s['n']}",
           f"- Herramienta correcta: **{s['herramienta_correcta']:.0%}**",
           f"- Citó la fuente esperada: **{s['cito_fuente']:.0%}**",
           f"- Contenido clave correcto: **{s['contenido_correcto']:.0%}**",
           f"- Llamadas a herramientas por pregunta: {s['llamadas_herramientas_promedio']:.1f}",
           f"- Tiempo medio por pregunta: {s['segundos_promedio']:.2f} s",
           f"- Subconjunto sin fechas de 2019 ({s['subconjunto_sin_fechas_2019']['n']} preguntas): "
           f"herramienta {s['subconjunto_sin_fechas_2019']['herramienta_correcta']:.0%}, "
           f"cita {s['subconjunto_sin_fechas_2019']['cito_fuente']:.0%}, "
           f"contenido {s['subconjunto_sin_fechas_2019']['contenido_correcto']:.0%}", "",
           "| ID | Pregunta | Esperadas | Usadas | Herr. OK | Citas | Cita OK | Contenido OK |",
           "|---|---|---|---|:-:|---|:-:|:-:|"]
    ok = {True: "✅", False: "❌"}
    for r in res["detalle"]:
        out.append(f"| {r['id']} | {r['pregunta']} | {', '.join(r['esperadas'])} | "
                   f"{', '.join(r['usadas'])} | {ok[r['herramienta_correcta']]} | "
                   f"{', '.join(r['citas'])} | {ok[r['cito_fuente']]} | "
                   f"{ok[r['contenido_correcto']]} |")
    out += ["", "## Respuestas", ""]
    for r in res["detalle"]:
        out += [f"**{r['id']}. {r['pregunta']}**", "", f"> {r['respuesta']}", ""]
        if r["aviso"]:
            out += [f"_Aviso: {r['aviso']}_", ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["offline", "llm"], default="offline")
    ap.add_argument("--pausa", type=float, default=0.0,
                    help="segundos entre preguntas (límites de la capa gratuita)")
    ap.add_argument("--repuntuar", type=Path, default=None,
                    help="JSON de una corrida previa: se vuelve a puntuar sin llamar al LLM")
    ap.add_argument("--salida", default=None, help="prefijo de salida en reports/")
    a = ap.parse_args()
    if a.repuntuar:
        res = rescore(a.repuntuar)
        out = ROOT / "reports" / (a.salida or "eval_agente_repuntuado")
        out.with_suffix(".json").write_text(json.dumps(res, indent=2, ensure_ascii=False),
                                            encoding="utf-8")
        out.with_suffix(".md").write_text(to_markdown(res), encoding="utf-8")
        s = res["resumen"]; t = s["subconjunto_sin_fechas_2019"]
        print(f"[repuntuado] total: herramienta={s['herramienta_correcta']:.0%} "
              f"cita={s['cito_fuente']:.0%} contenido={s['contenido_correcto']:.0%} | "
              f"sin fechas 2019 (n={t['n']}): {t['herramienta_correcta']:.0%} / "
              f"{t['cito_fuente']:.0%} / {t['contenido_correcto']:.0%}")
        return
    res = evaluate(a.backend, a.pausa)
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / f"eval_agente_{a.backend}.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    (ROOT / "reports" / f"eval_agente_{a.backend}.md").write_text(to_markdown(res), encoding="utf-8")
    s = res["resumen"]
    print(f"[{a.backend}] herramienta={s['herramienta_correcta']:.0%} cita={s['cito_fuente']:.0%} "
          f"contenido={s['contenido_correcto']:.0%} ({s['n']} preguntas)")


if __name__ == "__main__":
    main()
