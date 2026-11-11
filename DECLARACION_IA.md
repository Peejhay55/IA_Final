# Declaración de uso de IA generativa

**Curso:** SI3003 – Inteligencia Artificial, Universidad EAFIT, 2026-1
**Equipo:** William Alberto Villa · Pablo José Benítez

Conforme al pacto pedagógico del curso declaramos las herramientas de IA generativa usadas, su propósito y
el alcance de su contribución.

## 1. Herramientas usadas en el desarrollo

| Herramienta | Uso | Partes del proyecto |
|---|---|---|
| **Claude (Anthropic), modelo Claude Opus 5.5, vía claude.ai** | Asistente de programación y redacción. A partir del enunciado del curso generó la mayor parte del código inicial, el corpus parafraseado, las pruebas, los notebooks y los borradores de la documentación. | `src/aire/*`, `app.py`, `scripts/`, `evaluation/`, `tests/`, `notebooks/`, `data/corpus/`, `README.md`, `docs/informe.md` |

> **[Completar por el equipo]** Agreguen aquí cualquier otra herramienta que hayan usado (p. ej. Copilot,
> ChatGPT) y describan con precisión qué revisaron, modificaron o escribieron ustedes mismos.

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

> **[Completar por el equipo]** Describan cómo revisaron y comprendieron cada módulo (por ejemplo: quién
> revisó el HMM y la selección de hiperparámetros, quién probó el agente con la API real, qué cambios
> hicieron tras la revisión). El equipo asume la responsabilidad total por el contenido entregado y debe ser
> capaz de explicar cada componente.

## 5. Uso ético

El sistema es una herramienta académica: no es consejo médico, legal ni de seguridad, ni sustituye los
pronósticos de SIATA o las declaratorias del Área Metropolitana del Valle de Aburrá. Solo usa datos
ambientales agregados, sin datos personales.
