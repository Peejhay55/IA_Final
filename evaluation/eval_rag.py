"""Evaluación de la recuperación (RAG): hit@1, hit@3 y MRR sobre consultas fijas.

Uso:  python evaluation/eval_rag.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aire.rag import Retriever  # noqa: E402


def evaluate(retriever: Retriever, expand: bool) -> dict:
    qs = json.loads((ROOT / "evaluation" / "consultas_rag.json").read_text(encoding="utf-8"))
    h1 = h3 = mrr = 0.0
    detalle = []
    for item in qs:
        ok_ids = set(item["doc"].split("|"))
        res = retriever.search(item["q"], k=5, expand=expand)
        ids = [r["cita"].strip("[]") for r in res]
        rank = next((i + 1 for i, d in enumerate(ids) if d in ok_ids), None)
        h1 += rank == 1
        h3 += rank is not None and rank <= 3
        mrr += 1 / rank if rank else 0
        detalle.append({"consulta": item["q"], "esperado": item["doc"], "top3": ids[:3],
                        "rango": rank})
    n = len(qs)
    return {"n": n, "hit@1": h1 / n, "hit@3": h3 / n, "MRR": mrr / n, "detalle": detalle}


def main() -> dict:
    r = Retriever()
    out = {"backend": r.backend,
           "sin_expansion": evaluate(r, expand=False),
           "con_expansion": evaluate(r, expand=True)}
    for k in ("sin_expansion", "con_expansion"):
        m = out[k]
        print(f"{k:15s} hit@1={m['hit@1']:.2f}  hit@3={m['hit@3']:.2f}  MRR={m['MRR']:.2f}")
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "eval_rag.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    return out


if __name__ == "__main__":
    main()
