"""Entrena los modelos de la Parte 1 y genera el reporte de métricas.

Uso:  python -m aire.train          (desde src/)  o  python scripts/train.py
"""
from __future__ import annotations

import json

import numpy as np

from . import config as C
from .data import build_processed
from .forecast import (DEFAULT_HP, evaluate_split, expanding_window_cv, hmm_heldout_loglik,
                       log_wide, save_models, select_hyperparams)


def main(quick: bool = False) -> dict:
    if not C.DAILY_CSV.exists():
        build_processed()
    lw = log_wide()
    if quick:  # usa los hiperparámetros ya seleccionados
        hp, tabla_hp = DEFAULT_HP, []
    else:
        print("Seleccionando hiperparámetros con validación temporal dentro del entrenamiento…")
        hp, tabla_hp = select_hyperparams(lw, C.TRAIN_END)
        print("  elegido:", hp)
    models, metrics, te, preds = evaluate_split(lw, C.TRAIN_END, C.TEST_START, hp=hp)
    save_models(models, hp)
    if quick:
        return metrics
    hmm = models.hmm
    report = {
        "particion": {"entrenamiento": f"{lw.index.min().date()} a {C.TRAIN_END}",
                      "prueba": f"{C.TEST_START} a {lw.index.max().date()}",
                      "n_prueba": int(len(te))},
        "hmm": {
            "estados": C.HMM_STATES,
            "media_pm25_por_estado": [round(float(np.exp(m)), 1) for m in hmm.mu],
            "desv_log": [round(float(np.sqrt(v)), 3) for v in hmm.var],
            "matriz_transicion": np.round(hmm.A, 3).tolist(),
            "duracion_esperada_dias": [round(float(1 / (1 - hmm.A[i, i])), 1)
                                       for i in range(hmm.n_states)],
            "iteraciones_em": len(hmm.history),
            "loglik_prueba_por_obs": {k: round(v, 4) for k, v in
                                      hmm_heldout_loglik(lw, C.TRAIN_END, C.TEST_START).items()},
        },
        "seleccion_hiperparametros": {"elegido": hp, "tabla_cv_entrenamiento": tabla_hp},
        "clasificacion_dia_siguiente": metrics,
    }
    cv = expanding_window_cv(lw, ["2019-09-01", "2019-10-01", "2019-11-01", "2019-12-01",
                                  "2020-01-01", "2020-02-01"], hp=hp)
    C.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    cv.to_csv(C.REPORTS_DIR / "validacion_temporal.csv", index=False)
    resumen = cv.groupby("modelo")[["accuracy", "macro_f1", "balanced_accuracy",
                                    "f1_excedencia"]].mean()
    report["validacion_temporal_promedio"] = resumen.round(4).to_dict(orient="index")
    C.METRICS_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    _print_summary(report)
    return report


def _print_summary(r: dict) -> None:
    print("\n== HMM ==")
    print("Media PM2.5 por estado:", dict(zip(r["hmm"]["estados"], r["hmm"]["media_pm25_por_estado"])))
    print("Log-verosimilitud en prueba por observación:", r["hmm"]["loglik_prueba_por_obs"])
    print("\n== Clasificación del día siguiente (prueba", r["particion"]["prueba"], ") ==")
    print(f"{'Modelo':42s} {'Acc':>6s} {'F1mac':>6s} {'BalAc':>6s} {'F1exc':>6s} "
          f"{'RecExc':>6s} {'LogL':>6s} {'Brier':>6s}")
    for name, m in r["clasificacion_dia_siguiente"].items():
        e = m["excedencia_norma"]
        print(f"{name:42s} {m['accuracy']:6.3f} {m['macro_f1']:6.3f} {m['balanced_accuracy']:6.3f} "
              f"{e['f1']:6.3f} {e['recall']:6.3f} {m.get('log_loss', float('nan')):6.3f} "
              f"{m.get('brier', float('nan')):6.3f}")
    print("\n== Validación temporal (ventana creciente, promedio de 6 meses) ==")
    for name, m in r["validacion_temporal_promedio"].items():
        print(f"{name:42s} {m['accuracy']:6.3f} {m['macro_f1']:6.3f} {m['balanced_accuracy']:6.3f} "
              f"{m['f1_excedencia']:6.3f}")


if __name__ == "__main__":
    main()
