# Dacora · Datos clave para el pitch

> Hackathon UNAL Manizales 2026 · Vertical 05 · Datos & Inteligencia Operativa.
> Pitch de selección: **sábado 21 nov, 2:00 p. m.** Corte de estos datos: 21 nov 2026, mañana.

**Cómo usar este documento.** Cada cifra lleva su origen. Diga en voz alta solo lo que el origen
respalda:

| Marca | Significa | Cómo decirlo en el pitch |
|---|---|---|
| **[REAL]** | Dato público verificable (con enlace) | "Según el USGS…", "En SECOP II hay…" |
| **[EVIDENCIA]** | Cifras oficiales del evento recopiladas en la investigación del equipo | "La Alcaldía reportó…" |
| **[MEDIDO]** | Resultado de Dacora medido sobre el escenario sintético con verdad conocida | "En nuestro escenario de prueba de 254 reportes…" |
| **[SIMULADO]** | Modelo o escenario sintético | "En la simulación…", nunca como dato del evento |

---

## 1. La frase

**Dacora convierte reportes dispersos y contradictorios del sismo en un solo tablero confiable
para el PMU y el COE: verifica, deduplica y prioriza en segundos, funciona sin internet y protege
los datos personales desde el diseño.**

Una línea para cerrar: *"No necesitamos más datos; necesitamos una sola verdad, con fuente y hora."*

---

## 2. El problema, con números

### El evento · [REAL]

| Dato | Valor | Fuente |
|---|---|---|
| Sismo principal | **M 7,4**, 10 ago 2026, **7:34 a. m.** (hora de Colombia) | USGS `us6000tjl2` |
| Epicentro | 4 km al SSO de **San José del Palmar** (Chocó) | USGS |
| Profundidad | **116 km** según el USGS (los reportes nacionales hablan de ~103 km) | USGS · evitar dar una sola cifra: decir "a más de 100 km de profundidad" |
| Sismicidad posterior | **76 sismos M ≥ 2,5** a 300 km de Manizales desde el evento | USGS, consulta del 21 nov |
| Días desde el sismo | **103** (al 21 nov) | Calculado |

Enlace para mostrar: <https://earthquake.usgs.gov/earthquakes/eventpage/us6000tjl2>

### Lo que falló · [EVIDENCIA]

| Hallazgo | Cifra | Qué resuelve Dacora |
|---|---|---|
| Cifras que cambian | Viviendas con afectación total: **1.449 → 2.700 → 1.512** (13, 14 y 15 ago) | Cada cifra con fuente, versión y hora de corte |
| Entidades que no cuadran | Gobernación: **142** viviendas afectadas; Alcaldía el mismo día: **~2.000** solicitudes | Una sola fuente de verdad, diccionario de indicadores |
| Visitas repetidas | Hasta **3 visitas** al mismo inmueble; se contaban visitas, no predios | Identificador único de predio; visitas repetidas unidas |
| Sin satélite | Copernicus (EMSR916) no definió área en Manizales pese a **361 reportes** de daño | Verificación con sensores locales y corroboración entre fuentes |
| Línea 123 saturada | **30–70 %** de llamadas improcedentes o falsas (patrón nacional) | Trust score y detección de falsos |
| Lección de 1999 | A los 4 días se estimaban **35.000** viviendas; el censo real fue **79.500**. **731** desaparecidos por confusión | Censo único sin duplicados |

### El dinero tampoco se ve · [REAL] SECOP II

Consulta del 21 nov a SECOP II (datos.gov.co, licencia CC BY-SA 4.0): contratos firmados en
Manizales desde el 10 ago cuyo objeto menciona el sismo, la calamidad, los damnificados o el
alojamiento temporal.

| Dato | Valor |
|---|---|
| Contratos ligados al sismo | **97** |
| Valor contratado | **$25.754 millones** ($25.754.151.714) |
| Valor facturado | **$192 millones** |
| Pagos registrados en SECOP | **$163 millones = 0,6 %** de lo contratado |
| Contratos sin ningún pago registrado | **84 de 97** |
| Contratado en los primeros 15 días | **$5.439 millones** |
| Contratado en subsidios de arriendo y alojamiento | **$6.964 millones** |
| Contratos de reactivación económica | **2**, por **$400 millones** |
| Mayor contrato | **$5.500 millones**, 11 sep: apoyo a la evaluación, intervención y demolición de edificaciones |
| Principal contratante | Municipio de Manizales: **$17.010 millones** |

**Cómo decirlo:** *"A 103 días, SECOP II muestra $25.754 millones contratados por el sismo y solo
0,6 % con pago registrado. Puede ser rezago de registro, pero nadie lo está viendo. Dacora lo
pone en el tablero."* No afirmar que el dinero no se pagó: SECOP puede ir rezagado.

---

## 3. La solución en 30 segundos

1. **Captura** por todos los canales: app ciudadana que funciona **sin internet** (guarda y envía
   al volver la señal), SMS en formato compacto, línea 123, entidades, WhatsApp.
2. **Motor** en menos de un segundo: borra datos personales → clasifica y prioriza → une
   duplicados → calcula un **puntaje de veracidad 0–100 explicable**.
3. **Tablero PMU**: mapa por manzana, matriz de triaje, despacho a la agencia correcta, alertas que
   **solo aprueba el COE**.
4. **Recuperación** con los **formatos oficiales**: revisión a predio de la Alcaldía
   (GUE-RPD-FR-02), censo con campos del **RUD**, actas de entrega, albergues y derivaciones a
   entidades, todo enlazado.
5. **La IA sugiere, decide un humano**: ningún reporte con riesgo vital se descarta solo.

---

## 4. Lo que medimos · [MEDIDO]

Escenario sintético del 10 ago con **254 reportes** y verdad conocida (55 % únicos, 30 %
duplicados, 15 % falsos o rumores). Meta oficial de la vertical: **> 90 %** de detección de
duplicados y falsos.

| Indicador | Meta | Resultado |
|---|---|---|
| Duplicados detectados | > 90 % | **100 %** |
| Falsos o rumores detectados | > 90 % | **94,7 %** ⚠️ volver a medir antes del pitch (ver §10) |
| Legítimos marcados como falsos | lo más bajo posible | **0 %** |
| Críticos identificados | ≥ 98 % | **100 %** |
| Críticos descartados por la IA | 0 | **0** |
| Procesamiento por reporte (p95) | < 1 s | **< 100 ms** (74 ms en la demo en vivo) |
| Hecho en el mapa (p90) | minutos, no días | **< 1 minuto** simulado (en 2026 tomó días consolidar) |

**Frase:** *"De 254 reportes caóticos, Dacora detectó el 100 % de los duplicados y el 94,7 % de
los falsos, sin descartar un solo reporte con personas en riesgo."*

---

## 5. Cuánto vale la colaboración institucional · [SIMULADO]

Monte Carlo de **2.000 corridas por escenario** sobre una misma verdad simulada: solo cambia cómo
le llegan los datos al sistema. Detalle y supuestos: [escenarios_recuperacion.md](escenarios_recuperacion.md).

| Al día 102 | Mejor caso: con convenios | Peor caso: sin convenios |
|---|---|---|
| **Confianza global del sistema** | **95,7 %** (IC 90 %: 84,4–100) | **22,8 %** (IC 90 %: 8,2–37,6) |
| Cifras dentro de ±10 % de la realidad | 94,8 % | 4,5 % |
| Duplicados detectados | 96,7 % | 54,9 % |
| Error del índice de recuperación | 1,1 puntos | 11,6 puntos |
| Corridas con confianza alta (≥ 75 %) | 98,2 % | 0 % |

| Día | Mejor caso | Peor caso |
|---|---|---|
| 1 | 76,7 % | 15,3 % |
| 7 | 87,5 % | 19,1 % |
| 30 | 94,9 % | 22,2 % |
| 90 | 95,4 % | 22,9 % |

**Frase:** *"El mismo software da 96 % de confianza con convenios y 23 % sin ellos. La diferencia,
73 puntos, es lo que pedimos a las instituciones."* Siempre decir que es una simulación.

---

## 6. Qué mostrar en la demo (3–4 min)

| # | Momento | Qué se ve | Dato para decir |
|---|---|---|---|
| 1 | Contexto (20 s) | Inicio público | 1.449 → 2.700 → 1.512; Manizales sin satélite |
| 2 | Llega el sismo | `replay_scenario.py`: el mapa se llena | 254 reportes, < 100 ms cada uno |
| 3 | Celular en modo avión | Reporte se guarda y aparece al volver la red | Funciona sin internet, sin duplicar |
| 4 | SMS de personas atrapadas | Entra como **Crítico** y se une a un incidente | Duplicado detectado, suma corroboración |
| 5 | Cadena de WhatsApp falsa | **Posible falso** con el desglose del puntaje | Explicable, no una caja negra |
| 6 | Despacho | Bomberos en camino con traza | Sin despachos dobles |
| 7 | Panel de KPI | Duplicados 100 %, falsos 94,7 %, 0 críticos descartados | Meta > 90 % cumplida |
| 8 | Recuperación | Formato GUE-RPD-FR-02 → semáforo → censo RUD → albergue | Mismos formatos que ya usa la Alcaldía |
| 9 | Tablero de recuperación | Necesidades de hoy, SECOP real, respaldo de las cifras | 0,6 % pagado; cada cifra con fuente |
| 10 | Escenarios | Mejor frente a peor caso | 96 % frente a 23 % de confianza |

Usuario de la demo: `coe` / contraseña de `.env.example`. Guion completo: [guion_demo.md](guion_demo.md).
Casos de recuperación: [guia_recuperacion.md](guia_recuperacion.md).

---

## 7. Conocimiento UNAL y patentes (componente 3)

| Capacidad | Estado en el prototipo | Cómo decirlo |
|---|---|---|
| **CDIAC / SIMAC** (UNAL Manizales) | ✅ Conector de lluvia **real** de 36 estaciones urbanas; en vivo cuando hay red (el 21 nov no respondió desde la red del evento) | "Conectado a las estaciones de la UNAL" · probarlo antes del pitch |
| Patente **NC2025/0015763** (zonas inseguras) | ✅ Sensores, eventos de intrusión y confirmación de incidentes | "Implementamos la patente" |
| Patente **15111163** (RFID de vehículos) | ✅ Trazas de recursos despachados | "Trazabilidad de recursos" |
| Efectos en cascada (lluvia + pendiente) | ✅ Capa por manzana | "Predicción de deslizamientos" |
| **RAMAN** (acelerógrafos) | 🟡 Punto de integración listo; hoy en modo neutro | "Listo para conectar" (no decir "conectado") |
| SISMAN-LISA, IDE-UNAL, RAG local | ❌ Plan 30–90 días | "Siguiente paso" |

---

## 8. Habeas Data y viabilidad (componente 5)

- **Nada personal en la base:** cédulas y teléfonos solo como huella cifrada (HMAC con sal);
  nombres, fechas de nacimiento y firmas **quedan en el papel**. Prueba automática lo verifica.
- **Redacción en el borde:** el celular borra teléfonos, cédulas, correos y nombres antes de
  enviar; la API lo vuelve a hacer.
- **Datos sensibles separados** (niñez, discapacidad, gestación) y visibles solo para PMU/COE.
- **Público solo agregado** con k ≥ 5 (Ley 1712).
- **Offline-first:** corre en un portátil sin internet; las fuentes públicas se guardan como copia
  fechada con huella SHA-256.
- **Software abierto**, dos servicios (FastAPI + Next.js) y PostgreSQL/PostGIS: `docker compose up`.
- **Formatos oficiales:** revisión a predio GUE-RPD-FR-02 v4, campos del RUD (UNGRD), actas de
  entrega, 6 funciones de respuesta de la EMRE Manizales 2024.

---

## 9. Plan 30–90 días (componente 4)

| Plazo | Qué | Con quién |
|---|---|---|
| 30 días | Piloto en la sala de crisis con la UGR; conectar acelerógrafos RAMAN; servicio sísmico del SGC | UGR, Corpocaldas, SGC |
| 30 días | Reporte de situación automático con la cadencia EMRE (6 h / 12 h / 24 h) | COE |
| 60 días | Convenios de datos: cobertura de agua, energía y gas por barrio | Aguas de Manizales, CHEC, Efigas, Obras Públicas |
| 60 días | Negocios y empleo por comuna; presupuesto y pagos | Cámara de Comercio, Hacienda, UNGRD |
| 90 días | Exportación directa al RUD; portal público "Reconstruir Mejor"; asistente con protocolos EMRE (LLM local) | UNGRD, Alcaldía, IDE-UNAL |

**Modelo institucional:** dueño, las gobernaciones (convenio regional); operador técnico, la UNAL
Manizales; software abierto.

---

## 10. Antes de subir al escenario

- [ ] **Volver a medir los KPI** (la demo en vivo no tiene publicada la tasa de falsos):
  `replay_scenario.py --reset` → `evaluate_kpis.py`. **El reinicio borra los casos de
  recuperación:** después correr `seed_recovery_example.py`.
- [ ] **Video o GIF de respaldo** de la demo (criterio de terminado; protege 25 puntos).
- [ ] Actualizar la consulta de SECOP y USGS (con internet): `fetch_sources.py`.
- [ ] Probar el modo avión en el celular de la demo.
- [ ] Revisar los **34 incidentes críticos sin despacho** que muestra la demo: despachar algunos
  en el ensayo o tener lista la explicación.

---

## 11. Preguntas probables del jurado

| Pregunta | Respuesta corta |
|---|---|
| ¿De dónde salen los datos? | El sismo y los contratos son **reales** (USGS y SECOP II, con enlace). Los reportes ciudadanos y las familias son **sintéticos** por Ley 1581. Cada cifra muestra su fuente. |
| ¿Qué pasa sin internet? | Corre en un portátil; la app guarda los reportes y los envía al volver la red; SMS como respaldo; Plan C con nodos LoRa (el canal existe, la integración física es del plan 30–90 días). |
| ¿La IA decide? | No. Sugiere y explica su puntaje. Un humano confirma o descarta, y queda en la bitácora. Ningún reporte con riesgo vital se descarta solo. |
| ¿Cómo evitan duplicar familias o ayudas? | Huella cifrada del documento: un hogar es un hogar; la misma ayuda en el mismo periodo se bloquea salvo justificación. |
| ¿Por qué confiar en el 94,7 %? | Se mide contra un escenario con verdad conocida; el script es reproducible (`evaluate_kpis.py`). |
| ¿Qué necesitan para que funcione de verdad? | Convenios de datos. La simulación muestra que con ellos la confianza sube de 23 % a 96 %. |
| ¿Por qué el 0,6 % pagado? | Es lo que SECOP II tiene registrado; puede ser rezago. Justamente por eso hace falta verlo en un tablero. |
| ¿En qué se diferencian de soluciones existentes? | Frente a la patente US 12,536,153 (validación de información crowdsourced): offline-first, agregación por manzana, sensores locales, español colombiano y Habeas Data desde el diseño. |

---

## 12. El prototipo en cifras · al 21 nov

| Dato | Valor |
|---|---|
| Rutas de la API REST | **63** |
| Pruebas | API **231** pasan (4 desactualizadas por el cambio a acceso anónimo); web **31** |
| Historial | **363 commits** atómicos |
| Fuentes reales conectadas | USGS, SECOP II, CDIAC/SIMAC |
| Formatos oficiales digitalizados | Revisión a predio GUE-RPD-FR-02 v4, RUD, acta de entrega |
| Casos de capacitación | 6, con [guía](guia_recuperacion.md) |
| Evaluación propia frente a la rúbrica | **~79 / 100** (estimado del equipo, no del jurado) |
