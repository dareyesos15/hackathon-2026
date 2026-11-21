# Feature Specification: Despacho, alertas y predicción de efectos en cascada

**Feature Branch**: `002-dispatch-alerts-prediction`

**Created**: 2026-11-21

**Status**: Draft

**Input**: User description: "Vamos a iniciar la implementación del punto 5 de la imagen
docs/arquitectura_actual" — bloque 5 del diagrama de arquitectura actual ("Despacho, alertas y
predicción"): despacho a agencias según las 6 funciones de respuesta de la EMRE, alertas
multicanal con aprobación exclusiva del COE y predicción de efectos en cascada. Corresponde a
CLAUDE.md §8, puntos 9 y 10 (P1) y 14 (P2), y a la sección 7.7.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Despachar un incidente a la agencia correcta sin duplicar esfuerzos (Priority: P1)

Un operador del PMU abre un incidente verificado o en revisión (por ejemplo, personas atrapadas en
Milán). El sistema le sugiere la agencia responsable según la función de respuesta de la EMRE que
corresponde a la categoría del incidente (Salvamento y seguridad → Cuerpo Oficial de Bomberos) y le
muestra los recursos disponibles de esa agencia (cuadrillas y vehículos), ordenados por cercanía al
incidente. El operador elige un recurso y confirma el despacho. Desde ese momento el incidente
aparece como "despachado" en el tablero, el recurso pasa a "en camino" y su recorrido se ve en el
mapa con los puntos de paso registrados (salida de la base, puntos de control, llegada al sitio).
Si alguien intenta despachar de nuevo el mismo incidente mientras ya tiene un despacho activo, el
sistema lo advierte y solo permite un refuerzo con justificación explícita.

**Why this priority**: despachar es la primera acción que convierte la información consolidada en
respuesta; en el sismo del 10 ago 2026 hubo hasta 3 visitas al mismo inmueble. Evitar el doble
despacho y mostrar la trazabilidad del recurso es lo que el jurado verá en el paso 6 del guion de
la demo ("Se despacha Bomberos al incidente; se ve la traza del recurso").

**Independent Test**: con el escenario sintético cargado, se abre un incidente crítico, se
despacha un recurso de la agencia sugerida y se verifica: sugerencia de agencia correcta según la
tabla EMRE, cambio de estado del incidente y del recurso, traza visible en el mapa, registro en la
bitácora y bloqueo del segundo despacho no justificado. No requiere alertas ni la capa de cascada.

**Acceptance Scenarios**:

1. **Given** un incidente de "personas atrapadas" en Milán sin despacho, **When** el operador lo
   abre, **Then** el sistema sugiere la función "1. Salvamento y seguridad" y la agencia "Cuerpo
   Oficial de Bomberos", y lista sus recursos disponibles con la distancia aproximada al incidente.
2. **Given** la sugerencia anterior, **When** el operador elige la cuadrilla más cercana y
   confirma, **Then** el incidente queda con agencia asignada y estado de despacho "en camino", el
   recurso deja de aparecer como disponible y la acción queda en la bitácora con rol y fecha/hora.
3. **Given** un incidente con un despacho activo, **When** otro operador intenta despacharlo de
   nuevo, **Then** el sistema muestra el despacho existente (agencia, recurso, estado, hora) y solo
   permite continuar como "refuerzo" escribiendo una justificación, que queda en la bitácora.
4. **Given** un recurso despachado, **When** se registran sus puntos de paso (salida, punto de
   control, llegada), **Then** el mapa del PMU muestra su recorrido y su última posición conocida, y
   el estado del despacho avanza a "en sitio" al registrarse la llegada.
5. **Given** un despacho "en sitio", **When** la agencia (rol `agencia`) marca la atención como
   finalizada, **Then** el recurso vuelve a "disponible" y el operador del PMU ve el incidente como
   listo para cerrar; el cierre del incidente ("atendido") lo decide el operador.
6. **Given** un incidente de categoría "heridos" sin recursos disponibles de la agencia sugerida,
   **When** el operador lo abre, **Then** el sistema lo indica y ofrece recursos de las otras
   agencias de la misma función de respuesta.

---

### User Story 2 - Alertas oficiales con aprobación del COE (Priority: P2)

Un operador del PMU redacta una alerta (por ejemplo, evacuación preventiva de un sector de ladera
en Chipre) eligiendo el tipo, el área afectada (uno o varios barrios, o un área dibujada en el
mapa), el mensaje y los canales (aviso en el tablero del PMU, aviso en el mapa público y SMS a
cuadrillas en campo). La alerta queda en **borrador**. Solo un usuario con rol `coe` puede
aprobarla o rechazarla con un motivo; al aprobarla se emite: aparece en el tablero del PMU, en el
mapa público y en el registro de SMS enviados (simulado). Un rumor clásico (predicción de réplicas
con hora exacta) dispara una advertencia antes de guardar el borrador.

**Why this priority**: la EMRE Manizales 2024 (tarea 5.5) establece que solo el COE emite alertas
oficiales; mostrar ese control humano es la diferencia frente a sistemas que difunden rumores. Es
independiente del despacho y suma en el componente de viabilidad.

**Independent Test**: un operador crea un borrador, intenta enviarlo (rechazado por rol), un
usuario `coe` lo aprueba y se verifica que aparece en el tablero, en el mapa público y en el
registro de SMS, todo en la bitácora. No requiere despachos ni la capa de cascada.

**Acceptance Scenarios**:

1. **Given** un operador del PMU, **When** crea una alerta de evacuación para el barrio Chipre con
   mensaje de 140 caracteres y canales "tablero", "mapa público" y "SMS a cuadrillas", **Then** la
   alerta queda en estado "borrador", visible para el COE en su bandeja de aprobación.
2. **Given** una alerta en borrador, **When** un usuario que no tiene rol `coe` intenta aprobarla,
   **Then** el sistema lo rechaza con el mensaje "Solo el COE puede aprobar alertas oficiales" y la
   alerta sigue en borrador.
3. **Given** una alerta en borrador, **When** un usuario `coe` la aprueba, **Then** su estado pasa
   a "emitida", aparece como aviso destacado en el tablero del PMU y en el mapa público sobre el
   área afectada, y el registro de SMS muestra el envío simulado con el número de destinatarios,
   nunca sus números.
4. **Given** una alerta en borrador, **When** un usuario `coe` la rechaza indicando el motivo,
   **Then** el estado pasa a "rechazada", el autor ve el motivo y la alerta no se difunde.
5. **Given** un borrador con el texto "réplica de 9 a las 3 p. m., reenvía", **When** el operador
   lo guarda, **Then** el sistema advierte que el mensaje contiene señales de desinformación
   (predicción de sismos, cadena) y pide confirmar o corregir antes de enviarlo a aprobación.
6. **Given** una alerta emitida, **When** el COE la anula, **Then** deja de mostrarse como vigente
   en el tablero y en el mapa público, y queda en el historial con quién y cuándo la anuló.
7. **Given** un incidente abierto en el tablero, **When** el operador elige "crear alerta desde este
   incidente", **Then** el borrador se precarga con el área y el tipo sugerido según su categoría.

---

### User Story 3 - Predicción de efectos en cascada por manzana (Priority: P3)

El operador del PMU activa la capa "Efectos en cascada" en el mapa. Para cada manzana el sistema
estima un nivel de riesgo de deslizamiento o colapso secundario (Bajo, Medio, Alto, Muy alto)
combinando la pendiente de la ladera, la lluvia acumulada (feed SIMULADO tipo alarma de lluvia
por entropía de ecos), la intensidad sísmica estimada y los reportes recientes de daño o
deslizamiento cercanos. Al tocar una manzana se ve por qué tiene ese nivel (factores y su peso).
Desde la lista de manzanas en riesgo Alto o Muy alto, el operador puede crear un borrador de alerta
preventiva (US2). Al cambiar la lluvia simulada, la capa se recalcula.

**Why this priority**: Manizales tiene laderas de más de 60° y los movimientos en masa son su
amenaza más recurrente; anticipar el siguiente daño es el valor diferencial del bloque 5. Es P2 en
CLAUDE.md §8 y depende de capas simuladas, por eso va de última.

**Independent Test**: con el escenario cargado, se activa la capa, se sube la lluvia simulada y se
verifica que las manzanas de ladera con reportes de daño cercanos suben de nivel, que cada nivel
muestra su explicación y que todo aparece etiquetado SIMULADO. No requiere despachos.

**Acceptance Scenarios**:

1. **Given** el escenario cargado y lluvia simulada en cero, **When** el operador activa la capa,
   **Then** cada manzana con datos muestra un nivel de riesgo de cascada, la capa lleva la etiqueta
   SIMULADO y la leyenda explica los cuatro niveles.
2. **Given** una manzana de ladera con dos reportes de deslizamiento cercanos, **When** el operador
   la toca, **Then** ve el nivel y el desglose de factores (pendiente, lluvia, intensidad sísmica,
   reportes cercanos) con su contribución, y la fecha/hora de corte del cálculo.
3. **Given** la capa activa, **When** la lluvia simulada sube de 0 a 40 mm en 3 horas, **Then** la
   capa se recalcula y las manzanas de ladera suben de nivel sin recargar la página.
4. **Given** una manzana en riesgo "Muy alto", **When** el operador elige "crear alerta
   preventiva", **Then** se abre un borrador de alerta (US2) con el área y el tipo "deslizamiento"
   precargados; la alerta sigue requiriendo aprobación del COE.
5. **Given** que no hay lecturas de intensidad sísmica, **When** se calcula la capa, **Then** el
   factor sísmico usa un valor neutro y el desglose dice "sin dato de sensor".

---

### Edge Cases

- **Incidente descartado o fusionado con un despacho activo**: el despacho no se cancela solo; el
  operador recibe un aviso para decidir si lo cancela o lo reasigna al incidente resultante.
- **Recurso que deja de estar disponible** (averiado, reasignado) mientras está despachado: la
  agencia o el operador lo marcan "fuera de servicio" con motivo; el incidente vuelve a mostrarse
  como "sin despacho activo" y sube en la lista si es de riesgo vital.
- **Doble clic o reenvío del mismo despacho**: confirmar dos veces la misma acción produce un solo
  despacho.
- **Incidentes de riesgo vital sin despacho** por más de 15 minutos: se destacan en el tablero y se
  cuentan en el panel de KPI.
- **Puntos de paso fuera de orden o repetidos**: se guardan todos, se ordenan por hora y la
  posición actual es el último por hora, no el último recibido.
- **Conflicto en la aprobación**: si el autor edita el borrador mientras el COE lo revisa, el COE
  aprueba solo la versión que vio; si cambió, el sistema le pide revisar de nuevo.
- **Alerta con datos personales en el mensaje** (teléfono, cédula, nombre): se redactan antes de
  guardar, igual que los reportes.
- **Mensaje de alerta demasiado largo para SMS** (> 160 caracteres): el sistema lo indica y no
  permite elegir el canal SMS hasta acortarlo.
- **Alerta sin área** o con área fuera del casco urbano: no se puede enviar a aprobación.
- **Sin conexión en vivo con el tablero**: despachos, trazas y alertas emitidas aparecen igual en
  el siguiente ciclo de actualización (modo de respaldo ya existente).
- **Capa de cascada sin datos de lluvia**: usa lluvia cero y lo indica en el desglose.

## Requirements *(mandatory)*

### Functional Requirements

**Despacho y trazabilidad de recursos (US1)**

- **FR-001**: El sistema MUST sugerir, para cada incidente, la función de respuesta de la EMRE y la
  agencia responsable según su categoría, usando esta tabla:
  personas atrapadas, incendio, fuga de gas, colapso de estructura → 1. Salvamento y seguridad
  (Cuerpo Oficial de Bomberos, Defensa Civil, Policía); heridos → 2. Salud y saneamiento (Cruz
  Roja, Secretaría de Salud); necesidad de albergue, necesidad de ayuda, persona desaparecida →
  3. Asistencia social (Secretaría de Desarrollo Social, Cruz Roja); daño estructural, vía
  bloqueada, servicios caídos, deslizamiento → 4. Infraestructura, servicios y ambiente (Secretaría
  de Infraestructura, Aguas de Manizales, CHEC, Efigas, Corpocaldas). La sugerencia es editable:
  el operador puede elegir otra agencia.
- **FR-002**: El sistema MUST mantener un catálogo de recursos (cuadrillas y vehículos) por
  agencia, con tipo, base y estado: disponible, en camino, en sitio, fuera de servicio.
- **FR-003**: Al abrir un incidente, el sistema MUST listar los recursos disponibles de la agencia
  sugerida ordenados por distancia aproximada al incidente, y ofrecer los de otras agencias de la
  misma función si no hay disponibles.
- **FR-004**: Solo los roles operador del PMU y COE MUST poder crear un despacho, asignando uno o
  más recursos disponibles a un incidente.
- **FR-005**: El sistema MUST impedir asignar un recurso que no esté disponible.
- **FR-006**: Si el incidente ya tiene un despacho activo, el sistema MUST mostrarlo y solo
  permitir un nuevo despacho marcado como "refuerzo" con justificación escrita obligatoria.
- **FR-007**: Crear un despacho MUST ser idempotente: repetir la misma confirmación no crea un
  segundo despacho.
- **FR-008**: El sistema MUST registrar puntos de paso de cada recurso despachado (salida de base,
  punto de control, llegada al sitio, regreso) con hora y ubicación, provenientes de un lector de
  control vehicular tipo RFID (SIMULADO) o de registro manual.
- **FR-009**: El mapa del PMU MUST mostrar los recursos despachados con su recorrido y su última
  posición conocida, y el detalle del incidente MUST mostrar sus despachos con estado y
  hora estimada de llegada (SIMULADA).
- **FR-010**: El rol `agencia` MUST ver solo los despachos de su agencia y poder actualizar su
  estado (en camino → en sitio → finalizado, o fuera de servicio con motivo).
- **FR-011**: Al finalizar un despacho, el recurso MUST volver a "disponible"; el cambio del
  incidente a "atendido" MUST seguir siendo una decisión del operador del PMU.
- **FR-012**: Toda acción de despacho (crear, refuerzo, cambio de estado, cancelación, punto de
  paso manual) MUST quedar en la bitácora auditable con rol y fecha/hora; los despachos no se
  borran.
- **FR-013**: El tablero MUST destacar los incidentes de riesgo vital sin despacho activo y el
  panel de KPI MUST mostrar, con fuente y fecha de corte: incidentes críticos sin despacho,
  tiempo mediano desde que un incidente crítico aparece hasta su despacho, y despachos dobles
  evitados.
- **FR-014**: Un escenario de demostración MUST poder hacer avanzar automáticamente los puntos de
  paso de los recursos despachados para que su recorrido se vea en vivo.

**Alertas oficiales (US2)**

- **FR-015**: Los roles operador del PMU y COE MUST poder crear alertas en estado "borrador" con:
  tipo (evacuación, deslizamiento, réplica/información sísmica, servicios públicos, información
  general), área (uno o más barrios o un polígono dibujado en el mapa), mensaje y canales (tablero
  del PMU, mapa público, SMS a cuadrillas en campo).
- **FR-016**: Solo el rol `coe` MUST poder aprobar, rechazar (con motivo obligatorio) o anular
  alertas; cualquier otro rol recibe un rechazo explícito.
- **FR-017**: Una alerta MUST pasar por los estados borrador → emitida | rechazada, y emitida →
  anulada; una alerta emitida no se puede editar, solo anular y crear una nueva.
- **FR-018**: El COE MUST aprobar una versión concreta del borrador; si el borrador cambió desde
  que el COE lo abrió, la aprobación MUST rechazarse pidiendo revisar la versión nueva.
- **FR-019**: Al emitirse, la alerta MUST aparecer como aviso destacado en el tablero del PMU y,
  si el canal está elegido, en el mapa público sobre su área, en menos de 5 segundos.
- **FR-020**: El canal SMS MUST quedar registrado como envío SIMULADO con número de destinatarios y
  hora, sin guardar números de teléfono; el mensaje para SMS MUST tener máximo 160 caracteres.
- **FR-021**: El mensaje de la alerta MUST pasar por la misma redacción de datos personales que los
  reportes antes de guardarse.
- **FR-022**: Al guardar un borrador, el sistema MUST advertir si el mensaje contiene señales de
  desinformación (predicción de sismos o réplicas con magnitud u hora, "reenvía", "cadena") y pedir
  confirmación explícita para continuar.
- **FR-023**: El operador MUST poder crear un borrador desde un incidente o desde una manzana de la
  capa de cascada, con área y tipo precargados según la categoría.
- **FR-024**: Toda acción sobre alertas (crear, editar, aprobar, rechazar, anular) MUST quedar en la
  bitácora con rol y fecha/hora.

**Efectos en cascada (US3)**

- **FR-025**: El sistema MUST calcular para cada manzana un nivel de riesgo de efecto en cascada
  (Bajo, Medio, Alto, Muy alto) a partir de: pendiente del terreno, lluvia acumulada en las últimas
  horas, intensidad sísmica estimada y reportes recientes de daño estructural, colapso o
  deslizamiento a menos de 300 m.
- **FR-026**: Cada nivel MUST mostrar su desglose de factores con su contribución, la versión del
  modelo y la fecha/hora de corte.
- **FR-027**: La capa MUST recalcularse cuando cambien la lluvia simulada o los reportes, y
  reflejarse en el mapa sin recargar la página.
- **FR-028**: El sistema MUST aceptar lecturas de lluvia de un feed SIMULADO (tipo alarma de lluvia
  por entropía de ecos) y, en ausencia de lecturas, usar lluvia cero indicándolo en el desglose.
- **FR-029**: Sin datos de intensidad sísmica, el factor sísmico MUST usar un valor neutro e
  indicar "sin dato de sensor".
- **FR-030**: La capa, sus datos y su leyenda MUST llevar la etiqueta visible SIMULADO.
- **FR-031**: La predicción MUST ser solo una sugerencia: nunca emite alertas ni despacha recursos
  por sí sola.

**Transversales**

- **FR-032**: Todas las fuentes externas de esta funcionalidad (lector RFID de vehículos, cálculo
  de rutas y tiempos de llegada, envío de SMS, feed de lluvia) MUST funcionar con una
  implementación SIMULADA por defecto y sin conexión a internet, reemplazable por la integración
  real sin cambiar el tablero.
- **FR-033**: Ninguna pantalla pública MUST mostrar recursos, despachos ni incidentes individuales;
  el público solo ve alertas emitidas y la capa agregada ya existente.

### Key Entities *(include if feature involves data)*

- **Agencia**: organismo de respuesta (Bomberos, Cruz Roja, CHEC, …) con la función de respuesta
  EMRE a la que pertenece.
- **Recurso**: cuadrilla o vehículo de una agencia, con tipo, base, estado y última posición
  conocida; identificado de forma estable para la trazabilidad.
- **Despacho**: asignación de un recurso a un incidente; guarda agencia, si es refuerzo y su
  justificación, estado, hora estimada de llegada y quién lo creó. Un incidente puede tener varios
  despachos; un recurso solo uno activo.
- **Punto de paso**: registro con hora y ubicación del paso de un recurso (salida, control,
  llegada, regreso) y su origen (lector RFID simulado o manual).
- **Alerta**: aviso oficial con tipo, área, mensaje, canales, estado, versión, autor, aprobador y
  fechas de emisión o anulación.
- **Envío de alerta**: registro por canal de la difusión de una alerta emitida (hora, número de
  destinatarios, SIMULADO), sin datos de contacto.
- **Lectura de lluvia**: valor de lluvia acumulada con hora y estación (SIMULADO).
- **Estimación de cascada**: nivel de riesgo por manzana con desglose de factores, versión del
  modelo y fecha de corte.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un operador despacha un incidente crítico a la agencia sugerida en menos de 30
  segundos desde que lo abre, con un máximo de 3 acciones.
- **SC-002**: En la reproducción completa del escenario, la agencia sugerida coincide con la tabla
  EMRE en el 100 % de los incidentes con categoría asignable.
- **SC-003**: 0 incidentes con dos despachos activos sin justificación de refuerzo al final de la
  reproducción del escenario.
- **SC-004**: El recorrido de un recurso despachado es visible en el mapa del PMU en menos de 5
  segundos tras cada punto de paso.
- **SC-005**: El 100 % de las alertas emitidas tienen aprobación de un usuario COE registrada en la
  bitácora; 0 alertas emitidas por otros roles.
- **SC-006**: Una alerta aprobada aparece en el tablero del PMU y en el mapa público en menos de 5
  segundos.
- **SC-007**: 0 teléfonos, cédulas o correos almacenados en mensajes de alerta, justificaciones o
  notas de despacho (verificado con prueba automática).
- **SC-008**: La capa de cascada se recalcula y se ve actualizada en menos de 10 segundos tras un
  cambio de lluvia simulada, y el 100 % de las manzanas con nivel muestran su desglose.
- **SC-009**: El flujo completo de la demo (despachar → ver la traza → redactar alerta → aprobación
  COE → aviso en el mapa público) se completa en menos de 2 minutos por un integrante siguiendo el
  guion.

## Assumptions

- **Dependencia**: se construye sobre el núcleo P0 (`specs/001-p0-situational-core`): incidentes,
  bitácora, tablero del PMU con actualización en vivo y modo de respaldo, panel de KPI, mapa público
  y redacción de datos personales. El P0 está terminado y validado (principio VII), salvo el video
  de respaldo de la demo.
- **Alcance**: cubre el bloque 5 del diagrama `docs/arquitectura_actual.png` y la "Trazabilidad de
  recursos" del bloque 4, que el punto 9 de CLAUDE.md §8 asocia al despacho. Quedan fuera: sensores
  acelerográficos (P1 #8), nivel de emergencia sugerido y reporte de situación (P1 #12),
  recuperación (bloque 6), RAG e ingesta LoRa.
- **Roles**: se activan en la interfaz los roles `coe` y `agencia`, como los roles ya existentes
  (credenciales fijas por rol, sin registro de usuarios). Para la demo, una sola sesión `agencia`
  puede actuar por cualquier agencia eligiéndola al entrar.
- **Recursos**: catálogo sintético SIMULADO de unos 20 a 30 recursos repartidos entre las agencias
  de la tabla EMRE, con bases en ubicaciones aproximadas de Manizales.
- **Trazas**: el lector RFID de vehículos (patente 15111163) y los puntos de paso se simulan; las
  posiciones avanzan en línea recta hacia el incidente. El cálculo de rutas con probabilidad de
  bloqueo (ERIS-UNAL) queda como punto de integración; el tiempo estimado de llegada usa distancia
  en línea recta y una velocidad fija, etiquetado SIMULADO.
- **SMS**: no se envían SMS reales; se registra el envío simulado con número de destinatarios. El
  número de destinatarios es el de recursos en campo dentro del área, no de ciudadanos.
- **Pendiente**: se asigna por manzana desde la geografía sintética (SIMULADO) si no hay modelo de
  elevación disponible sin conexión.
- **Lluvia**: un feed sintético controlable por el operador o por la reproducción del escenario
  (patente NC2022/0005821, alarma de lluvia por entropía de ecos, como origen declarado).
- **Intensidad sísmica**: mientras no existan las lecturas simuladas de acelerógrafos (P1 #8), el
  factor sísmico es neutro; cuando existan, la capa las usa sin cambiar su presentación.
- **Umbrales**: la ventana de "riesgo vital sin despacho" (15 min), el radio de reportes cercanos
  (300 m) y los cortes de los niveles de cascada son configurables y se calibran con el escenario.
- **Rama**: la especificación se crea en la rama de trabajo actual; el equipo decide si la
  implementación va en una rama `002-dispatch-alerts-prediction` aparte.
