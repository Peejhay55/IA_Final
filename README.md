# 🌫️ Agente de calidad del aire del Valle de Aburrá

**SI3003 – Inteligencia Artificial · Universidad EAFIT · Proyecto final 2026-1 (idea 3.1)**

Integrantes: **William Alberto Villa** · **Pablo José Benítez**

Los ciudadanos ven a diario un número de PM2.5 sin saber qué significa ni qué hacer. Este proyecto combina
datos reales de **SIATA**, un **modelo oculto de Markov** y un **clasificador implementados por el equipo**
(Parte 1) con un **agente LLM con RAG y herramientas** (Parte 2), en un **dashboard Streamlit** donde el
usuario elige estación y fecha, ve mapas y series, y conversa con el agente.

```
          SIATA (PM2.5 horario, 21 estaciones)
                      │  ETL: limpieza + promedio 24 h (≥18 h válidas)
                      ▼
   ┌──────────── Parte 1 (NumPy, propio) ────────────┐
   │ HMM gaussiano 3 estados (Baum-Welch, forward,   │
   │ Viterbi) ──► P(estado | historia) ──► regresión │
   │ logística multinomial ──► clase ICA de mañana   │
   └───────────────┬─────────────────────────────────┘
                   │ herramientas
   ┌───────────────▼──────── Parte 2 ────────────────┐
   │ Agente LLM (loop manual, Tmáx=6, tool calling)  │
   │  get_pm25 · predict_tomorrow · estado_regional  │
   │  listar_estaciones · search_docs (RAG + FAISS)  │
   │  corpus: Res. 2254/2017, POECA, OMS 2021, SIATA │
   └───────────────┬─────────────────────────────────┘
                   ▼
   Dashboard Streamlit: mapa ICA · series · estados HMM · pronóstico · chat con traza y citas
```

## 1. Ejecución rápida (reproducible)

```bash
git clone <url-del-repo> && cd agente-calidad-aire-aburra
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # (opcional) pegue su LLM_API_KEY de Groq
streamlit run app.py        # abre http://localhost:8501
```

- **Todo lo necesario está en el repositorio**: datos (`data/`), modelos entrenados (`models/`), corpus RAG
  (`data/corpus/`) y métricas (`reports/`). La app arranca sin red y sin clave.
- **Sin `LLM_API_KEY`** el chat funciona en *modo de respaldo* (router determinista con las mismas
  herramientas y citas). **Con clave** se usa el LLM real; si el proveedor falla durante la demo, el agente
  reintenta una vez y responde con el modo de respaldo avisando al usuario, así la demostración no se cae.
- LLM por defecto: Groq `openai/gpt-oss-120b` (capa gratuita). Groq retiró `llama-3.3-70b-versatile` el
  16-ago-2026. Cualquier endpoint compatible con OpenAI sirve (NVIDIA NIM, Ollama): ver `.env.example`.

### Reproducir los resultados desde cero

```bash
python scripts/download_data.py --force    # SIATA oficial → espejo GitHub → copia local (plan B)
python scripts/train.py                    # HMM + clasificadores, selección temporal, métricas (~1 min)
python evaluation/eval_rag.py              # hit@1 / hit@3 / MRR de la recuperación
python evaluation/run_eval_agente.py --backend offline
python evaluation/run_eval_agente.py --backend llm --pausa 2     # requiere LLM_API_KEY
pytest                                      # 20 pruebas (HMM vs enumeración, NB vs sklearn, loop agéntico)
```

Los cuadernos `notebooks/01_eda.ipynb`, `02_modelos_parte1.ipynb` y `03_agente_rag.ipynb` están ejecutados
y muestran el análisis con sus salidas.

## 2. Datos

| Fuente | Uso | Acceso |
|---|---|---|
| **SIATA – AMVA**, `https://siata.gov.co/EntregaData1/Datos_SIATA_Aire_pm25.json` | PM2.5 horario de 21 estaciones, 21-feb-2019 → 20-feb-2020 (183 981 registros) | Copia comprimida en `data/raw/`; `scripts/download_data.py` intenta la URL oficial y luego un espejo público en GitHub (`SVA999/IoT-ETL`) con el mismo archivo |
| **Geoportal SIATA** (`geoportal.siata.gov.co/fastgeoapi/...pm25_minio`) | Dato en vivo opcional (`get_pm25(en_vivo=true)`) | Si no responde, se usa el histórico |
| Res. 2254/2017, POECA (Acuerdo Metropolitano 04/2018), OMS 2021, SIATA/Alcaldía de Medellín | Corpus RAG (`data/corpus/*.md`, resúmenes parafraseados con URL de la fuente) | Público |

**Limpieza** (`src/aire/data.py`): se eliminan centinelas (−9999), banderas de calidad SIATA > 2.5 y valores
fuera de 0–500 µg/m³ → 97.3 % de registros válidos. Promedio diario por estación con ≥ 18 horas válidas
(75 %); la marca horaria de SIATA es fin de hora. Resultado: 7 525 días-estación.

**Uso responsable**: solo datos ambientales agregados, sin datos personales; se acredita a SIATA – AMVA como
fuente. El archivo histórico se redistribuye comprimido únicamente para garantizar la reproducibilidad
académica.

## 3. Parte 1 – Técnica clásica implementada por el equipo

| Componente | Archivo | Detalle |
|---|---|---|
| HMM gaussiano | `src/aire/hmm.py` | 3 estados sobre log(PM2.5) diario; forward-backward escalado, Baum-Welch con múltiples secuencias (una por estación), Viterbi, datos faltantes marginalizados, predicción a un paso |
| Naive Bayes gaussiano y regresión logística multinomial | `src/aire/classifier.py` | Adam + L2 + pesos de clase; métricas (matriz de confusión, F1, exactitud balanceada) también propias |
| Pipeline | `src/aire/forecast.py` | Variables: PM2.5 de hoy/ayer, media 3 días, media regional, P(estado HMM) filtrada, fin de semana, mes |

**Problema:** predecir la clase del día siguiente por estación: *Buena* (≤12 µg/m³), *Aceptable* (12–37) o
*Dañina* (>37, supera la norma diaria). **Partición temporal:** entrenamiento hasta 31-oct-2019, prueba
1-nov-2019 → 20-feb-2020 (2 238 casos, 68 días-estación sobre la norma). Los hiperparámetros se eligen con
validación temporal **dentro** del entrenamiento (5 meses), nunca con la prueba.

| Modelo (prueba) | Exactitud | F1-macro | Exactitud bal. | Recall excedencia | F1 excedencia | Log-loss |
|---|---|---|---|---|---|---|
| **Regresión logística + estados HMM** | 0.768 | 0.574 | **0.737** | **0.838** | 0.396 | 0.522 |
| Regresión logística sin HMM (ablación) | 0.783 | 0.583 | 0.732 | 0.838 | 0.413 | 0.530 |
| Naive Bayes gaussiano + HMM | 0.641 | 0.484 | 0.736 | 0.912 | 0.280 | 2.093 |
| HMM solo (pronóstico a un paso) | 0.834 | 0.449 | 0.454 | 0.000 | 0.000 | **0.413** |
| Línea base: persistencia | 0.831 | **0.594** | 0.593 | 0.441 | **0.448** | — |
| Línea base: climatología | 0.849 | 0.306 | 0.333 | 0.000 | 0.000 | 0.529 |

Validación temporal con ventana creciente (6 meses, sep-2019 → feb-2020, el HMM se reentrena en cada
pliegue): regresión logística + HMM F1-macro **0.525** vs persistencia 0.511; exactitud balanceada
**0.558** vs 0.506. HMM: log-verosimilitud por observación en prueba −0.17 (3 estados) vs −0.47
(gaussiana i.i.d.).

**Lectura honesta:** el clasificador detecta 84 % de los días que superan la norma (persistencia 44 %), pero
con muchas falsas alarmas (precisión 0.26). La persistencia sigue siendo competitiva en F1-macro en la
partición principal. El HMM solo da las probabilidades mejor calibradas. La ablación indica que las
probabilidades del HMM **no** mejoran apreciablemente al clasificador; su valor está en el pronóstico
probabilístico y en interpretar el régimen. Detalle: `reports/metricas_parte1.json` y el notebook 02.

## 4. Parte 2 – Agente LLM con RAG

- **Loop agéntico manual** (`src/aire/agent.py`): pensar → pedir herramientas → ejecutar → observar → …,
  con **Tmáx = 6** pasos (al alcanzarlo se fuerza la respuesta con `tool_choice="none"`).
- **Herramientas** (`src/aire/tools.py`): `get_pm25(estacion, fecha, dias, en_vivo)`,
  `predict_tomorrow(estacion, fecha)`, `estado_regional(fecha)`, `listar_estaciones(municipio)`,
  `search_docs(query, k)`. Los **errores vuelven como observación** (`{"error": ...}`) para que el LLM se
  corrija; la fecha y estación del tablero se inyectan si el usuario no las menciona.
- **RAG** (`src/aire/rag.py`): 8 documentos → 43 fragmentos por sección; embeddings TF-IDF (palabras +
  n-gramas de caracteres, sin tildes, stopwords en español) o `sentence-transformers` (opcional);
  índice **FAISS** `IndexFlatIP`; expansión de consulta con un tesauro mínimo del dominio
  (p. ej. *trotar → actividad física al aire libre*). Recuperación en 20 consultas fijas:
  **hit@3 = 1.00, hit@1 = 0.85, MRR = 0.93** (sin expansión: hit@1 = 0.80).
- **Citas**: cada fragmento y cada herramienta traen un código (`[RES2254-NORMA]`, `[POECA]`, `[SALUD]`,
  `[SIATA-DATOS]`, `[MODELO]`, …). Se extraen de la respuesta y se listan con su URL en el chat.
- **Manejo de errores del LLM**: un reintento y luego respuesta del router de respaldo con aviso.

### Evaluación del agente (15 preguntas fijas, `evaluation/preguntas_agente.json`)

Se mide si llamó a la **herramienta correcta**, si **citó la fuente** esperada y si la respuesta contiene el
**dato clave** (p. ej. "37" para la norma). Resultados en `reports/eval_agente_*.md`.

| Backend | Herramienta correcta | Citó la fuente | Contenido correcto |
|---|---|---|---|
| Router de respaldo sin LLM (línea base) | 93 % | 87 % | 87 % |
| LLM (`openai/gpt-oss-120b`) | *ejecutar `run_eval_agente.py --backend llm`* | | |

## 5. Dashboard (`app.py`)

Barra lateral: estación, fecha («hoy»), estaciones a comparar, ventana de días, motor del chat.
Pestañas: **Mapa y series** (mapa con colores oficiales del ICA, serie de tiempo con bandas ICA y norma
diaria, tabla de datos) · **Pronóstico y modelo** (probabilidades de los tres modelos, estados latentes del
HMM, tabla de métricas vs líneas base) · **Chat** (preguntas de ejemplo, fuentes y traza de herramientas).

## 6. Limitaciones

- Un solo año de histórico (2019-2020) sin variables meteorológicas; pocos días sobre la norma en prueba
  (68), por lo que las métricas de esa clase son inestables y la selección de hiperparámetros quedó en
  empate técnico (se resolvió con una regla fija de desempate por log-loss).
- El HMM comparte parámetros entre estaciones: las de nivel base alto pasan más tiempo en el estado
  *Elevado* (media ≈ 30 µg/m³, categoría Aceptable), que **no** equivale a un episodio crítico oficial.
- El "hoy" del tablero es una fecha histórica; el dato en vivo depende de un endpoint no documentado de SIATA.
- El corpus son resúmenes parafraseados por el equipo; el tesauro y las preguntas de evaluación fueron
  escritos por el mismo equipo (riesgo de sobreajuste).
- **No es consejo médico, legal ni de seguridad**, ni un pronóstico o declaratoria oficial del AMVA/SIATA.

## 7. Estructura del repositorio

```
app.py                     dashboard Streamlit
src/aire/                  config, data (ETL), hmm, classifier, forecast, train, rag, tools, agent
scripts/                   download_data.py, train.py
data/raw|processed|corpus  datos SIATA (crudo comprimido y diario) y corpus RAG
models/                    hmm.json, clasificador.json (entrenados)
evaluation/                preguntas del agente, consultas RAG y scripts de evaluación
reports/                   métricas, validación temporal, evaluaciones, figuras
notebooks/                 01 EDA · 02 Parte 1 · 03 Agente y RAG (ejecutados)
tests/                     pruebas con pytest (incluye LLM simulado)
docs/                      informe (≤ 4 páginas)
DECLARACION_IA.md          declaración de uso de IA generativa
```

## 8. Créditos

Datos: **SIATA – Área Metropolitana del Valle de Aburrá y Alcaldía de Medellín**. Normativa: Ministerio de
Ambiente y Desarrollo Sostenible (Res. 2254 de 2017), AMVA (POECA), OMS (2021). Ver
[`DECLARACION_IA.md`](DECLARACION_IA.md) para el uso de IA generativa.
