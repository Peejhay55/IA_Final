# Evaluación del agente — backend `offline`

- Preguntas: 15
- Herramienta correcta: **80%**
- Citó la fuente esperada: **47%**
- Contenido clave correcto: **40%**
- Llamadas a herramientas por pregunta: 1.5
- Tiempo medio por pregunta: 0.37 s

| ID | Pregunta | Esperadas | Usadas | Herr. OK | Citas | Cita OK | Contenido OK |
|---|---|---|---|:-:|---|:-:|:-:|
| P01 | ¿Cuál fue el PM2.5 promedio en Sabaneta (SAB-RAME) el 2019-03-16? | get_pm25 | get_pm25 | ✅ |  | ❌ | ❌ |
| P02 | ¿Cuál es la norma diaria de PM2.5 en Colombia? | search_docs | search_docs | ✅ | RES2254-NORMA | ✅ | ✅ |
| P03 | ¿Qué calidad del aire se espera mañana en Itagüí? | predict_tomorrow | get_pm25, predict_tomorrow | ✅ |  | ❌ | ❌ |
| P04 | ¿Había un episodio de contaminación en el Valle de Aburrá el 2019-03-17? | estado_regional | get_pm25 | ❌ |  | ❌ | ❌ |
| P05 | ¿Puedo salir a trotar en Aranjuez el 2019-03-16? | get_pm25, search_docs | get_pm25, search_docs | ✅ | SALUD | ✅ | ❌ |
| P06 | ¿Qué medidas de pico y placa aplica el POECA en nivel de alerta? | search_docs | estado_regional, search_docs | ✅ | POECA | ✅ | ✅ |
| P07 | ¿Qué recomienda la OMS como límite de PM2.5 en 24 horas? | search_docs | search_docs | ✅ | RES2254-NORMA | ❌ | ❌ |
| P08 | ¿Por qué empeora la calidad del aire en marzo en el Valle de Aburrá? | search_docs | get_pm25, search_docs | ✅ | SIATA-VALLE | ✅ | ✅ |
| P09 | ¿Qué estaciones de PM2.5 hay en Caldas? | listar_estaciones | get_pm25, search_docs | ❌ | SIATA-VALLE | ❌ | ❌ |
| P10 | ¿Cómo estuvo la calidad del aire en Bello el 2021-05-01? | get_pm25 | get_pm25 | ✅ |  | ✅ | ✅ |
| P11 | ¿Qué pronosticaba el modelo para el 17 de agosto de 2019 en Belén? | predict_tomorrow | predict_tomorrow, search_docs | ✅ | SIATA-VALLE | ❌ | ❌ |
| P12 | ¿Qué significa el estado 'Elevado' del modelo HMM? | search_docs | search_docs | ✅ | METODOLOGIA | ✅ | ✅ |
| P13 | ¿Qué umbral de PM2.5 define el nivel de emergencia? | search_docs | estado_regional, search_docs | ✅ | RES2254-NIVELES | ✅ | ✅ |
| P14 | ¿Cómo estaba el aire en Tráfico Sur y qué tan representativa es esa estación? | get_pm25, search_docs | get_pm25 | ❌ |  | ❌ | ❌ |
| P15 | ¿Qué deben hacer los colegios si se declara nivel de alerta? | search_docs | estado_regional, search_docs | ✅ | RES2254-NIVELES | ❌ | ❌ |

## Respuestas

**P01. ¿Cuál fue el PM2.5 promedio en Sabaneta (SAB-RAME) el 2019-03-16?**

> No pude consultar la medición: La fecha 2019-03-16 está fuera del histórico disponible (2023-07-31 a 2024-07-30). Los datos son históricos de SIATA.

**P02. ¿Cuál es la norma diaria de PM2.5 en Colombia?**

> Según «Nivel máximo permisible de PM2.5 en 24 horas»: Desde el 1 de julio de 2018 el nivel máximo permisible de material particulado fino PM2.5 para un tiempo de exposición de 24 horas es 37 µg/m³, y el de PM10 es 75 µg/m³ (artículo 2, parágrafo 1). Antes, con la Resolución 610 de 2010, el límite diario de PM2.5 era 50 µg/m³. [RES2254-NORMA]

**P03. ¿Qué calidad del aire se espera mañana en Itagüí?**

> No pude consultar la medición: La fecha 2019-03-15 está fuera del histórico disponible (2023-07-31 a 2024-07-30). Los datos son históricos de SIATA. No pude generar el pronóstico: La fecha 2019-03-15 está fuera del histórico disponible (2023-07-31 a 2024-07-30). Los datos son históricos de SIATA.

**P04. ¿Había un episodio de contaminación en el Valle de Aburrá el 2019-03-17?**

> No pude consultar la medición: La fecha 2019-03-17 está fuera del histórico disponible (2023-07-31 a 2024-07-30). Los datos son históricos de SIATA.

**P05. ¿Puedo salir a trotar en Aranjuez el 2019-03-16?**

> No pude consultar la medición: La fecha 2019-03-16 está fuera del histórico disponible (2023-07-31 a 2024-07-30). Los datos son históricos de SIATA. Según «Quiénes son los grupos sensibles»: Se consideran grupos sensibles a la contaminación por material particulado las personas con enfermedades respiratorias como asma o EPOC, las personas con enfermedades cardiacas, los niños y adolescentes, los adultos mayores, las mujeres embarazadas y quienes practican deporte o actividad física intensa al aire libre. [SALUD] Esta información es orientativa y no es consejo médico.

**P06. ¿Qué medidas de pico y placa aplica el POECA en nivel de alerta?**

> No pude consultar el estado regional: La fecha 2019-03-15 está fuera del histórico disponible (2023-07-31 a 2024-07-30). Los datos son históricos de SIATA. Según «Medidas de movilidad por nivel»: En prevención se amplía la restricción vehicular (pico y placa) por dígitos de placa en horas pico; en alerta la restricción se extiende a seis dígitos y a horarios más amplios para vehículos particulares y motos; en emergencia la restricción puede cubrir todos los dígitos durante casi todo el día para particulares, motos y carga. Suelen exceptuarse vehículos de emergencia, de transporte público colectivo, eléctricos y a gas natural. [POECA]

**P07. ¿Qué recomienda la OMS como límite de PM2.5 en 24 horas?**

> Según «Nivel máximo permisible de PM2.5 en 24 horas»: Desde el 1 de julio de 2018 el nivel máximo permisible de material particulado fino PM2.5 para un tiempo de exposición de 24 horas es 37 µg/m³, y el de PM10 es 75 µg/m³ (artículo 2, parágrafo 1). Antes, con la Resolución 610 de 2010, el límite diario de PM2.5 era 50 µg/m³. [RES2254-NORMA]

**P08. ¿Por qué empeora la calidad del aire en marzo en el Valle de Aburrá?**

> No pude consultar la medición: La fecha 2019-03-15 está fuera del histórico disponible (2023-07-31 a 2024-07-30). Los datos son históricos de SIATA. Según «Por qué hay episodios críticos en febrero–marzo y octubre–noviembre»: En las épocas secas la radiación solar calienta la superficie y genera turbulencia que mezcla el aire y saca los contaminantes del valle. En las temporadas de transición hacia las lluvias (febrero–abril y octubre–noviembre) se forma con frecuencia una capa de nubes bajas que reduce la radiación, estabiliza la atmósfera y disminuye la altura de mezcla. [SIATA-VALLE]

**P09. ¿Qué estaciones de PM2.5 hay en Caldas?**

> No pude consultar la medición: La fecha 2019-03-15 está fuera del histórico disponible (2023-07-31 a 2024-07-30). Los datos son históricos de SIATA. Según «Tipos de estaciones»: SIATA clasifica las estaciones de PM2.5 en estaciones de representatividad poblacional, que describen la exposición de la población en zonas residenciales y son las que se usan para el POECA, y estaciones de tráfico o industriales (por ejemplo Tráfico Centro y Tráfico Sur), que miden el impacto directo de una vía o una industria en un punto. Si una estación poblacional marca naranja o rojo es probable que, además de las emisiones, existan condiciones meteorológicas desfavorables para la dispersión. [SIATA-VALLE]

**P10. ¿Cómo estuvo la calidad del aire en Bello el 2021-05-01?**

> No pude consultar la medición: La fecha 2021-05-01 está fuera del histórico disponible (2023-07-31 a 2024-07-30). Los datos son históricos de SIATA.

**P11. ¿Qué pronosticaba el modelo para el 17 de agosto de 2019 en Belén?**

> No pude generar el pronóstico: La fecha 2019-08-17 está fuera del histórico disponible (2023-07-31 a 2024-07-30). Los datos son históricos de SIATA. Según «Patrones típicos del PM2.5»: Las concentraciones horarias muestran un pico en la mañana asociado al tráfico y a la baja altura de la capa de mezcla. En el histórico SIATA usado en este proyecto (febrero de 2019 a febrero de 2020) el domingo es el día con menor promedio (unos 17 µg/m³ frente a 21–22 µg/m³ de martes a viernes); febrero y marzo presentan los promedios mensuales más altos (30–33 µg/m³) y junio y julio los más bajos (cerca de 15 µg/m³). [SIATA-VALLE]

**P12. ¿Qué significa el estado 'Elevado' del modelo HMM?**

> Según «Estado latente con un modelo oculto de Markov (HMM)»: Un HMM gaussiano de tres estados, implementado por el equipo con el algoritmo de Baum-Welch, modela el logaritmo del PM2.5 diario de cada estación. Los estados se ordenan por su media y se nombran Bajo (media cercana a 11 µg/m³), Moderado (cerca de 18 µg/m³) y Elevado (cerca de 30 µg/m³). [METODOLOGIA]

**P13. ¿Qué umbral de PM2.5 define el nivel de emergencia?**

> No pude consultar el estado regional: La fecha 2019-03-15 está fuera del histórico disponible (2023-07-31 a 2024-07-30). Los datos son históricos de SIATA. Según «Umbrales de PM2.5 para cada nivel»: Según la tabla 4 de la resolución, para PM2.5 con exposición de 24 horas: nivel de Prevención entre 38 y 55 µg/m³, nivel de Alerta entre 56 y 150 µg/m³ y nivel de Emergencia a partir de 151 µg/m³. Para PM10 los rangos son 155–254 (prevención), 255–354 (alerta) y 355 µg/m³ o más (emergencia). [RES2254-NIVELES]

**P14. ¿Cómo estaba el aire en Tráfico Sur y qué tan representativa es esa estación?**

> No pude consultar la medición: La fecha 2019-03-15 está fuera del histórico disponible (2023-07-31 a 2024-07-30). Los datos son históricos de SIATA.

**P15. ¿Qué deben hacer los colegios si se declara nivel de alerta?**

> No pude consultar el estado regional: La fecha 2019-03-15 está fuera del histórico disponible (2023-07-31 a 2024-07-30). Los datos son históricos de SIATA. Según «Cómo se calcula la declaratoria»: La declaratoria puede hacerse por constatación (mediciones) o por pronóstico con modelos (artículo 11). Con monitoreo automático, se declara el nivel cuando las medias móviles de 24 horas permanecen dentro del rango correspondiente durante más del 75 % del tiempo en un periodo de 48 horas consecutivas. [RES2254-NIVELES]
