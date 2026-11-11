# Evaluación del agente — backend `offline`

- Preguntas: 15
- Herramienta correcta: **93%**
- Citó la fuente esperada: **87%**
- Contenido clave correcto: **87%**
- Llamadas a herramientas por pregunta: 1.8
- Tiempo medio por pregunta: 0.07 s

| ID | Pregunta | Esperadas | Usadas | Herr. OK | Citas | Cita OK | Contenido OK |
|---|---|---|---|:-:|---|:-:|:-:|
| P01 | ¿Cuál fue el PM2.5 promedio en Sabaneta (SAB-RAME) el 2019-03-16? | get_pm25 | get_pm25, search_docs | ✅ | SIATA-DATOS, SALUD | ✅ | ✅ |
| P02 | ¿Cuál es la norma diaria de PM2.5 en Colombia? | search_docs | search_docs | ✅ | RES2254-NORMA | ✅ | ✅ |
| P03 | ¿Qué calidad del aire se espera mañana en Itagüí? | predict_tomorrow | get_pm25, predict_tomorrow, search_docs | ✅ | SIATA-DATOS, MODELO, SALUD | ✅ | ✅ |
| P04 | ¿Había un episodio de contaminación en el Valle de Aburrá el 2019-03-17? | estado_regional | estado_regional | ✅ | SIATA-DATOS, RES2254-NIVELES, MODELO | ✅ | ✅ |
| P05 | ¿Puedo salir a trotar en Aranjuez el 2019-03-16? | get_pm25, search_docs | get_pm25, search_docs | ✅ | SIATA-DATOS, SALUD | ✅ | ✅ |
| P06 | ¿Qué medidas de pico y placa aplica el POECA en nivel de alerta? | search_docs | estado_regional, search_docs | ✅ | SIATA-DATOS, RES2254-NIVELES, MODELO, POECA | ✅ | ✅ |
| P07 | ¿Qué recomienda la OMS como límite de PM2.5 en 24 horas? | search_docs | search_docs | ✅ | RES2254-NORMA | ❌ | ❌ |
| P08 | ¿Por qué empeora la calidad del aire en marzo en el Valle de Aburrá? | search_docs | estado_regional, search_docs | ✅ | SIATA-DATOS, RES2254-NIVELES, MODELO, SIATA-VALLE | ✅ | ✅ |
| P09 | ¿Qué estaciones de PM2.5 hay en Caldas? | listar_estaciones | get_pm25, search_docs | ❌ | SIATA-DATOS, SALUD | ✅ | ✅ |
| P10 | ¿Cómo estuvo la calidad del aire en Bello el 2021-05-01? | get_pm25 | get_pm25 | ✅ |  | ✅ | ✅ |
| P11 | ¿Qué pronosticaba el modelo para el 17 de agosto de 2019 en Belén? | predict_tomorrow | predict_tomorrow, search_docs | ✅ | MODELO, SALUD | ✅ | ✅ |
| P12 | ¿Qué significa el estado 'Episodio crítico' del modelo HMM? | search_docs | estado_regional, search_docs | ✅ | SIATA-DATOS, RES2254-NIVELES, MODELO, METODOLOGIA | ✅ | ✅ |
| P13 | ¿Qué umbral de PM2.5 define el nivel de emergencia? | search_docs | estado_regional, search_docs | ✅ | SIATA-DATOS, RES2254-NIVELES, MODELO | ✅ | ✅ |
| P14 | ¿Cómo estaba el aire en Tráfico Sur y qué tan representativa es esa estación? | get_pm25, search_docs | get_pm25, search_docs | ✅ | SIATA-DATOS, SALUD | ✅ | ✅ |
| P15 | ¿Qué deben hacer los colegios si se declara nivel de alerta? | search_docs | estado_regional, search_docs | ✅ | SIATA-DATOS, RES2254-NIVELES, MODELO | ❌ | ❌ |

## Respuestas

**P01. ¿Cuál fue el PM2.5 promedio en Sabaneta (SAB-RAME) el 2019-03-16?**

> En SAB-RAME (Sabaneta) el PM2.5 promedio del 2019-03-16 fue 52.3 µg/m³, categoría ICA «Dañina a la salud de grupos sensibles» [SIATA-DATOS]. Según «Naranja – Dañina para grupos sensibles (38 a 55 µg/m³)»: Adultos mayores, niños y personas con afecciones pulmonares o cardiovasculares pueden verse afectados si hacen actividades al aire libre por tiempo prolongado. Se recomienda a los grupos sensibles reducir o evitar el ejercicio vigoroso al aire libre, en especial en las horas de mayor tráfico (aproximadamente 6:00–10:00 y 16:00–20:00), y preferir el transporte público para no aumentar las emisiones. [SALUD] Esta información es orientativa y no es consejo médico.

**P02. ¿Cuál es la norma diaria de PM2.5 en Colombia?**

> Según «Nivel máximo permisible de PM2.5 en 24 horas»: Desde el 1 de julio de 2018 el nivel máximo permisible de material particulado fino PM2.5 para un tiempo de exposición de 24 horas es 37 µg/m³, y el de PM10 es 75 µg/m³ (artículo 2, parágrafo 1). Antes, con la Resolución 610 de 2010, el límite diario de PM2.5 era 50 µg/m³. [RES2254-NORMA]

**P03. ¿Qué calidad del aire se espera mañana en Itagüí?**

> En ITA-CJUS (Itagüí) el PM2.5 promedio del 2019-03-15 fue 47.7 µg/m³, categoría ICA «Dañina a la salud de grupos sensibles» [SIATA-DATOS]. Para el 2019-03-16 el modelo pronostica «Dañina» (Buena 0%, Aceptable 25%, Dañina 75%); el estado latente actual es «Episodio crítico» [MODELO]. Según «Naranja – Dañina para grupos sensibles (38 a 55 µg/m³)»: Adultos mayores, niños y personas con afecciones pulmonares o cardiovasculares pueden verse afectados si hacen actividades al aire libre por tiempo prolongado. Se recomienda a los grupos sensibles reducir o evitar el ejercicio vigoroso al aire libre, en especial en las horas de mayor tráfico (aproximadamente 6:00–10:00 y 16:00–20:00), y preferir el transporte público para no aumentar las emisiones. [SALUD] Esta información es orientativa y no es consejo médico.

**P04. ¿Había un episodio de contaminación en el Valle de Aburrá el 2019-03-17?**

> El 2019-03-17 el promedio de las estaciones poblacionales fue 54.6 µg/m³ y el 100.0 % superó la norma diaria de 37 µg/m³; nivel prevención (indicativo) [SIATA-DATOS] [RES2254-NIVELES]. Estados HMM: {'Episodio crítico': 19} [MODELO].

**P05. ¿Puedo salir a trotar en Aranjuez el 2019-03-16?**

> En MED-ARAN (Medellín) el PM2.5 promedio del 2019-03-16 fue 61.3 µg/m³, categoría ICA «Dañina a la salud» [SIATA-DATOS]. Según «Rojo – Dañina a la salud (56 a 150 µg/m³)»: Toda la población es susceptible de presentar afecciones por una exposición prolongada. Se recomienda evitar actividades al aire libre en la zona, especialmente las de esfuerzo físico, y los grupos sensibles deben permanecer en interiores en la medida de lo posible. [SALUD] Esta información es orientativa y no es consejo médico.

**P06. ¿Qué medidas de pico y placa aplica el POECA en nivel de alerta?**

> El 2019-03-15 el promedio de las estaciones poblacionales fue 47.4 µg/m³ y el 100.0 % superó la norma diaria de 37 µg/m³; nivel prevención (indicativo) [SIATA-DATOS] [RES2254-NIVELES]. Estados HMM: {'Episodio crítico': 19} [MODELO]. Según «Medidas de movilidad por nivel»: En prevención se amplía la restricción vehicular (pico y placa) por dígitos de placa en horas pico; en alerta la restricción se extiende a seis dígitos y a horarios más amplios para vehículos particulares y motos; en emergencia la restricción puede cubrir todos los dígitos durante casi todo el día para particulares, motos y carga. Suelen exceptuarse vehículos de emergencia, de transporte público colectivo, eléctricos y a gas natural. [POECA]

**P07. ¿Qué recomienda la OMS como límite de PM2.5 en 24 horas?**

> Según «Nivel máximo permisible de PM2.5 en 24 horas»: Desde el 1 de julio de 2018 el nivel máximo permisible de material particulado fino PM2.5 para un tiempo de exposición de 24 horas es 37 µg/m³, y el de PM10 es 75 µg/m³ (artículo 2, parágrafo 1). Antes, con la Resolución 610 de 2010, el límite diario de PM2.5 era 50 µg/m³. [RES2254-NORMA]

**P08. ¿Por qué empeora la calidad del aire en marzo en el Valle de Aburrá?**

> El 2019-03-15 el promedio de las estaciones poblacionales fue 47.4 µg/m³ y el 100.0 % superó la norma diaria de 37 µg/m³; nivel prevención (indicativo) [SIATA-DATOS] [RES2254-NIVELES]. Estados HMM: {'Episodio crítico': 19} [MODELO]. Según «Por qué hay episodios críticos en febrero–marzo y octubre–noviembre»: En las épocas secas la radiación solar calienta la superficie y genera turbulencia que mezcla el aire y saca los contaminantes del valle. En las temporadas de transición hacia las lluvias (febrero–abril y octubre–noviembre) se forma con frecuencia una capa de nubes bajas que reduce la radiación, estabiliza la atmósfera y disminuye la altura de mezcla. [SIATA-VALLE]

**P09. ¿Qué estaciones de PM2.5 hay en Caldas?**

> En CAL-JOAR (Caldas) el PM2.5 promedio del 2019-03-15 fue 48.2 µg/m³, categoría ICA «Dañina a la salud de grupos sensibles» [SIATA-DATOS]. Según «Naranja – Dañina para grupos sensibles (38 a 55 µg/m³)»: Adultos mayores, niños y personas con afecciones pulmonares o cardiovasculares pueden verse afectados si hacen actividades al aire libre por tiempo prolongado. Se recomienda a los grupos sensibles reducir o evitar el ejercicio vigoroso al aire libre, en especial en las horas de mayor tráfico (aproximadamente 6:00–10:00 y 16:00–20:00), y preferir el transporte público para no aumentar las emisiones. [SALUD] Esta información es orientativa y no es consejo médico.

**P10. ¿Cómo estuvo la calidad del aire en Bello el 2021-05-01?**

> No pude consultar la medición: La fecha 2021-05-01 está fuera del histórico disponible (2019-02-21 a 2020-02-20). Los datos son históricos de SIATA.

**P11. ¿Qué pronosticaba el modelo para el 17 de agosto de 2019 en Belén?**

> Para el 2019-08-18 el modelo pronostica «Aceptable» (Buena 1%, Aceptable 90%, Dañina 9%); el estado latente actual es «Episodio crítico» [MODELO]. Según «Amarillo – Aceptable (13 a 37 µg/m³)»: La calidad del aire es aceptable. Personas excepcionalmente sensibles a algún contaminante podrían presentar síntomas, por lo que no se les recomienda permanecer al aire libre por tiempos prolongados. [SALUD] Esta información es orientativa y no es consejo médico.

**P12. ¿Qué significa el estado 'Episodio crítico' del modelo HMM?**

> El 2019-03-15 el promedio de las estaciones poblacionales fue 47.4 µg/m³ y el 100.0 % superó la norma diaria de 37 µg/m³; nivel prevención (indicativo) [SIATA-DATOS] [RES2254-NIVELES]. Estados HMM: {'Episodio crítico': 19} [MODELO]. Según «Estado latente con un modelo oculto de Markov (HMM)»: Un HMM gaussiano de tres estados, implementado por el equipo con el algoritmo de Baum-Welch, modela el logaritmo del PM2.5 diario de cada estación. Los estados se ordenan por su media y se nombran Normal (media cercana a 11 µg/m³), Alerta (cerca de 18 µg/m³) y Episodio crítico (cerca de 30 µg/m³). [METODOLOGIA]

**P13. ¿Qué umbral de PM2.5 define el nivel de emergencia?**

> El 2019-03-15 el promedio de las estaciones poblacionales fue 47.4 µg/m³ y el 100.0 % superó la norma diaria de 37 µg/m³; nivel prevención (indicativo) [SIATA-DATOS] [RES2254-NIVELES]. Estados HMM: {'Episodio crítico': 19} [MODELO]. Según «Umbrales de PM2.5 para cada nivel»: Según la tabla 4 de la resolución, para PM2.5 con exposición de 24 horas: nivel de Prevención entre 38 y 55 µg/m³, nivel de Alerta entre 56 y 150 µg/m³ y nivel de Emergencia a partir de 151 µg/m³. Para PM10 los rangos son 155–254 (prevención), 255–354 (alerta) y 355 µg/m³ o más (emergencia). [RES2254-NIVELES]

**P14. ¿Cómo estaba el aire en Tráfico Sur y qué tan representativa es esa estación?**

> En SUR-TRAF (Sabaneta) el PM2.5 promedio del 2019-03-15 fue 59.7 µg/m³, categoría ICA «Dañina a la salud» [SIATA-DATOS]. Según «Rojo – Dañina a la salud (56 a 150 µg/m³)»: Toda la población es susceptible de presentar afecciones por una exposición prolongada. Se recomienda evitar actividades al aire libre en la zona, especialmente las de esfuerzo físico, y los grupos sensibles deben permanecer en interiores en la medida de lo posible. [SALUD] Esta información es orientativa y no es consejo médico.

**P15. ¿Qué deben hacer los colegios si se declara nivel de alerta?**

> El 2019-03-15 el promedio de las estaciones poblacionales fue 47.4 µg/m³ y el 100.0 % superó la norma diaria de 37 µg/m³; nivel prevención (indicativo) [SIATA-DATOS] [RES2254-NIVELES]. Estados HMM: {'Episodio crítico': 19} [MODELO]. Según «Cómo se calcula la declaratoria»: La declaratoria puede hacerse por constatación (mediciones) o por pronóstico con modelos (artículo 11). Con monitoreo automático, se declara el nivel cuando las medias móviles de 24 horas permanecen dentro del rango correspondiente durante más del 75 % del tiempo en un periodo de 48 horas consecutivas. [RES2254-NIVELES]
