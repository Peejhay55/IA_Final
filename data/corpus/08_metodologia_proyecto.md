---
id: METODOLOGIA
titulo: Metodología, modelos y limitaciones de este proyecto (SI3003 – EAFIT)
fuente: Documentación técnica del propio proyecto (README e informe del repositorio).
url: docs/informe.md
nota: Documento escrito por el equipo para que el agente pueda explicar cómo funcionan sus herramientas.
---

## Datos usados por el agente
El agente usa el histórico oficial de PM2.5 horario publicado por SIATA (archivo EntregaData1) para 21 estaciones del Valle de Aburrá entre el 21 de febrero de 2019 y el 20 de febrero de 2020. Se descartan valores centinela (-9999), registros con bandera de calidad de SIATA mayor a 2,5 y valores fuera del rango 0–500 µg/m³. Un día es válido si tiene al menos 18 horas con dato (75 % de representatividad). Los datos son históricos: el agente no conoce la calidad del aire de hoy salvo que la consulta en vivo al geoportal de SIATA funcione.

## Estado latente con un modelo oculto de Markov (HMM)
Un HMM gaussiano de tres estados, implementado por el equipo con el algoritmo de Baum-Welch, modela el logaritmo del PM2.5 diario de cada estación. Los estados se ordenan por su media y se nombran Normal (media cercana a 11 µg/m³), Alerta (cerca de 18 µg/m³) y Episodio crítico (cerca de 30 µg/m³). Son regímenes estadísticos persistentes (duran en promedio entre 13 y 18 días), no las declaratorias oficiales del POECA. El filtrado forward entrega la probabilidad de cada estado usando solo información pasada.

## Pronóstico de la categoría del día siguiente
Una regresión logística multinomial, implementada desde cero, predice si el día siguiente será Buena (≤12 µg/m³), Aceptable (12–37 µg/m³) o Dañina (>37 µg/m³, supera la norma diaria). Usa el PM2.5 de los últimos días, la media regional, las probabilidades del HMM, el día de la semana y el mes. Se entrenó con datos hasta el 31 de octubre de 2019 y se evaluó entre noviembre de 2019 y febrero de 2020, comparándola con persistencia (mañana igual a hoy), climatología y el HMM solo.

## Resultados principales
En el periodo de prueba la regresión logística detecta el 84 % de los días que superan la norma, frente al 44 % de la persistencia, a costa de más falsas alarmas; su exactitud balanceada es 0,74 frente a 0,59 de la persistencia, aunque su F1-macro (0,57) queda ligeramente por debajo de la persistencia (0,59). En la validación temporal de seis meses supera a la persistencia en F1-macro (0,53 frente a 0,51) y en exactitud balanceada (0,56 frente a 0,51). El HMM solo ofrece las probabilidades mejor calibradas (log-loss 0,41 frente a 0,53 de la climatología). Ningún modelo domina en todas las métricas, por lo que el agente reporta las probabilidades de ambos.

## Limitaciones
El histórico cubre solo un año (2019–2020), sin variables meteorológicas, y los días con norma excedida son pocos, lo que hace inestables las métricas de esa clase. El pronóstico es por estación y no reemplaza los pronósticos oficiales de SIATA ni las declaratorias del Área Metropolitana. Las respuestas del agente son informativas y no constituyen consejo médico; ante síntomas se debe consultar a un profesional de la salud.
