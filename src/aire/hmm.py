"""Modelo Oculto de Markov (HMM) gaussiano implementado desde cero con NumPy.

Modela la serie diaria de log(PM2.5) de cada estación como generada por una cadena
de Markov de K estados latentes (Normal, Alerta, Episodio crítico). Cada estado emite
log(PM2.5) ~ N(mu_k, sigma_k^2).

Incluye:
  * Algoritmo forward-backward con escalado (Rabiner, 1989) → filtrado y suavizado.
  * Baum-Welch (EM) sobre múltiples secuencias (una por estación) con parámetros
    compartidos.
  * Viterbi en espacio logarítmico.
  * Datos faltantes: si y_t es NaN la verosimilitud de emisión es 1 (se marginaliza).
  * Predicción a un paso: P(s_{t+1} | y_{1:t}) = alpha_t · A, y la distribución
    predictiva de la clase ICA integrando cada gaussiana sobre los intervalos.

No usa librerías de HMM (hmmlearn, pomegranate…); solo NumPy.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

LOG_2PI = math.log(2 * math.pi)


def _norm_cdf(x: np.ndarray) -> np.ndarray:
    from math import erf

    return 0.5 * (1.0 + np.vectorize(erf)(np.asarray(x) / math.sqrt(2.0)))


@dataclass
class GaussianHMM:
    n_states: int = 3
    n_iter: int = 200
    tol: float = 1e-4
    min_var: float = 1e-3
    seed: int = 0
    pi: np.ndarray | None = None
    A: np.ndarray | None = None
    mu: np.ndarray | None = None
    var: np.ndarray | None = None
    history: list = field(default_factory=list)

    # ------------------------------------------------------------------ util
    def _emission(self, y: np.ndarray) -> np.ndarray:
        """Matriz T x K de densidades de emisión (1 donde falta el dato)."""
        y = np.asarray(y, dtype=float)
        B = np.ones((len(y), self.n_states))
        ok = ~np.isnan(y)
        d = y[ok, None] - self.mu[None, :]
        logp = -0.5 * (LOG_2PI + np.log(self.var)[None, :] + d**2 / self.var[None, :])
        B[ok] = np.exp(logp)
        return np.maximum(B, 1e-300)

    def _init_params(self, seqs: list[np.ndarray]) -> None:
        allv = np.concatenate([s[~np.isnan(s)] for s in seqs])
        K = self.n_states
        qs = np.quantile(allv, np.linspace(0, 1, K + 2)[1:-1])
        self.mu = np.sort(qs)
        self.var = np.full(K, np.var(allv) / K)
        self.pi = np.full(K, 1.0 / K)
        if K == 1:
            self.A = np.ones((1, 1))
        else:  # diagonal dominante: los episodios persisten varios días
            self.A = np.full((K, K), 0.1 / (K - 1))
            np.fill_diagonal(self.A, 0.9)

    # -------------------------------------------------------- forward/backward
    def forward(self, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Devuelve (alpha_hat T x K, c T) con alpha_hat_t = P(s_t | y_{1:t})."""
        B = self._emission(y)
        T, K = B.shape
        alpha = np.zeros((T, K))
        c = np.zeros(T)
        a = self.pi * B[0]
        c[0] = a.sum()
        alpha[0] = a / c[0]
        for t in range(1, T):
            a = (alpha[t - 1] @ self.A) * B[t]
            c[t] = a.sum()
            alpha[t] = a / c[t]
        return alpha, c

    def backward(self, y: np.ndarray, c: np.ndarray) -> np.ndarray:
        B = self._emission(y)
        T, K = B.shape
        beta = np.ones((T, K))
        for t in range(T - 2, -1, -1):
            beta[t] = (self.A @ (B[t + 1] * beta[t + 1])) / c[t + 1]
        return beta

    def log_likelihood(self, y: np.ndarray) -> float:
        _, c = self.forward(y)
        return float(np.log(c).sum())

    # -------------------------------------------------------------- Baum-Welch
    def fit(self, seqs: list[np.ndarray]) -> "GaussianHMM":
        seqs = [np.asarray(s, dtype=float) for s in seqs if np.sum(~np.isnan(s)) > 2]
        if self.mu is None:
            self._init_params(seqs)
        K = self.n_states
        prev = -np.inf
        self.history = []
        for it in range(self.n_iter):
            pi_acc = np.zeros(K)
            xi_acc = np.zeros((K, K))
            g_acc = np.zeros(K)
            gy_acc = np.zeros(K)
            gyy_acc = np.zeros(K)
            ll = 0.0
            for y in seqs:
                B = self._emission(y)
                alpha, c = self.forward(y)
                beta = self.backward(y, c)
                gamma = alpha * beta
                gamma /= gamma.sum(1, keepdims=True)
                ll += np.log(c).sum()
                pi_acc += gamma[0]
                # xi_t(i,j) = alpha_t(i) A_ij B_{t+1}(j) beta_{t+1}(j) / c_{t+1}
                xi = (
                    alpha[:-1, :, None]
                    * self.A[None]
                    * (B[1:] * beta[1:])[:, None, :]
                    / c[1:, None, None]
                )
                xi_acc += xi.sum(0)
                ok = ~np.isnan(y)
                g = gamma[ok]
                g_acc += g.sum(0)
                gy_acc += (g * y[ok, None]).sum(0)
                gyy_acc += (g * y[ok, None] ** 2).sum(0)
            self.pi = pi_acc / pi_acc.sum()
            self.A = xi_acc / xi_acc.sum(1, keepdims=True)
            self.mu = gy_acc / g_acc
            self.var = np.maximum(gyy_acc / g_acc - self.mu**2, self.min_var)
            self.history.append(float(ll))
            if ll - prev < self.tol * abs(ll):
                break
            prev = ll
        self._sort_states()
        return self

    def _sort_states(self) -> None:
        """Ordena los estados por media creciente para que 0=Normal, K-1=Crítico."""
        o = np.argsort(self.mu)
        self.mu, self.var, self.pi = self.mu[o], self.var[o], self.pi[o]
        self.A = self.A[np.ix_(o, o)]

    # ------------------------------------------------------------- inferencia
    def filter(self, y: np.ndarray) -> np.ndarray:
        """P(s_t | y_{1:t}) — causal, apto para pronóstico (sin fuga de información)."""
        return self.forward(y)[0]

    def smooth(self, y: np.ndarray) -> np.ndarray:
        alpha, c = self.forward(y)
        beta = self.backward(y, c)
        g = alpha * beta
        return g / g.sum(1, keepdims=True)

    def viterbi(self, y: np.ndarray) -> np.ndarray:
        logB = np.log(self._emission(y))
        logA = np.log(self.A)
        T, K = logB.shape
        delta = np.log(self.pi) + logB[0]
        psi = np.zeros((T, K), dtype=int)
        for t in range(1, T):
            s = delta[:, None] + logA
            psi[t] = s.argmax(0)
            delta = s.max(0) + logB[t]
        path = np.zeros(T, dtype=int)
        path[-1] = delta.argmax()
        for t in range(T - 2, -1, -1):
            path[t] = psi[t + 1, path[t + 1]]
        return path

    def predict_next_state(self, y: np.ndarray) -> np.ndarray:
        """P(s_{t+1} | y_{1:t}) para cada t (T x K)."""
        return self.filter(y) @ self.A

    def class_probs_from_state(self, p_state: np.ndarray, log_edges: list[float]) -> np.ndarray:
        """Convierte P(estado) en P(clase) integrando las gaussianas de emisión
        sobre los intervalos de log(PM2.5) definidos por ``log_edges``."""
        sd = np.sqrt(self.var)
        cuts = [-np.inf, *log_edges, np.inf]
        M = np.zeros((self.n_states, len(cuts) - 1))
        for k in range(self.n_states):
            cdf = _norm_cdf((np.array(cuts) - self.mu[k]) / sd[k])
            M[k] = np.diff(cdf)
        return np.atleast_2d(p_state) @ M

    # ------------------------------------------------------------ persistencia
    def to_dict(self) -> dict:
        return {
            "n_states": self.n_states,
            "pi": self.pi.tolist(),
            "A": self.A.tolist(),
            "mu": self.mu.tolist(),
            "var": self.var.tolist(),
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GaussianHMM":
        m = cls(n_states=d["n_states"])
        m.pi, m.A = np.array(d["pi"]), np.array(d["A"])
        m.mu, m.var = np.array(d["mu"]), np.array(d["var"])
        m.history = d.get("history", [])
        return m

    def save(self, path: Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: Path) -> "GaussianHMM":
        return cls.from_dict(json.loads(Path(path).read_text()))
