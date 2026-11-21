# Diccionario de indicadores — Dacora

Cada cifra que muestra Dacora usa **exactamente** esta definición, con su fuente, versión y
fecha/hora de corte (constitución, principio V). No se admiten sinónimos sueltos.

> Todos los valores de la demo provienen del escenario **SIMULADO** del sismo del 10 ago 2026.

| Clave (`indicator`) | Nombre en pantalla | Unidad | Fuente | Definición | Meta P0 |
|---|---|---|---|---|---|
| `reports_received` | Reportes recibidos | conteo | `api` | Reportes registrados (todos los canales), sin contar reenvíos idempotentes del mismo `client_uuid`. | — |
| `incidents_consolidated` | Incidentes consolidados | conteo | `api` | Incidentes con al menos un reporte vigente (no descartado). | — |
| `duplicate_detection_rate` | Duplicados detectados | % | `evaluate_kpis.py` | Reportes que la verdad marca como duplicados y que quedaron en el **mismo incidente** que el reporte original ÷ total de duplicados reales. | > 90 % |
| `fake_detection_rate` | Falsos detectados | % | `evaluate_kpis.py` | Reportes falsos cuyo incidente quedó con etiqueta **Posible falso** (trust < 25) o clasificados como `rumor_informacion` ÷ total de falsos reales. | > 90 % |
| `false_positive_rate` | Legítimos marcados como falsos | % | `evaluate_kpis.py` | Reportes legítimos (únicos o duplicados) cuyo incidente quedó como Posible falso o rumor ÷ total de legítimos. | lo más bajo posible |
| `critical_auto_discarded` | Críticos descartados por la IA | conteo | `evaluate_kpis.py` | Reportes con riesgo vital en estado `descartado` sin una acción humana en la bitácora. | **0** |
| `critical_recall` | Críticos identificados | % | `evaluate_kpis.py` | Reportes críticos reales marcados con riesgo vital ÷ total de críticos reales. | ≥ 98 % |
| `time_to_consolidated_map_min` | Hecho en el mapa en (p90) | min | `evaluate_kpis.py` | Percentil 90, sobre los hechos reales recibidos, de los minutos simulados entre el primer reporte de un hecho y el momento en que su incidente queda ubicado en el mapa. Referencia del evento real: las cifras consolidadas tardaron días (1.449 → 2.700 → 1.512 viviendas entre el 13 y el 15 de agosto). | minutos, no días |
| `p95_processing_ms` | Procesamiento por reporte (p95) | ms | `api` | Percentil 95 del tiempo de procesamiento del motor por reporte. | < 1.000 ms |
| `critical_without_dispatch` | Críticos sin despacho | conteo | `api` | Incidentes con riesgo vital (abiertos, en revisión o verificados) sin ningún despacho que no esté cancelado. | **0** |
| `median_time_to_dispatch_min` | Tiempo a despacho de críticos (mediana) | min | `api` | Mediana, sobre los incidentes con riesgo vital despachados, de los minutos entre la consolidación del incidente en Dacora y su primer despacho no cancelado. Se mide en hora real, no en la hora sintética del sismo. | minutos |
| `double_dispatch_prevented` | Despachos dobles evitados | conteo | `api` | Intentos de despachar un incidente que ya tenía un despacho activo, bloqueados por no ser un refuerzo justificado (evento `despacho_doble_bloqueado` en la bitácora). | — |

## Indicadores de recuperación (`GET /api/v1/recovery/summary`)

Fuente: módulo de recuperación de Dacora (SIMULADO), con versión y fecha de corte. Para el rol
público las cifras menores a 5 se suprimen (se muestran como "< 5").

| Clave | Nombre en pantalla | Unidad | Definición |
|---|---|---|---|
| `predios_evaluados` | Predios evaluados | conteo | Predios distintos con al menos una evaluación de habitabilidad. Un predio es el código catastral o, si no hay, la manzana + dirección normalizada. |
| `visitas` | Visitas de inspección | conteo | Evaluaciones registradas (incluye visitas repetidas al mismo predio). `visitas − predios_evaluados` = visitas repetidas. |
| `predios_verde` / `predios_amarillo` / `predios_rojo` | Habitables · Uso restringido · No habitables | conteo | Predios según el color de su **última** evaluación. Verde admite daño menor; amarillo, menor o mediano con uso restringido; rojo, mediano, mayor o colapso (NSR-10). |
| `hogares` | Hogares en el censo único | conteo | Hogares distintos, identificados por HMAC con sal del documento del jefe de hogar. |
| `personas` | Personas damnificadas | conteo | Suma de integrantes de los hogares del censo único. |
| `rud_inscritos` | Hogares inscritos en el RUD | conteo | Hogares del censo con estado `inscrito` en el Registro Único de Damnificados. |
| `ayudas` | Ayudas entregadas | conteo | Entregas registradas (subsidio de arriendo, kit, mercado, cupo en albergue). |
| `ayudas_duplicadas` | Ayudas repetidas con justificación | conteo | Entregas del mismo tipo al mismo hogar dentro de su plazo (30 días; 7 para mercado) que se autorizaron con justificación. Sin justificación, la entrega se bloquea y no se cuenta. |
| `albergue_personas` / `albergue_mascotas` | Personas · Mascotas en albergue | conteo | Ocupación actual sumada de los albergues. |
| `albergue_capacidad` | Capacidad de albergues | conteo | Cupos totales de los albergues registrados. |

## Tablero de recuperación unificado (`GET /api/v1/recovery/dashboard`)

Solo para PMU/COE. Regla de oro: cada cifra lleva su nombre de este diccionario, fuente, versión y
hora de corte, y se cuentan **predios únicos, no visitas**. **Ninguna cifra es inventada**: sale
del registro de Dacora o de la copia fechada de una fuente pública; lo que no tiene fuente se
muestra como *Sin fuente* nombrando la entidad del convenio, nunca con un número estimado.

### Fuentes y respaldo

| Fuente | Qué aporta | Cómo se obtiene | Respaldo |
|---|---|---|---|
| **Registro de Dacora** | Censo, inspecciones, ayudas, albergues, reportes | Base de datos solo-agregar con bitácora | La propia base. En la demo sus registros son sintéticos (Ley 1581) y se marcan SIMULADO (`DEMO_DATA=true`) |
| **USGS** (servicio FDSN) | Sismo principal y sismicidad posterior a 300 km | `scripts/fetch_sources.py` → `data/sources/usgs_sismos.json` | URL de la consulta, fecha, licencia (dominio público) y SHA-256. El FDSN del SGC no respondió en sus rutas públicas; se puede sumar con el mismo formato |
| **SECOP II** (datos.gov.co) | Contratos del sismo en Manizales: valor contratado, facturado y pagado registrado | `scripts/fetch_sources.py` → `data/sources/secop_sismo_manizales.json`. Filtro: firmados desde el 10 ago 2026 en Manizales con objeto que mencione `SISM…`, calamidad, damnificados, terremoto o alojamiento/arrendamiento temporal | URL, fecha, licencia CC BY-SA 4.0 y SHA-256. Sin nombres ni documentos de contratistas (Ley 1581) |
| **CDIAC / SIMAC** (UNAL) | Lluvia de las últimas 3 h por estación urbana | En vivo si el administrador activa la fuente CDIAC; si no, copia de `fetch_sources.py` de menos de 6 h | Lectura en `rain_readings` o copia con SHA-256 |
| *Sin convenio* | Cobertura de servicios por barrio · negocios y empleo por comuna · pérdida estimada, recursos y brecha · ICA, turismo y café | — | Se nombra la entidad: Aguas de Manizales, CHEC, Efigas, Obras Públicas · Cámara de Comercio de Manizales por Caldas (y DANE solo a nivel ciudad) · Hacienda, UNGRD y aseguradoras · Hacienda, Cotelco y Comité de Cafeteros |

Si la huella SHA-256 de una copia no coincide con sus registros, el tablero lo marca ("Huella no
coincide"). Para actualizar las copias (con internet): `uv run --project services/api python
scripts/fetch_sources.py`, revisar el diff y confirmar el commit.

### Indicadores

| N.º | Indicador | Claves | Fuente | Definición |
|---|---|---|---|---|
| 1 | Familias damnificadas únicas | `familias_unicas`, `personas_damnificadas`, `rud_inscritos` | Registro de Dacora | Hogares distintos por HMAC del documento; exportables en formato RUD. |
| 2 | Predios evaluados únicos contra pendientes | `predios_evaluados`, `manzanas_dano_reportado`, `manzanas_sin_evaluar`, `visitas_repetidas_evitadas` | Registro de Dacora | Manzanas con daño reportado = manzanas con reportes no descartados de `colapso_estructura` o `dano_estructural`; sin evaluar = las que no tienen ninguna evaluación de habitabilidad. Visitas repetidas = visitas − predios evaluados. |
| 3 | Viviendas por semáforo NSR-10 | `predios_verde`, `predios_amarillo`, `predios_rojo`, `predios_colapso` | Registro de Dacora (EDAN) | Última evaluación de cada predio; **colapsado** = daño `colapso` (se descuenta de rojo). También por barrio. |
| 4 | Índice de recuperación | `indice_recuperacion`, `barrios_bajo_50` | Calculado por Dacora | Promedio con igual peso de los componentes **con fuente**: habitabilidad (verde + ½ amarillo sobre evaluados, ind. 3) y familias en casa (ind. 7). Servicios (6) y economía (9) entran cuando haya convenio. La curva se reconstruye con las fechas del registro (un punto por día con cambios). |
| 5 | Días desde el evento y riesgo activo | `dias_desde_evento`, `sismos_desde_evento`, `replicas_7d`, `replica_max`, `lluvia_3h` | USGS · CDIAC | Días completos desde el sismo principal del USGS (`us6000tjl2`, M 7,4). Sismos M ≥ 2,5 a 300 km. Lluvia: alerta si alcanza el **umbral operativo** `LANDSLIDE_RAIN_THRESHOLD_MM_3H` (25 mm por defecto; no oficial, calibrar con el SAT). |
| 6 | Servicios básicos | `incidentes_servicios`, `barrios_servicios`, *sin fuente: cobertura* | Registro de Dacora | Incidentes abiertos de `servicios_caidos` y barrios afectados. La cobertura por servicio requiere convenio. |
| 7 | Familias por situación y ayudas | `familias_albergue`, `familias_arriendo`, `familias_casa`, `familias_sin_solucion`, `ayudas_entregadas`, `ayudas_repetidas`, `personas_albergue` | Registro de Dacora | Situación por la última ayuda de vivienda del hogar. **Sin solución** = predio rojo sin albergue ni subsidio de arriendo. |
| 8 | Calidad de los reportes | `reports_received`, `incidents_consolidated`, `critical_in_human_queue`, `duplicate_detection_rate`, `fake_detection_rate`, `critical_auto_discarded` | Motor de Dacora y `evaluate_kpis.py` | Tasas: última instantánea de `evaluate_kpis.py`. Sin medición, la tarjeta dice *Sin fuente*. |
| 9 | Negocios reabiertos y empleos recuperados | `contratos_reactivacion`, `valor_reactivacion`, *sin fuente: negocios y empleo* | SECOP II | Contratos del sismo cuyo objeto menciona reactivación económica. Negocios y empleo requieren convenio. |
| 10 | Recursos y trazabilidad | `contratos_sismo`, `contratado`, `facturado`, `pagado`, `pagado_pct`, *sin fuente: pérdida, recursos y brecha* | SECOP II | Sumas de los contratos del sismo. `pagado` es lo **registrado en SECOP** (puede ir rezagado frente al pago real). |

**Necesidades** (solo si su valor es mayor que cero): críticos en cola humana, lluvia sobre el
umbral (con lectura real) y familias sin solución de vivienda (críticas); hogares vulnerables sin
ayuda, manzanas con daño sin evaluar y albergues al 90 % (altas); servicios caídos sin atender y
contratos del sismo sin pagos registrados en SECOP cuando lo pagado es menos del 10 % (medias).

**Ciclo económico (parte B):** cinco etapas con su ventana de días. Solo reciben semáforo las
etapas cuyo avance tiene fuente: 1 El golpe = manzanas con daño reportado ya evaluadas ÷ manzanas
con daño reportado; 3 La plata en movimiento = pagos registrados en SECOP ÷ valor contratado. Las
etapas 2, 4 y 5 quedan **Sin fuente para medir** hasta tener convenio. Semáforo: el avance
esperado crece lineal dentro de la ventana y es 100 % al cerrarla; **verde** (a tiempo) si el
avance ≥ 90 % de lo esperado, **amarillo** (con retraso) si ≥ 60 %, **rojo** (estancada) si es
menor; *aún no empieza* antes de la ventana.

## Sensor de zonas inseguras (`/api/v1/sensors/zones`, patente NC2025/0015763)

Fuente: "SIMULADO · patente NC2025/0015763", con hora de cada evento y fecha de corte del listado.

| Término | Definición |
|---|---|
| Cono de vigilancia | Espacio configurado del sensor: alcance (m) y semiapertura (°) alrededor de su rumbo. Por defecto 12 m y ±30°. |
| Intrusión | Persona u objeto dentro del cono detectado por ultrasonido, infrarrojo o ambos, **sin** tarjeta RFID registrada (o con una desconocida). Es alarma hasta que alguien la marca *Atendida*. |
| Acceso autorizado | Detección dentro del cono con una tarjeta RFID registrada (personal de Bomberos, Defensa Civil, Cruz Roja o Infraestructura). No es alarma. |
| Batería baja | Lectura con batería del equipo < 15 %. |
| Manipulación | Apertura de la carcasa del equipo. Es alarma. |
| Alarmas sin atender | Intrusiones y manipulaciones sin atención registrada. |
| Confirmación por sensor de campo | Señal del puntaje de veracidad (10 pts): intrusión detectada por **ambos** detectores a ≤ 150 m del incidente, en las últimas 3 h, para incidentes de personas atrapadas, colapso de estructura o daño estructural. |

## Etiquetas del puntaje de veracidad

| Etiqueta | Rango |
|---|---|
| Verificado | ≥ 75 |
| Probable | 50–74 |
| Sin verificar | 25–49 |
| Posible falso | < 25 |

## Términos

- **Reporte:** mensaje de una persona o entidad. Solo-agregar.
- **Incidente:** agrupación de reportes que describen el mismo hecho.
- **Fuente independiente:** remitente distinto (por huella HMAC); un remitente que repite no suma.
- **Fecha de corte (`cutoff_at`):** momento hasta el cual una cifra incluye datos.
