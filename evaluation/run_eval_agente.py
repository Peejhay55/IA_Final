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

from aire.agent import LLMAgent, OfflineAgent  # noqa: E402


def _n(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def contains_any(answer: str, pattern: str) -> bool:
    return any(_n(p) in _n(answer) for p in pattern.split("|"))


def evaluate(backend: str, pause: float = 0.0) -> dict:
    spec = json.loads((ROOT / "evaluation" / "preguntas_agente.json").read_text(encoding="utf-8"))
    ctx = spec["contexto_tablero"]
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
        tool_ok = all(t in used for t in q["herramientas"])
        cite_ok = (not q["citas"]) or any(c in cites for c in q["citas"])
        content_ok = all(contains_any(answer, p) for p in q["contiene"])
        rows.append({"id": q["id"], "pregunta": q["pregunta"], "esperadas": q["herramientas"],
                     "usadas": used, "herramienta_correcta": tool_ok,
                     "citas_esperadas": q["citas"], "citas": cites, "cito_fuente": cite_ok,
                     "contenido_correcto": content_ok, "segundos": round(dt, 2),
                     "backend_real": real_backend, "aviso": notice, "respuesta": answer})
        if pause:
            time.sleep(pause)
    n = len(rows)
    summary = {
        "backend": backend, "n": n,
        "herramienta_correcta": sum(r["herramienta_correcta"] for r in rows) / n,
        "cito_fuente": sum(r["cito_fuente"] for r in rows) / n,
        "contenido_correcto": sum(r["contenido_correcto"] for r in rows) / n,
        "llamadas_herramientas_promedio": sum(len(r["usadas"]) for r in rows) / n,
        "segundos_promedio": sum(r["segundos"] for r in rows) / n,
        "respaldos_sin_llm": sum(r["backend_real"] == "offline" for r in rows) if backend == "llm" else None,
    }
    return {"resumen": summary, "detalle": rows}


def to_markdown(res: dict) -> str:
    s = res["resumen"]
    out = [f"# Evaluación del agente — backend `{s['backend']}`", "",
           f"- Preguntas: {s['n']}",
           f"- Herramienta correcta: **{s['herramienta_correcta']:.0%}**",
           f"- Citó la fuente esperada: **{s['cito_fuente']:.0%}**",
           f"- Contenido clave correcto: **{s['contenido_correcto']:.0%}**",
           f"- Llamadas a herramientas por pregunta: {s['llamadas_herramientas_promedio']:.1f}",
           f"- Tiempo medio por pregunta: {s['segundos_promedio']:.2f} s", "",
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
    a = ap.parse_args()
    res = evaluate(a.backend, a.pausa)
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / f"eval_agente_{a.backend}.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False))
    (ROOT / "reports" / f"eval_agente_{a.backend}.md").write_text(to_markdown(res), encoding="utf-8")
    s = res["resumen"]
    print(f"[{a.backend}] herramienta={s['herramienta_correcta']:.0%} cita={s['cito_fuente']:.0%} "
          f"contenido={s['contenido_correcto']:.0%} ({s['n']} preguntas)")


if __name__ == "__main__":
    main()
