"""Configuración central del proyecto: rutas, umbrales normativos y parámetros."""
from __future__ import annotations

import os
from pathlib import Path

try:  # python-dotenv es opcional
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
CORPUS_DIR = DATA_DIR / "corpus"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"

RAW_PM25 = RAW_DIR / "Datos_SIATA_Aire_pm25.json.gz"
DAILY_CSV = PROCESSED_DIR / "pm25_diario.csv"
STATIONS_CSV = PROCESSED_DIR / "estaciones.csv"
HMM_JSON = MODELS_DIR / "hmm.json"
CLASSIFIER_JSON = MODELS_DIR / "clasificador.json"
METRICS_JSON = REPORTS_DIR / "metricas_parte1.json"
INDEX_DIR = MODELS_DIR / "rag_index"

# Fuente oficial y espejo (plan B) del histórico horario de PM2.5
SIATA_HIST_URL = "https://siata.gov.co/EntregaData1/Datos_SIATA_Aire_pm25.json"
MIRROR_HIST_URL = (
    "https://raw.githubusercontent.com/SVA999/IoT-ETL/main/Datos_SIATA_Aire_pm25.json"
)
# Endpoint en vivo del geoportal SIATA (no documentado oficialmente)
SIATA_LIVE_URL = "https://geoportal.siata.gov.co/fastgeoapi/geodata/geodataJson/1/pm25_minio"

# --- Limpieza (criterios documentados en el README) ---
QUALITY_MAX = 2.5          # banderas de calidad SIATA > 2.5 se descartan
VALUE_MIN, VALUE_MAX = 0.0, 500.0
MIN_HOURS_PER_DAY = 18     # 75 % de representatividad temporal (Res. 2254/2017)

# --- Categorías ICA PM2.5 (Resolución 2254 de 2017, promedio 24 h, µg/m³) ---
ICA_BREAKS = [
    (0.0, 12.0, "Buena", "#00e400"),
    (12.1, 37.0, "Aceptable", "#ffff00"),
    (37.1, 55.0, "Dañina a la salud de grupos sensibles", "#ff7e00"),
    (55.1, 150.0, "Dañina a la salud", "#ff0000"),
    (150.1, 250.0, "Muy dañina a la salud", "#8f3f97"),
    (250.1, 500.0, "Peligrosa", "#7e0023"),
]
NORMA_DIARIA = 37.0  # µg/m³, Res. 2254/2017

# Clases del problema de clasificación (día siguiente)
CLASSES = ["Buena", "Aceptable", "Dañina"]
CLASS_EDGES = [12.0, 37.0]  # <=12 Buena, (12, 37] Aceptable, >37 Dañina
CLASS_COLORS = {"Buena": "#2e9e44", "Aceptable": "#e3c400", "Dañina": "#e8590c"}

# Estados latentes del HMM (ordenados por media creciente)
# Nombres fieles a lo aprendido (medias ≈ 11, 18 y 30 µg/m³). Corresponden a los
# estados "normal / alerta / episodio" sugeridos en el enunciado, pero el estado más
# alto NO equivale a un episodio crítico oficial (su media está en categoría Aceptable).
HMM_STATES = ["Bajo", "Moderado", "Elevado"]
HMM_N_STATES = 3

# Partición temporal principal
TRAIN_END = "2019-10-31"
TEST_START = "2019-11-01"

# --- LLM (endpoint compatible con OpenAI) ---
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "6"))  # Tmáx del loop agéntico
RAG_BACKEND = os.getenv("RAG_BACKEND", "tfidf")  # tfidf | st (sentence-transformers)
