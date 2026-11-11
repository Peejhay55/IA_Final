"""Entrena los modelos de la Parte 1 y escribe reports/metricas_parte1.json."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aire.train import main  # noqa: E402

if __name__ == "__main__":
    main()
