"""Recuperación aumentada (RAG) sobre el corpus normativo y de salud.

* Fragmentación: cada documento Markdown de ``data/corpus`` se divide por secciones
  (``## ...``); cada fragmento conserva el id, título, URL y sección de su documento.
* Embeddings (configurable con la variable RAG_BACKEND):
    - ``tfidf`` (por defecto, 100 % offline y reproducible): TF-IDF de palabras (1-2
      gramas) + n-gramas de caracteres, sin tildes, normalizado L2.
    - ``st``: sentence-transformers multilingüe
      (paraphrase-multilingual-MiniLM-L12-v2), si está instalado.
* Índice: FAISS ``IndexFlatIP`` (producto interno = coseno con vectores normalizados);
  si FAISS no está disponible se usa NumPy con el mismo resultado.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import config as C

try:  # FAISS es opcional
    import faiss  # type: ignore
except Exception:  # pragma: no cover
    faiss = None


@dataclass
class Chunk:
    doc_id: str
    titulo: str
    url: str
    seccion: str
    texto: str

    @property
    def cita(self) -> str:
        return f"[{self.doc_id}]"


def _strip_accents(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


STOPWORDS_ES = sorted(set(_strip_accents(w) for w in """
a al algo ante como con cual cuales cuando de del desde donde e el ella ellas ellos en
entre era es esa ese eso esta estan este esto fue ha hay la las le les lo los mas me mi
muy no nos o para pero por porque puede pueden que quien se segun ser si sin sobre son su
sus tambien te tiene un una uno unos y ya yo qué cómo cuál dónde cuándo está están hoy
mañana debo deberia puedo quiero saber dime explica favor
""".split()))

# Tesauro mínimo del dominio para expandir consultas coloquiales (documentado en el
# informe). Cada clave (sin tildes) agrega términos técnicos usados en el corpus.
THESAURUS = {
    "trotar": "actividad fisica ejercicio al aire libre grupos sensibles",
    "correr": "actividad fisica ejercicio al aire libre grupos sensibles",
    "ejercicio": "actividad fisica al aire libre esfuerzo",
    "deporte": "actividad fisica al aire libre esfuerzo",
    "salir": "actividades al aire libre recomendaciones",
    "ninos": "grupos sensibles ninos instituciones educativas",
    "colegio": "instituciones educativas ninos esfuerzo al aire libre",
    "asma": "enfermedades respiratorias grupos sensibles",
    "verde": "buena 0 12",
    "amarillo": "aceptable 13 37",
    "naranja": "danina grupos sensibles 38 55 prevencion",
    "rojo": "danina a la salud 56 150 alerta",
    "morado": "muy danina 151 250 emergencia",
    "purpura": "muy danina 151 250 emergencia",
    "pico": "restriccion vehicular movilidad",
    "placa": "restriccion vehicular movilidad",
    "carro": "restriccion vehicular movilidad vehiculos",
    "norma": "nivel maximo permisible resolucion 2254",
    "limite": "nivel maximo permisible",
    "marzo": "temporada transicion episodios criticos febrero",
    "febrero": "temporada transicion episodios criticos",
    "octubre": "temporada transicion episodios criticos noviembre",
    "sube": "aumenta concentraciones episodios criticos atmosfera estable",
    "oms": "organizacion mundial de la salud guias",
    "salud": "efectos sobre la salud recomendaciones",
}


def expand_query(q: str) -> str:
    toks = re.findall(r"\w+", _strip_accents(q))
    extra = [THESAURUS[t] for t in toks if t in THESAURUS]
    return q + (" " + " ".join(extra) if extra else "")


def parse_doc(path: Path) -> list[Chunk]:
    raw = Path(path).read_text(encoding="utf-8")
    meta, body = {}, raw
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, flags=re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        body = m.group(2)
    chunks = []
    for sec in re.split(r"\n(?=## )", body.strip()):
        lines = sec.strip().splitlines()
        if not lines:
            continue
        title = lines[0].lstrip("# ").strip()
        text = " ".join(l.strip() for l in lines[1:] if l.strip())
        if text:
            chunks.append(Chunk(meta.get("id", path.stem), meta.get("titulo", path.stem),
                                meta.get("url", ""), title, text))
    return chunks


def load_corpus(corpus_dir: Path = C.CORPUS_DIR) -> list[Chunk]:
    chunks: list[Chunk] = []
    for p in sorted(Path(corpus_dir).glob("*.md")):
        chunks.extend(parse_doc(p))
    return chunks


class TfidfEmbedder:
    name = "tfidf"

    def fit(self, texts: list[str]):
        from scipy.sparse import hstack  # noqa: F401
        from sklearn.feature_extraction.text import TfidfVectorizer

        self.word = TfidfVectorizer(preprocessor=_strip_accents, ngram_range=(1, 2),
                                    sublinear_tf=True, min_df=1, stop_words=STOPWORDS_ES)
        self.char = TfidfVectorizer(preprocessor=_strip_accents, analyzer="char_wb",
                                    ngram_range=(3, 5), sublinear_tf=True, min_df=1)
        self.word.fit(texts)
        self.char.fit(texts)
        return self

    def encode(self, texts: list[str]) -> np.ndarray:
        from scipy.sparse import hstack

        X = hstack([self.word.transform(texts), 0.3 * self.char.transform(texts)]).toarray()
        n = np.linalg.norm(X, axis=1, keepdims=True)
        return (X / np.maximum(n, 1e-12)).astype("float32")


class STEmbedder:  # pragma: no cover - requiere descargar el modelo
    name = "st"
    model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    def fit(self, texts):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(self.model_name)
        return self

    def encode(self, texts):
        return np.asarray(self.model.encode(texts, normalize_embeddings=True), dtype="float32")


class Retriever:
    def __init__(self, backend: str | None = None, corpus_dir: Path = C.CORPUS_DIR):
        self.chunks = load_corpus(corpus_dir)
        if not self.chunks:
            raise RuntimeError(f"Corpus vacío en {corpus_dir}")
        docs = [f"{c.titulo}. {c.seccion}. {c.texto}" for c in self.chunks]
        backend = (backend or C.RAG_BACKEND).lower()
        emb = None
        if backend == "st":
            try:
                emb = STEmbedder().fit(docs)
            except Exception as exc:  # noqa: BLE001
                print(f"[RAG] sentence-transformers no disponible ({exc}); uso TF-IDF")
        self.embedder = emb or TfidfEmbedder().fit(docs)
        self.vectors = self.embedder.encode(docs)
        if faiss is not None:
            self.index = faiss.IndexFlatIP(self.vectors.shape[1])
            self.index.add(self.vectors)
        else:  # pragma: no cover
            self.index = None

    @property
    def backend(self) -> str:
        return f"{self.embedder.name}+{'faiss' if self.index is not None else 'numpy'}"

    def search(self, query: str, k: int = 4, expand: bool = True) -> list[dict]:
        if not query or not query.strip():
            raise ValueError("La consulta está vacía.")
        q = self.embedder.encode([expand_query(query) if expand else query])
        k = min(k, len(self.chunks))
        if self.index is not None:
            scores, idx = self.index.search(q, k)
            pairs = zip(idx[0], scores[0])
        else:  # pragma: no cover
            s = self.vectors @ q[0]
            order = np.argsort(-s)[:k]
            pairs = zip(order, s[order])
        out = []
        for i, s in pairs:
            c = self.chunks[int(i)]
            out.append({"cita": c.cita, "documento": c.titulo, "seccion": c.seccion,
                        "url": c.url, "puntaje": round(float(s), 3), "texto": c.texto})
        return out

    def sources(self) -> dict[str, dict]:
        return {c.doc_id: {"titulo": c.titulo, "url": c.url} for c in self.chunks}
