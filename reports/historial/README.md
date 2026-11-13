# Corrida 1 de la evaluación con LLM (inválida, se conserva como registro)

Ejecutada por el equipo el 12-nov-2026 con Groq `openai/gpt-oss-120b`: herramienta correcta 93 %,
cita 67 %, contenido 60 %.

**No es válida**: `scripts/download_data.py --force` había reemplazado los datos del proyecto
(2019-2020) por el archivo que SIATA publica hoy (2023-07-31 → 2024-07-30). Las preguntas con fechas de
2019 recibieron el error «fecha fuera del histórico», como se ve en las respuestas P01, P03, P04, P05 y
P11. Se corrigió el script (la descarga ya no sobrescribe los datos) y la evaluación ahora verifica el
periodo antes de correr. Los resultados válidos están en `reports/eval_agente_llm.md`.
