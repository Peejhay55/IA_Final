# Declaración de uso de IA generativa

**Curso:** SI3003 – Inteligencia Artificial, Universidad EAFIT, 2026-2
**Equipo:** William Alberto Villa · Pablo José Benítez

Conforme al pacto pedagógico del curso declaramos las herramientas de IA generativa usadas, su propósito y
el alcance de su contribución.

## 1. Herramientas usadas en el desarrollo

| Herramienta | Uso | Partes del proyecto |
|---|---|---|
| **Claude (Anthropic), modelo Claude Opus 5.5, vía claude.ai** | Asistente de programación y redacción. A partir del enunciado del curso generó la mayor parte del código inicial, el corpus parafraseado, las pruebas, los notebooks y los borradores de la documentación. | `src/aire/*`, `app.py`, `scripts/`, `evaluation/`, `tests/`, `notebooks/`, `data/corpus/`, `README.md`, `docs/informe.md` |

| **Groq (`openai/gpt-oss-120b`)** | LLM del agente durante las pruebas locales y la evaluación de 15 preguntas | `evaluation/run_eval_agente.py --backend llm`, chat del dashboard |

**Trabajo del equipo con el asistente.** El equipo eligió la idea 3.1 entre las propuestas del enunciado y
definió las instrucciones de trabajo para el asistente: usar los puntos 1 y 2 como requisitos, seguir la
rúbrica (punto 6) y los entregables (punto 5), y repartir los commits entre los dos integrantes. El
asistente generó el código, el corpus y los borradores; el equipo los ejecutó en su propio computador,
reportó los resultados y pidió las correcciones necesarias.

## 2. IA generativa dentro del producto

El agente del dashboard usa un LLM de terceros mediante un endpoint compatible con OpenAI (por defecto Groq,
`openai/gpt-oss-120b`) para decidir qué herramientas llamar y redactar las respuestas. El LLM **no** calcula
mediciones ni pronósticos: estos provienen de los datos de SIATA y de los modelos propios, y las afirmaciones
normativas provienen del corpus recuperado (RAG) con citas.

## 3. Qué no se delegó en la IA

- Los modelos de la Parte 1 (HMM, Naive Bayes, regresión logística, métricas) están implementados con NumPy
  dentro del repositorio, no invocados desde librerías que ya los resuelven; su corrección se verifica con
  pruebas automáticas (enumeración exhaustiva para el HMM y comparación con scikit-learn).
- Todas las cifras reportadas salen de ejecutar el código sobre datos reales (`reports/`); ninguna fue
  escrita a mano.
- Las fuentes normativas del corpus se consultaron en sitios oficiales y están citadas con su URL en cada
  documento; son resúmenes parafraseados y deben verificarse contra el texto oficial.

## 4. Verificación y responsabilidad

Verificaciones hechas por el equipo en su máquina local (12-nov-2026):

1. **Acceso a datos.** Se ejecutó `python scripts/download_data.py --force`: la URL oficial de SIATA
   respondió, y el equipo observó que hoy entrega el periodo 2023-07-31 → 2024-07-30 (184 485 registros,
   74.94 % válidos, 5 869 días-estación), distinto del periodo 2019-2020 del proyecto.
2. **Agente con LLM real.** Se configuró una clave de Groq en `.env` (no versionada) y se corrió la
   evaluación de 15 preguntas con el LLM. La primera corrida dio 93 % de herramienta correcta, pero solo
   67 % de citas y 60 % de contenido. Al reportar el resultado, el asistente identificó la causa: la descarga
   había sobrescrito los datos del proyecto con el periodo 2023-2024, por lo que las preguntas con fechas de
   2019 fallaban. Esto llevó a corregir el script de descarga (ahora guarda aparte), a proteger el dashboard
   contra fechas fuera de rango y a que la evaluación verifique el periodo antes de correr. Las respuestas de
   esa corrida se volvieron a puntuar tras corregir el evaluador (citas con corchetes 【 】 de gpt-oss):
   en las 9 preguntas que no dependen de fechas de 2019 el LLM obtuvo 89 % / 100 % / 100 %
   (`reports/historial/`).
3. **Contraste con la rúbrica.** El equipo pidió un checklist de la rúbrica y los entregables y lo usó para
   identificar lo pendiente antes de la entrega (evaluación con LLM, declaración, publicación en GitHub).

El equipo asume la responsabilidad total por el contenido entregado.

## 5. Uso ético

El sistema es una herramienta académica: no es consejo médico, legal ni de seguridad, ni sustituye los
pronósticos de SIATA o las declaratorias del Área Metropolitana del Valle de Aburrá. Solo usa datos
ambientales agregados, sin datos personales.
