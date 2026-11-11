"""Pruebas de corrección de las implementaciones propias (Parte 1)."""
import itertools
import math

import numpy as np
import pytest

from aire import config as C
from aire.classifier import (GaussianNaiveBayes, SoftmaxRegression, StandardScaler,
                             classification_metrics)
from aire.data import ica_category, to_class
from aire.hmm import GaussianHMM


def _toy_hmm():
    m = GaussianHMM(n_states=2)
    m.pi = np.array([0.6, 0.4])
    m.A = np.array([[0.8, 0.2], [0.3, 0.7]])
    m.mu = np.array([0.0, 2.0])
    m.var = np.array([1.0, 0.5])
    return m


def _brute_force(m, y):
    """Suma sobre todas las secuencias de estados (solo para T pequeño)."""
    T, K = len(y), m.n_states
    total, best, best_path = 0.0, -1, None
    for path in itertools.product(range(K), repeat=T):
        p = m.pi[path[0]]
        for t in range(T):
            if t:
                p *= m.A[path[t - 1], path[t]]
            if not np.isnan(y[t]):
                v = m.var[path[t]]
                p *= math.exp(-(y[t] - m.mu[path[t]]) ** 2 / (2 * v)) / math.sqrt(2 * math.pi * v)
        total += p
        if p > best:
            best, best_path = p, path
    return total, np.array(best_path)


def test_forward_y_viterbi_coinciden_con_enumeracion():
    m = _toy_hmm()
    y = np.array([0.1, 1.9, np.nan, 2.3, -0.4])
    total, path = _brute_force(m, y)
    assert m.log_likelihood(y) == pytest.approx(math.log(total), rel=1e-9)
    assert np.array_equal(m.viterbi(y), path)


def test_filtrado_y_suavizado_son_distribuciones():
    m = _toy_hmm()
    y = np.array([0.0, 2.0, 2.1, np.nan, 0.2])
    for P in (m.filter(y), m.smooth(y), m.predict_next_state(y)):
        assert np.allclose(P.sum(1), 1.0)
        assert (P >= 0).all()


def test_baum_welch_recupera_parametros_y_ll_no_decrece():
    rng = np.random.default_rng(1)
    true = _toy_hmm()
    seqs = []
    for _ in range(30):
        s, y = rng.choice(2, p=true.pi), []
        for _ in range(80):
            y.append(rng.normal(true.mu[s], math.sqrt(true.var[s])))
            s = rng.choice(2, p=true.A[s])
        seqs.append(np.array(y))
    m = GaussianHMM(n_states=2).fit(seqs)
    assert np.allclose(m.mu, true.mu, atol=0.15)
    assert np.allclose(m.A, true.A, atol=0.07)
    assert all(b >= a - 1e-6 for a, b in zip(m.history, m.history[1:]))  # EM monótono


def test_naive_bayes_igual_a_sklearn():
    from sklearn.naive_bayes import GaussianNB

    rng = np.random.default_rng(0)
    X = rng.normal(size=(300, 4)) + np.repeat(np.arange(3), 100)[:, None]
    y = np.repeat(np.arange(3), 100)
    ours = GaussianNaiveBayes().fit(X, y).predict_proba(X)
    ref = GaussianNB().fit(X, y).predict_proba(X)
    assert np.allclose(ours, ref, atol=1e-6)


def test_regresion_logistica_aprende_y_se_acerca_a_sklearn():
    from sklearn.linear_model import LogisticRegression

    rng = np.random.default_rng(0)
    X = rng.normal(size=(600, 3))
    y = np.argmax(X @ np.array([[2, 0, -1], [0, 1, 1], [-1, 1, 0]]) + rng.normal(0, .5, (600, 3)), 1)
    Xs = StandardScaler().fit(X).transform(X)
    ours = SoftmaxRegression(l2=1e-3, class_weight=None, epochs=3000).fit(Xs, y, 3)
    ref = LogisticRegression(C=1 / (1e-3 * len(y)), max_iter=2000).fit(Xs, y)
    agree = (ours.predict(Xs) == ref.predict(Xs)).mean()
    assert agree > 0.97
    assert ours.loss_[-1] < ours.loss_[0]


def test_metricas_manual():
    r = classification_metrics([0, 1, 2, 2], [0, 2, 2, 2], 3, C.CLASSES)
    assert r["accuracy"] == 0.75
    assert r["confusion_matrix"] == [[1, 0, 0], [0, 0, 1], [0, 0, 2]]
    assert r["per_class"]["Aceptable"]["recall"] == 0.0


@pytest.mark.parametrize("v,cat,cls", [(5, "Buena", "Buena"), (12.0, "Buena", "Buena"),
                                       (37.0, "Aceptable", "Aceptable"),
                                       (37.4, "Dañina a la salud de grupos sensibles", "Dañina"),
                                       (60, "Dañina a la salud", "Dañina")])
def test_categorias_ica(v, cat, cls):
    assert ica_category(v) == cat
    assert to_class(v) == cls
