"""Clasificadores implementados desde cero con NumPy.

* ``GaussianNaiveBayes``: Naive Bayes con verosimilitudes gaussianas por clase.
* ``SoftmaxRegression``: regresión logística multinomial con descenso de gradiente
  (Adam), regularización L2 y pesos por clase opcionales para el desbalance.

scikit-learn solo se usa en las pruebas para verificar que los resultados coinciden.
"""
from __future__ import annotations

import numpy as np


class StandardScaler:
    def fit(self, X):
        self.mean_ = X.mean(0)
        self.std_ = X.std(0)
        self.std_[self.std_ < 1e-9] = 1.0
        return self

    def transform(self, X):
        return (X - self.mean_) / self.std_

    def to_dict(self):
        return {"mean": self.mean_.tolist(), "std": self.std_.tolist()}

    @classmethod
    def from_dict(cls, d):
        s = cls()
        s.mean_, s.std_ = np.array(d["mean"]), np.array(d["std"])
        return s


class GaussianNaiveBayes:
    def __init__(self, var_smoothing: float = 1e-9):
        self.var_smoothing = var_smoothing

    def fit(self, X: np.ndarray, y: np.ndarray, n_classes: int | None = None):
        K = n_classes or int(y.max()) + 1
        D = X.shape[1]
        eps = self.var_smoothing * X.var(0).max()
        self.theta_ = np.zeros((K, D))
        self.var_ = np.ones((K, D))
        self.log_prior_ = np.full(K, -np.inf)
        for k in range(K):
            Xk = X[y == k]
            if len(Xk) == 0:
                continue
            self.theta_[k] = Xk.mean(0)
            self.var_[k] = Xk.var(0) + eps
            self.log_prior_[k] = np.log(len(Xk) / len(X))
        return self

    def joint_log_likelihood(self, X: np.ndarray) -> np.ndarray:
        ll = -0.5 * (
            np.log(2 * np.pi * self.var_)[None].sum(-1)
            + (((X[:, None, :] - self.theta_[None]) ** 2) / self.var_[None]).sum(-1)
        )
        return ll + self.log_prior_[None]

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        jll = self.joint_log_likelihood(X)
        jll -= jll.max(1, keepdims=True)
        p = np.exp(jll)
        return p / p.sum(1, keepdims=True)

    def predict(self, X):
        return self.predict_proba(X).argmax(1)

    def to_dict(self):
        return {
            "theta": self.theta_.tolist(),
            "var": self.var_.tolist(),
            "log_prior": [float(v) if np.isfinite(v) else -1e30 for v in self.log_prior_],
        }

    @classmethod
    def from_dict(cls, d):
        m = cls()
        m.theta_, m.var_ = np.array(d["theta"]), np.array(d["var"])
        m.log_prior_ = np.array(d["log_prior"])
        return m


def _softmax(Z: np.ndarray) -> np.ndarray:
    Z = Z - Z.max(1, keepdims=True)
    E = np.exp(Z)
    return E / E.sum(1, keepdims=True)


class SoftmaxRegression:
    """Regresión logística multinomial: P(y=k|x) = softmax(W x + b)_k.

    Minimiza la entropía cruzada (ponderada) + (l2/2)||W||^2 con Adam.
    """

    def __init__(self, l2: float = 1e-2, lr: float = 0.05, epochs: int = 2000,
                 class_weight: str | None = "balanced", seed: int = 0):
        self.l2, self.lr, self.epochs = l2, lr, epochs
        self.class_weight, self.seed = class_weight, seed

    def fit(self, X: np.ndarray, y: np.ndarray, n_classes: int | None = None):
        rng = np.random.default_rng(self.seed)
        N, D = X.shape
        K = n_classes or int(y.max()) + 1
        Y = np.eye(K)[y]
        counts = np.bincount(y, minlength=K).astype(float)
        if self.class_weight == "balanced":
            w_k = np.where(counts > 0, N / (K * np.maximum(counts, 1)), 0.0)
        elif self.class_weight == "sqrt":  # compensación parcial del desbalance
            w_k = np.where(counts > 0, np.sqrt(N / (K * np.maximum(counts, 1))), 0.0)
        else:
            w_k = np.ones(K)
        w = w_k[y][:, None]
        W = rng.normal(0, 0.01, (D, K))
        b = np.zeros(K)
        mW = vW = np.zeros_like(W)
        mb = vb = np.zeros_like(b)
        b1, b2, eps = 0.9, 0.999, 1e-8
        self.loss_ = []
        for t in range(1, self.epochs + 1):
            P = _softmax(X @ W + b)
            G = w * (P - Y) / w.sum()
            gW = X.T @ G + self.l2 * W
            gb = G.sum(0)
            mW = b1 * mW + (1 - b1) * gW
            vW = b2 * vW + (1 - b2) * gW**2
            mb = b1 * mb + (1 - b1) * gb
            vb = b2 * vb + (1 - b2) * gb**2
            W -= self.lr * (mW / (1 - b1**t)) / (np.sqrt(vW / (1 - b2**t)) + eps)
            b -= self.lr * (mb / (1 - b1**t)) / (np.sqrt(vb / (1 - b2**t)) + eps)
            if t % 100 == 0 or t == 1:
                ce = -(w * Y * np.log(P + 1e-12)).sum() / w.sum()
                self.loss_.append(float(ce + 0.5 * self.l2 * (W**2).sum()))
        self.W_, self.b_ = W, b
        return self

    def predict_proba(self, X):
        return _softmax(X @ self.W_ + self.b_)

    def predict(self, X):
        return self.predict_proba(X).argmax(1)

    def to_dict(self):
        return {"W": self.W_.tolist(), "b": self.b_.tolist(), "l2": self.l2}

    @classmethod
    def from_dict(cls, d):
        m = cls(l2=d.get("l2", 1e-2))
        m.W_, m.b_ = np.array(d["W"]), np.array(d["b"])
        return m


# ---------------------------------------------------------------------------
# Métricas (también implementadas a mano)
# ---------------------------------------------------------------------------
def confusion_matrix(y_true, y_pred, K: int) -> np.ndarray:
    M = np.zeros((K, K), dtype=int)
    for t, p in zip(y_true, y_pred):
        M[int(t), int(p)] += 1
    return M


def classification_metrics(y_true, y_pred, K: int, labels: list[str]) -> dict:
    M = confusion_matrix(y_true, y_pred, K)
    tp = np.diag(M).astype(float)
    prec = np.divide(tp, M.sum(0), out=np.zeros(K), where=M.sum(0) > 0)
    rec = np.divide(tp, M.sum(1), out=np.zeros(K), where=M.sum(1) > 0)
    f1 = np.divide(2 * prec * rec, prec + rec, out=np.zeros(K), where=(prec + rec) > 0)
    present = M.sum(1) > 0
    return {
        "accuracy": float(tp.sum() / max(M.sum(), 1)),
        "macro_f1": float(f1[present].mean()),
        "balanced_accuracy": float(rec[present].mean()),
        "per_class": {
            lab: {"precision": float(prec[i]), "recall": float(rec[i]), "f1": float(f1[i]),
                  "soporte": int(M[i].sum())}
            for i, lab in enumerate(labels)
        },
        "confusion_matrix": M.tolist(),
        "n": int(M.sum()),
    }
