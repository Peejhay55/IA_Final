"""Construcción de variables, entrenamiento, validación temporal y predicción.

Integración de la Parte 1:
  1. El HMM (aprendido solo con el periodo de entrenamiento) estima de forma causal
     P(estado latente | historia) para cada estación y día (filtrado forward).
  2. Esas probabilidades son variables de entrada del clasificador (regresión
     logística multinomial / Naive Bayes) que predice la clase ICA del día siguiente.
  3. Se compara contra líneas base: persistencia, clase mayoritaria y el propio HMM
     usado como pronosticador (P(s_{t+1}|y_{1:t}) integrado sobre las clases).
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config as C
from .classifier import (GaussianNaiveBayes, SoftmaxRegression, StandardScaler,
                         classification_metrics)
from .data import daily_wide, to_class_index
from .hmm import GaussianHMM

FEATURES = [
    "log_pm25_t", "log_pm25_t1", "log_media_3d", "delta_log", "log_media_regional",
    "p_normal", "p_alerta", "p_critico", "manana_fin_de_semana", "mes_sin", "mes_cos",
]
LOG_EDGES = [float(np.log(e)) for e in C.CLASS_EDGES]
K = len(C.CLASSES)


def log_wide(wide: pd.DataFrame | None = None) -> pd.DataFrame:
    w = daily_wide() if wide is None else wide
    return np.log(w.clip(lower=1.0))


def fit_hmm(lw: pd.DataFrame, end: str | None = None, seed: int = 0) -> GaussianHMM:
    part = lw if end is None else lw.loc[:end]
    seqs = [part[c].values for c in part.columns]
    return GaussianHMM(n_states=C.HMM_N_STATES, seed=seed).fit(seqs)


def build_features(lw: pd.DataFrame, hmm: GaussianHMM) -> pd.DataFrame:
    """Una fila por (estación, día t) con variables en t y objetivo en t+1."""
    regional = lw.mean(axis=1, skipna=True)
    frames = []
    for cod in lw.columns:
        y = lw[cod]
        filt = hmm.filter(y.values)
        p_next_state = filt @ hmm.A
        p_hmm_cls = hmm.class_probs_from_state(p_next_state, LOG_EDGES)
        df = pd.DataFrame(index=lw.index)
        df["codigo"] = cod
        df["log_pm25_t"] = y
        df["log_pm25_t1"] = y.shift(1).fillna(y)
        df["log_media_3d"] = y.rolling(3, min_periods=1).mean()
        df["delta_log"] = df["log_pm25_t"] - df["log_pm25_t1"]
        df["log_media_regional"] = regional
        df[["p_normal", "p_alerta", "p_critico"]] = filt
        manana = lw.index + pd.Timedelta(days=1)
        df["manana_fin_de_semana"] = (manana.day_of_week >= 5).astype(float)
        df["mes_sin"] = np.sin(2 * np.pi * manana.month / 12)
        df["mes_cos"] = np.cos(2 * np.pi * manana.month / 12)
        df[["hmm_p_buena", "hmm_p_aceptable", "hmm_p_danina"]] = p_hmm_cls
        df["estado_hmm"] = filt.argmax(1)
        df["pm25_t"] = np.exp(y)
        df["pm25_t_mas_1"] = np.exp(y.shift(-1))
        frames.append(df)
    out = pd.concat(frames).rename_axis("fecha").reset_index()
    out["clase_t"] = np.where(out["pm25_t"].notna(), to_class_index(out["pm25_t"].fillna(0)), -1)
    out["y"] = np.where(out["pm25_t_mas_1"].notna(),
                        to_class_index(out["pm25_t_mas_1"].fillna(0)), -1)
    return out


def _xy(df: pd.DataFrame):
    m = df["log_pm25_t"].notna() & (df["y"] >= 0)
    d = df[m]
    return d, d[FEATURES].values.astype(float), d["y"].values.astype(int)


@dataclass
class TrainedModels:
    hmm: GaussianHMM
    scaler: StandardScaler
    logreg: SoftmaxRegression
    nb: GaussianNaiveBayes
    majority: int


# Hiperparámetros por defecto (los elegidos por ``select_hyperparams`` en la corrida
# documentada en reports/metricas_parte1.json).
DEFAULT_HP = {"class_weight": "sqrt", "l2": 1e-3}
NO_HMM = [f for f in FEATURES if not f.startswith("p_")]


def train_models(lw: pd.DataFrame, train_end: str, hp: dict | None = None,
                 feats: pd.DataFrame | None = None) -> tuple[TrainedModels, pd.DataFrame]:
    hp = hp or DEFAULT_HP
    hmm = fit_hmm(lw, end=train_end)
    feats = build_features(lw, hmm) if feats is None else feats
    tr, Xtr, ytr = _xy(feats[feats["fecha"] <= train_end])
    scaler = StandardScaler().fit(Xtr)
    Xs = scaler.transform(Xtr)
    logreg = SoftmaxRegression(**hp).fit(Xs, ytr, n_classes=K)
    nb = GaussianNaiveBayes().fit(Xs, ytr, n_classes=K)
    majority = int(np.bincount(ytr, minlength=K).argmax())
    m = TrainedModels(hmm, scaler, logreg, nb, majority)
    # Ablación: misma regresión logística sin las probabilidades del HMM
    idx = [FEATURES.index(f) for f in NO_HMM]
    m.logreg_sin_hmm = SoftmaxRegression(**hp).fit(Xs[:, idx], ytr, n_classes=K)
    m.prior = np.bincount(ytr, minlength=K) / len(ytr)
    return m, feats


def select_hyperparams(lw: pd.DataFrame, train_end: str, n_folds: int = 5,
                      tie_tol: float = 0.005) -> tuple[dict, list]:
    """Elige pesos de clase y L2 con validación temporal *dentro* del periodo de
    entrenamiento (los últimos ``n_folds`` meses), maximizando el F1-macro medio.
    Desempate (fijado antes de ver la prueba): entre las configuraciones a menos de
    ``tie_tol`` del mejor F1-macro, se elige la de menor log-loss de validación.
    El periodo de prueba nunca se usa para elegir hiperparámetros."""
    grid = [{"class_weight": cw, "l2": l2} for cw in (None, "sqrt", "balanced")
            for l2 in (1e-3, 1e-2, 1e-1)]
    end = pd.Timestamp(train_end)
    months = [(end - pd.offsets.MonthBegin(i + 1)) for i in range(n_folds)][::-1]
    scores = {i: [] for i in range(len(grid))}
    losses = {i: [] for i in range(len(grid))}
    for s in months:
        e = s + pd.offsets.MonthEnd(0)
        tre = s - pd.Timedelta(days=1)
        hmm = fit_hmm(lw, end=str(tre.date()))
        f = build_features(lw, hmm)
        _, Xtr, ytr = _xy(f[f["fecha"] <= tre])
        _, Xva, yva = _xy(f[(f["fecha"] >= s) & (f["fecha"] <= e)])
        sc = StandardScaler().fit(Xtr)
        for i, hp in enumerate(grid):
            mdl = SoftmaxRegression(epochs=1000, **hp).fit(sc.transform(Xtr), ytr, n_classes=K)
            P = mdl.predict_proba(sc.transform(Xva))
            r = classification_metrics(yva, P.argmax(1), K, C.CLASSES)
            scores[i].append(r["macro_f1"])
            losses[i].append(prob_metrics(yva, P)["log_loss"])
    table = [{**grid[i], "macro_f1_cv": float(np.mean(scores[i])),
              "log_loss_cv": float(np.mean(losses[i]))} for i in scores]
    table.sort(key=lambda r: -r["macro_f1_cv"])
    top = table[0]["macro_f1_cv"]
    tied = [r for r in table if r["macro_f1_cv"] >= top - tie_tol]
    chosen = min(tied, key=lambda r: r["log_loss_cv"])
    best = {k: chosen[k] for k in ("class_weight", "l2")}
    return best, table


MAIN_MODEL = "Regresión logística + estados HMM"


def predict_all(m: TrainedModels, d: pd.DataFrame) -> dict[str, np.ndarray]:
    """Probabilidades (N x K) de cada modelo; las líneas base deterministas se
    representan como one-hot."""
    X = m.scaler.transform(d[FEATURES].values.astype(float))
    idx = [FEATURES.index(f) for f in NO_HMM]
    eye = np.eye(K)
    out = {
        MAIN_MODEL: m.logreg.predict_proba(X),
        "Regresión logística sin HMM (ablación)": m.logreg_sin_hmm.predict_proba(X[:, idx]),
        "Naive Bayes gaussiano + estados HMM": m.nb.predict_proba(X),
        "HMM solo (pronóstico a un paso)": d[["hmm_p_buena", "hmm_p_aceptable",
                                              "hmm_p_danina"]].values.astype(float),
        "Línea base: persistencia": eye[d["clase_t"].values],
        "Línea base: climatología (frecuencias)": np.tile(m.prior, (len(d), 1)),
    }
    return out


def prob_metrics(y: np.ndarray, P: np.ndarray) -> dict:
    Y = np.eye(K)[y]
    Pc = np.clip(P, 1e-6, 1)
    Pc = Pc / Pc.sum(1, keepdims=True)
    return {"log_loss": float(-(Y * np.log(Pc)).sum(1).mean()),
            "brier": float(((P - Y) ** 2).sum(1).mean())}


def exceed_metrics(y: np.ndarray, yhat: np.ndarray) -> dict:
    """Problema binario de salud pública: ¿mañana se supera la norma (Dañina)?"""
    t, p = y == K - 1, yhat == K - 1
    tp, fp, fn = int((t & p).sum()), int((~t & p).sum()), int((t & ~p).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"precision": prec, "recall": rec, "f1": f1, "vp": tp, "fp": fp, "fn": fn}


def evaluate_split(lw: pd.DataFrame, train_end: str, test_start: str,
                   test_end: str | None = None, hp: dict | None = None):
    models, feats = train_models(lw, train_end, hp)
    te = feats[feats["fecha"] >= test_start]
    if test_end is not None:
        te = te[te["fecha"] <= test_end]
    te, _, yte = _xy(te)
    probs = predict_all(models, te)
    metrics = {}
    for name, P in probs.items():
        yhat = P.argmax(1)
        r = classification_metrics(yte, yhat, K, C.CLASSES)
        r["excedencia_norma"] = exceed_metrics(yte, yhat)
        if "persistencia" not in name:
            r.update(prob_metrics(yte, P))
        metrics[name] = r
    return models, metrics, te, probs


def hmm_heldout_loglik(lw: pd.DataFrame, train_end: str, test_start: str) -> dict:
    """Log-verosimilitud por observación en prueba: HMM-3 vs gaussiana i.i.d. (HMM-1)."""
    out = {}
    for k in (1, 2, 3, 4):
        part = lw.loc[:train_end]
        m = GaussianHMM(n_states=k).fit([part[c].values for c in part.columns])
        te = lw.loc[test_start:]
        # se condiciona en el entrenamiento: ll(train+test) - ll(train)
        ll, n = 0.0, 0
        for c in lw.columns:
            full = lw.loc[:, c].values
            ntr = len(part)
            ll += m.log_likelihood(full) - m.log_likelihood(full[:ntr])
            n += int(np.sum(~np.isnan(te[c].values)))
        out[f"HMM-{k}"] = ll / n
    return out


def expanding_window_cv(lw: pd.DataFrame, months: list[str],
                        hp: dict | None = None) -> pd.DataFrame:
    """Validación temporal con ventana creciente: para cada mes de prueba se entrena
    con todo lo anterior (HMM incluido) y se evalúa en ese mes."""
    rows = []
    for mstart in months:
        start = pd.Timestamp(mstart)
        end = (start + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d")
        train_end = (start - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        _, met, te, _ = evaluate_split(lw, train_end, mstart, end, hp)
        for name, r in met.items():
            rows.append({"mes_prueba": mstart[:7], "modelo": name, "n": r["n"],
                         "accuracy": r["accuracy"], "macro_f1": r["macro_f1"],
                         "balanced_accuracy": r["balanced_accuracy"],
                         "f1_excedencia": r["excedencia_norma"]["f1"],
                         "recall_danina": r["per_class"]["Dañina"]["recall"],
                         "soporte_danina": r["per_class"]["Dañina"]["soporte"]})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Persistencia y predicción en línea (usada por las herramientas del agente)
# ---------------------------------------------------------------------------
def save_models(m: TrainedModels, hp: dict | None = None) -> None:
    m.hmm.save(C.HMM_JSON)
    C.CLASSIFIER_JSON.write_text(json.dumps({
        "features": FEATURES, "classes": C.CLASSES, "train_end": C.TRAIN_END,
        "hiperparametros": hp or DEFAULT_HP,
        "scaler": m.scaler.to_dict(), "logreg": m.logreg.to_dict(),
        "nb": m.nb.to_dict(), "majority": m.majority,
    }, indent=2))


def load_models() -> TrainedModels:
    if not (C.HMM_JSON.exists() and C.CLASSIFIER_JSON.exists()):
        from .train import main as train_main

        train_main(quick=True)
    d = json.loads(C.CLASSIFIER_JSON.read_text())
    return TrainedModels(
        hmm=GaussianHMM.load(C.HMM_JSON),
        scaler=StandardScaler.from_dict(d["scaler"]),
        logreg=SoftmaxRegression.from_dict(d["logreg"]),
        nb=GaussianNaiveBayes.from_dict(d["nb"]),
        majority=d["majority"],
    )


class Forecaster:
    """Fachada usada por el agente y el dashboard."""

    def __init__(self):
        self.models = load_models()
        self.lw = log_wide()
        self.feats = build_features(self.lw, self.models.hmm)

    def states(self, codigo: int) -> pd.DataFrame:
        f = self.feats[self.feats["codigo"] == codigo].copy()
        y = self.lw[codigo].values
        f["estado_viterbi"] = self.models.hmm.viterbi(y)
        return f

    def predict(self, codigo: int, fecha) -> dict:
        fecha = pd.Timestamp(fecha).normalize()
        f = self.feats[(self.feats["codigo"] == codigo) & (self.feats["fecha"] == fecha)]
        if f.empty or f["log_pm25_t"].isna().all():
            raise ValueError(
                f"No hay dato válido de PM2.5 para la estación {codigo} el {fecha.date()}; "
                "elija otra fecha entre "
                f"{self.lw.index.min().date()} y {self.lw.index.max().date()}.")
        row = f.iloc[0]
        X = self.models.scaler.transform(row[FEATURES].values.astype(float)[None])
        p_lr = self.models.logreg.predict_proba(X)[0]
        p_nb = self.models.nb.predict_proba(X)[0]
        p_hmm = row[["hmm_p_buena", "hmm_p_aceptable", "hmm_p_danina"]].values.astype(float)
        real = row["pm25_t_mas_1"]
        return {
            "codigo": int(codigo),
            "fecha_base": str(fecha.date()),
            "fecha_pronostico": str((fecha + pd.Timedelta(days=1)).date()),
            "pm25_fecha_base": round(float(row["pm25_t"]), 1),
            "estado_hmm_actual": C.HMM_STATES[int(row["estado_hmm"])],
            "p_estado_hmm": {s: round(float(row[c]), 3) for s, c in
                             zip(C.HMM_STATES, ["p_normal", "p_alerta", "p_critico"])},
            "clase_predicha": C.CLASSES[int(p_lr.argmax())],
            "probabilidades": {c: round(float(p), 3) for c, p in zip(C.CLASSES, p_lr)},
            "probabilidades_naive_bayes": {c: round(float(p), 3) for c, p in zip(C.CLASSES, p_nb)},
            "probabilidades_hmm": {c: round(float(p), 3) for c, p in zip(C.CLASSES, p_hmm)},
            "modelo": "Regresión logística multinomial con estados HMM (implementación propia)",
            "valor_real_dia_siguiente": None if pd.isna(real) else round(float(real), 1),
            "en_periodo_de_prueba": bool(fecha >= pd.Timestamp(C.TEST_START)),
        }
