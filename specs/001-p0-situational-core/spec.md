# Feature Specification: Núcleo situacional P0 de Dacora

**Feature Branch**: `001-p0-situational-core`

**Created**: 2026-11-20

**Status**: Draft

**Input**: User description: "arranca con p0" — alcance P0 de CLAUDE.md §8 (puntos 1–7) y criterios
de terminado de §14: captura ciudadana sin conexión, canal SMS compacto, motor de verificación
(redacción de datos personales → clasificación → gravedad → agrupación de duplicados → puntaje de
veracidad), tablero del PMU, panel de KPI en vivo y reproducción del escenario sintético del sismo
del 10 ago 2026.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reportes verificados y agrupados automáticamente (Priority: P1)

Un operador del Puesto de Mando Unificado (PMU) recibe reportes de varios canales (reporte
ciudadano estructurado, SMS compacto, entidad oficial, WhatsApp reenviado). Cada reporte llega ya
sin datos personales, con una categoría, un nivel de triaje (Crítico, Alto, Medio, Bajo), una
ubicación, y unido al incidente al que pertenece si otro reporte ya describió el mismo hecho. Cada
incidente tiene un puntaje de veracidad de 0 a 100 con su desglose (por qué tiene ese puntaje).

**Why this priority**: es el corazón del KPI oficial del reto (detección de falsos y duplicados
> 90 %) y lo que convierte información dispersa en decisiones; sin esto el tablero solo
mostraría ruido.

**Independent Test**: se envía un lote de reportes conocidos (incluye duplicados, falsos y
reportes con teléfonos y cédulas) y se consulta el resultado: se verifica categoría, triaje,
agrupación, puntaje con desglose y ausencia de datos personales, sin necesidad del mapa ni de la
aplicación ciudadana.

**Acceptance Scenarios**:

1. **Given** no hay incidentes en el sector, **When** llega el SMS
   `DACORA ATR MILAN 3 edificio caido cra 23`, **Then** se registra un reporte de categoría
   "personas atrapadas", nivel Crítico, marcado como riesgo para la vida, ubicado en el barrio
   Milán con precisión "barrio", con 3 personas afectadas, y se crea un incidente nuevo.
2. **Given** existe un incidente de personas atrapadas en Milán creado hace 40 minutos, **When**
   llega desde otro canal y otro remitente un reporte del mismo hecho a menos de 250 m, **Then** el
   reporte se une a ese incidente, el incidente suma una fuente independiente y su puntaje de
   veracidad sube.
3. **Given** el mismo remitente envía tres veces el mismo mensaje, **When** se procesan, **Then**
   los tres quedan en el mismo incidente pero cuentan como una sola fuente independiente.
4. **Given** un mensaje "reenvía urgente: dicen que habrá una réplica de 9 a las 3 p. m.",
   **When** se procesa, **Then** se clasifica como rumor, recibe la etiqueta "Posible falso"
   (< 25) y su desglose muestra las señales de desinformación detectadas.
5. **Given** un reporte que contiene "me llamo Ana, mi cel 3001234567, cédula 1053123456",
   **When** se procesa, **Then** el texto almacenado contiene `[NOMBRE]`, `[TEL]` y `[CC]` en
   lugar de los datos, y ningún dato personal en claro queda guardado.
6. **Given** un reporte de personas atrapadas con puntaje de veracidad bajo, **When** el sistema
   termina de procesarlo, **Then** el reporte queda en la cola de revisión humana y nunca en
   estado "descartado".
7. **Given** se reenvía exactamente el mismo reporte (mismo identificador de cliente), **When** se
   recibe por segunda vez, **Then** no se crea un reporte nuevo y se devuelve el ya registrado.

---

### User Story 2 - Tablero situacional del PMU con decisión humana (Priority: P2)

El operador del PMU ve en un mapa de Manizales los incidentes coloreados por nivel de triaje y
dimensionados por número de reportes, una capa de intensidad por manzana, y una matriz/lista de
triaje filtrable. Al abrir un incidente ve sus reportes, el desglose del puntaje de veracidad y
puede confirmar, descartar o marcar como duplicado; cada decisión queda registrada con su rol y
hora. El tablero se actualiza solo cuando llegan reportes nuevos.

**Why this priority**: es el entregable oficial del reto ("tablero de comando situacional
geoespacial") y el lugar donde se cumple "la IA sugiere, decide un humano".

**Independent Test**: con incidentes ya cargados (por ejemplo, desde la historia 1), un integrante
abre el tablero, filtra por "Crítico", abre un incidente, lo confirma, y verifica que la acción
aparece en la bitácora y que un reporte nuevo aparece en el mapa sin recargar la página.

**Acceptance Scenarios**:

1. **Given** hay incidentes de varios niveles, **When** el operador abre el tablero, **Then** ve
   cada incidente en el mapa con color por nivel de triaje y tamaño proporcional a su número de
   reportes, y la capa por manzana con la concentración de reportes.
2. **Given** el tablero está abierto, **When** llega un reporte nuevo, **Then** aparece en el mapa
   y en la lista en menos de 5 segundos sin recargar la página.
3. **Given** el operador filtra por nivel "Crítico" y estado "en revisión", **When** aplica el
   filtro, **Then** la lista muestra solo esos incidentes, ordenados por nivel y antigüedad.
4. **Given** el operador abre un incidente, **When** revisa el detalle, **Then** ve cada componente
   del puntaje (canal, fuentes independientes, consistencia física, precisión geográfica, señales
   de desinformación, evidencia, sensor) con su aporte, y la etiqueta resultante.
5. **Given** un incidente abierto, **When** el operador pulsa "Confirmar", "Descartar" o "Marcar
   duplicado", **Then** el estado cambia, la acción queda en la bitácora con rol, fecha y hora, y
   el reporte original no se borra ni se sobrescribe.
6. **Given** un incidente con riesgo para la vida, **When** se descarta, **Then** el sistema exige
   que la acción la haga una persona con rol de operador y queda registrada; nunca ocurre de forma
   automática.

---

### User Story 3 - Reproducción del sismo y KPI medidos en vivo (Priority: P3)

Un integrante del equipo lanza la reproducción del escenario sintético del sismo del 10 ago 2026
(entre 150 y 300 reportes de las primeras 12 horas, en tiempo acelerado). El mapa se llena en
vivo y un panel de KPI muestra, contra la verdad conocida del escenario: porcentaje de duplicados
detectados, porcentaje de falsos detectados, reportes recibidos frente a incidentes consolidados,
reportes críticos descartados automáticamente (debe ser 0) y tiempo hasta el mapa consolidado.
Cada cifra muestra fuente, versión y fecha/hora de corte.

**Why this priority**: es la evidencia medible para el jurado (componente "Impactos") y el motor
de la demo de 3–4 minutos; depende de las historias 1 y 2 para lucir, pero su cálculo de KPI se
puede probar solo.

**Independent Test**: se ejecuta la reproducción completa y luego la evaluación; se comprueba que
los porcentajes reportados coinciden con un conteo manual sobre una muestra y que todas las
cifras del panel tienen fuente y fecha de corte.

**Acceptance Scenarios**:

1. **Given** el sistema recién arrancado, **When** se lanza la reproducción a la velocidad por
   defecto (1 hora del evento = 1 minuto real), **Then** los reportes llegan en el orden y ritmo
   del escenario y el mapa se va llenando en vivo.
2. **Given** la reproducción terminó, **When** se abre el panel de KPI, **Then** muestra detección
   de duplicados y de falsos > 90 %, 0 reportes críticos descartados automáticamente, la relación
   reportes recibidos → incidentes consolidados y el tiempo hasta mapa consolidado.
3. **Given** cualquier cifra del panel, **When** el usuario la mira, **Then** ve su fuente,
   versión y fecha/hora de corte en hora de Colombia.
4. **Given** el escenario, **When** se revisa el motor, **Then** la verdad conocida del escenario
   (qué es único, duplicado o falso) no fue usada por el motor, solo por la evaluación.
5. **Given** datos simulados (escenario, geografía sintética), **When** se muestran en pantalla,
   **Then** llevan la etiqueta visible "SIMULADO".

---

### User Story 4 - Reporte ciudadano sin conexión (Priority: P4)

Una persona en Manizales, sin señal de datos, abre la aplicación de reporte, acepta el aviso de
privacidad, llena un formulario corto (categoría, descripción, ubicación por GPS o por barrio,
número de personas, foto opcional) y envía. El reporte queda guardado en su teléfono en una cola
de envío; cuando vuelve la conexión se sincroniza solo, una sola vez, y aparece en el tablero.

**Why this priority**: demuestra la restricción offline-first del reto y es el momento más
visual de la demo (modo avión), pero el núcleo de valor (historias 1–3) funciona sin ella.

**Independent Test**: con el teléfono en modo avión se crea un reporte, se verifica que queda
"pendiente de envío", se desactiva el modo avión y se comprueba que aparece una sola vez en el
sistema, sin datos personales.

**Acceptance Scenarios**:

1. **Given** es el primer uso, **When** la persona abre la aplicación, **Then** ve el aviso de
   privacidad y no puede enviar un reporte hasta aceptarlo explícitamente.
2. **Given** el dispositivo sin conexión, **When** la persona envía un reporte, **Then** la
   aplicación confirma "guardado, se enviará cuando haya señal" y el reporte queda en la cola.
3. **Given** hay reportes en cola, **When** vuelve la conexión, **Then** se envían
   automáticamente sin acción de la persona y la cola queda vacía.
4. **Given** la conexión se cae a mitad del envío, **When** se reintenta, **Then** el reporte no
   queda duplicado en el sistema.
5. **Given** la persona escribe su teléfono o cédula en la descripción, **When** guarda el
   reporte, **Then** el dato ya está reemplazado por un marcador en su propio dispositivo antes
   de salir.
6. **Given** no hay GPS disponible, **When** la persona elige su barrio de una lista, **Then** el
   reporte se ubica en el centro del barrio con precisión "barrio".

---

### Edge Cases

- **SMS mal formado** (código desconocido, sin barrio, más de 160 caracteres): se registra con
  categoría por texto libre o "sin clasificar", precisión geográfica "ninguna", y va a revisión
  humana; nunca se pierde.
- **Barrio o lugar no reconocido**: el reporte se guarda sin coordenadas, con precisión "ninguna",
  y aparece en la lista de triaje aunque no en el mapa.
- **Reporte crítico con señales de desinformación** (ej. "dicen que hay atrapados en …"): el
  puntaje baja pero el reporte sigue siendo crítico y va a revisión humana.
- **Dos incidentes cercanos de categorías distintas** (incendio y vía bloqueada en la misma
  cuadra): no se fusionan.
- **Mismo hecho reportado más de 3 horas después**: crea un incidente nuevo (fuera de ventana).
- **Avalancha de reportes** (todo el escenario en pocos segundos): ningún reporte se pierde y el
  tablero se pone al día.
- **El tablero pierde la conexión en vivo**: sigue mostrando datos actualizados consultando
  periódicamente y avisa que está en modo de respaldo.
- **El modelo semántico no está disponible**: la agrupación sigue funcionando con un método
  alternativo más simple y el sistema no se detiene.
- **Cola local llena o almacenamiento del teléfono no disponible**: la aplicación avisa a la
  persona y no simula un envío exitoso.
- **Descarte de un reporte ya agrupado**: el incidente recalcula conteo, fuentes y puntaje.

## Requirements *(mandatory)*

### Functional Requirements

**Arranque y operación sin internet**

- **FR-001**: El sistema MUST arrancar completo con un solo comando en un portátil sin conexión a
  internet y cargar automáticamente la geografía y el escenario de demo.
- **FR-002**: El sistema MUST funcionar sin ningún servicio en la nube; mapas base, geografía y
  modelos MUST estar disponibles localmente.

**Ingesta y privacidad**

- **FR-003**: El sistema MUST aceptar reportes por estos canales: aplicación ciudadana, SMS
  compacto, entidad oficial, WhatsApp reenviado (simulado), llamada 123 (simulado) y lote de
  sincronización de la aplicación ciudadana.
- **FR-004**: El sistema MUST interpretar SMS con el formato
  `DACORA <CÓDIGO> <BARRIO o lat,lon> <N_PERSONAS> <texto>` (≤ 160 caracteres) con los códigos
  ATR, HER, COL, DAN, INC, GAS, DES, VIA, SER, ALB, AYU, DSP.
- **FR-005**: Cada reporte MUST tener un identificador generado por el cliente; recibir dos veces
  el mismo identificador MUST NOT crear un segundo reporte.
- **FR-006**: El sistema MUST reemplazar por marcadores (`[TEL]`, `[CC]`, `[CORREO]`, `[PLACA]`,
  `[NOMBRE]`) los celulares colombianos, cédulas, correos, placas y nombres propios introducidos
  por "me llamo", "soy" o "mi mamá/papá/hijo…" **antes de guardar** cualquier reporte.
- **FR-007**: El remitente MUST guardarse solo como huella irreversible con clave secreta, que
  permita reconocer al mismo remitente sin conocer su dato.
- **FR-008**: La aplicación ciudadana MUST aplicar la misma redacción en el dispositivo antes de
  enviar, y el sistema central MUST volver a aplicarla al recibir.
- **FR-009**: Los reportes MUST ser solo-agregar: ningún reporte se sobrescribe ni se borra; todo
  cambio de estado queda en una bitácora con rol, acción y fecha/hora.

**Clasificación y triaje**

- **FR-010**: El sistema MUST asignar a cada reporte una de las categorías: personas atrapadas,
  heridos, colapso de estructura, daño estructural, incendio, fuga de gas, deslizamiento, vía
  bloqueada, servicios caídos, necesidad de albergue, necesidad de ayuda, persona desaparecida,
  sismo sentido, rumor/información.
- **FR-011**: El sistema MUST asignar nivel de triaje según la matriz de CLAUDE.md §7.2 y marcar
  como riesgo para la vida las categorías de nivel Crítico.
- **FR-012**: El sistema MUST extraer la ubicación del texto usando un listado local de barrios,
  comunas, vías y referencias de Manizales; sin GPS, ubica en el centro del barrio con precisión
  "barrio"; sin lugar reconocido, precisión "ninguna".
- **FR-013**: Un reporte con riesgo para la vida MUST NOT quedar descartado ni marcado como falso
  por el sistema; MUST ir a revisión humana sin importar su puntaje.

**Agrupación de duplicados**

- **FR-014**: El sistema MUST unir un reporte a un incidente existente cuando la categoría es la
  misma o compatible, la distancia es ≤ 250 m (≤ 600 m si la precisión es "barrio"), la diferencia
  de tiempo es ≤ 3 h y la similitud del texto supera el umbral configurado (0,75, o 0,6 con
  ubicación exacta).
- **FR-015**: Un reporte duplicado MUST sumar corroboración al incidente y completar datos que le
  falten (p. ej. número de personas, ubicación más precisa); MUST NOT eliminarse.
- **FR-016**: Reportes del mismo remitente MUST contar como una sola fuente independiente.
- **FR-017**: Los umbrales de agrupación MUST ser configurables sin cambiar el sistema.

**Puntaje de veracidad**

- **FR-018**: El sistema MUST calcular para cada incidente un puntaje de 0 a 100 con las señales y
  pesos de CLAUDE.md §7.4 y guardar el desglose por señal.
- **FR-019**: El sistema MUST etiquetar el puntaje como Verificado (≥ 75), Probable (50–74), Sin
  verificar (25–49) o Posible falso (< 25).
- **FR-020**: El puntaje MUST recalcularse cuando el incidente recibe un nuevo reporte o una
  decisión humana.
- **FR-021**: Procesar un reporte (redacción, clasificación, triaje, agrupación y puntaje) MUST
  tardar menos de 1 segundo.

**Tablero del PMU**

- **FR-022**: El tablero MUST mostrar los incidentes en un mapa de Manizales con color por nivel
  de triaje y tamaño por número de reportes, y una capa por manzana con la concentración de
  reportes.
- **FR-023**: El tablero MUST ofrecer una lista/matriz de triaje filtrable por nivel, estado y
  categoría.
- **FR-024**: El detalle de un incidente MUST mostrar sus reportes (texto redactado, canal, hora),
  el desglose del puntaje y la bitácora de acciones.
- **FR-025**: El operador MUST poder confirmar, descartar o marcar como duplicado un incidente o
  reporte; la acción MUST quedar en la bitácora.
- **FR-026**: El tablero MUST actualizarse solo cuando lleguen reportes o cambios, en menos de
  5 segundos, y MUST seguir actualizándose por consulta periódica si se pierde la conexión en
  vivo.
- **FR-027**: El acceso al tablero y a las acciones MUST estar limitado por rol (operador del PMU
  para decidir; público sin acceso a reportes individuales).

**KPI y trazabilidad**

- **FR-028**: El panel de KPI MUST mostrar: % de duplicados detectados, % de falsos detectados,
  reportes recibidos frente a incidentes consolidados, reportes críticos descartados
  automáticamente y tiempo hasta mapa consolidado.
- **FR-029**: Cada cifra del tablero y del panel MUST mostrar fuente, versión y fecha/hora de
  corte en hora de Colombia.
- **FR-030**: Los KPI MUST calcularse comparando con la verdad conocida del escenario, que MUST
  estar separada y no ser accesible para el motor de verificación.

**Escenario de demo**

- **FR-031**: El sistema MUST incluir un escenario sintético del sismo del 10 ago 2026
  (07:34, 0–12 h) con 150–300 reportes concentrados en Centro, Milán, Av. Santander, Av. Paralela
  y carrera 23, con ~55 % únicos, ~30 % duplicados y ~15 % falsos o rumores, sin datos personales
  reales.
- **FR-032**: El escenario MUST poder reproducirse contra el sistema en tiempo acelerado con
  velocidad configurable (por defecto 1 h del evento = 1 min real).
- **FR-033**: Todo dato, capa o canal simulado MUST mostrarse con la etiqueta "SIMULADO".

**Aplicación ciudadana**

- **FR-034**: La aplicación ciudadana MUST mostrar el aviso de privacidad y exigir
  consentimiento explícito antes del primer reporte.
- **FR-035**: La aplicación ciudadana MUST permitir crear reportes sin conexión, guardarlos en el
  dispositivo y enviarlos automáticamente al volver la conexión, con reintentos.
- **FR-036**: La aplicación ciudadana MUST mostrar a la persona el estado de cada reporte
  (pendiente, enviado).
- **FR-037**: Toda la interfaz MUST estar en español de Colombia (números `1.449`, decimales con
  coma, hora de Colombia).

### Key Entities *(include if feature involves data)*

- **Reporte**: un mensaje de una persona o entidad sobre la emergencia. Canal, hora de recepción
  y de ocurrencia, texto redactado, texto de lugar, ubicación y su precisión, manzana, categoría,
  gravedad, nivel de triaje, personas afectadas, si trae evidencia, huella del remitente,
  incidente al que pertenece, estado, si es riesgo para la vida. Solo-agregar.
- **Evento de reporte (bitácora)**: cada acción sobre un reporte o incidente: quién (rol), qué,
  cuándo y datos de la acción.
- **Incidente**: agrupación de reportes que describen el mismo hecho. Ubicación central,
  categoría, nivel de triaje, número de reportes, fuentes independientes, puntaje de veracidad y
  desglose, primera y última vez visto, estado.
- **Manzana**: unidad geográfica de agregación con barrio, comuna, zona sísmica y población;
  puede ser sintética (etiquetada SIMULADO).
- **Lugar de referencia**: entrada del listado local (barrio, comuna, vía, sitio de referencia)
  con su punto central, usada para ubicar reportes sin GPS.
- **Indicador (instantánea de métrica)**: valor de un KPI con fuente, versión y fecha de corte.
- **Verdad del escenario**: para cada reporte sintético, si es único, duplicado de cuál, o falso;
  separada del motor.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un integrante sin experiencia previa pone en marcha la demo completa desde cero en
  menos de 5 minutos siguiendo una sola instrucción, en un portátil sin internet.
- **SC-002**: Sobre el escenario completo, el sistema detecta más del 90 % de los reportes
  duplicados y más del 90 % de los reportes falsos.
- **SC-003**: 0 reportes con riesgo para la vida quedan descartados o marcados como falsos sin una
  decisión humana, y menos del 2 % de los reportes críticos quedan sin marcar como críticos.
- **SC-004**: 0 teléfonos, cédulas o correos del escenario aparecen en los datos almacenados
  (verificado automáticamente sobre todo el escenario).
- **SC-005**: Un reporte nuevo aparece en el tablero en menos de 5 segundos después de recibido,
  y cada reporte se procesa en menos de 1 segundo.
- **SC-006**: Un reporte creado en modo avión aparece exactamente una vez en el tablero en menos
  de 30 segundos después de restablecer la conexión.
- **SC-007**: El 100 % de las cifras visibles en el tablero y el panel de KPI muestran fuente y
  fecha/hora de corte.
- **SC-008**: Al terminar la reproducción, el panel muestra cuántos reportes se consolidaron en
  cuántos incidentes y en cuántos minutos simulados se consolidó el mapa.
- **SC-009**: Cualquier integrante del equipo puede ejecutar el guion de demo de 3–4 minutos sin
  ayuda, siguiendo la guía escrita.

## Assumptions

- **Alcance**: esta especificación cubre solo el P0 (CLAUDE.md §8, puntos 1–7). Sensores, despacho,
  alertas, recuperación, nivel de emergencia, RAG y LoRa quedan para especificaciones posteriores.
- **Arquitectura**: dos servicios principales (backend y frontend) comunicados por una API con
  contrato publicado, según la constitución v1.2.0, principio X; los detalles se definen en el plan.
- **Roles**: para la demo bastan credenciales fijas por rol (ciudadano, operador del PMU, público);
  no hay registro de usuarios.
- **Geografía**: si no hay datos oficiales de manzanas y barrios disponibles sin conexión, se usa
  una grilla sintética sobre el casco urbano y un listado aproximado de barrios, etiquetados
  SIMULADO. Centro de referencia: 5.0689, -75.5174.
- **Consistencia física**: sin sensores (P1), la señal de consistencia física del puntaje usa un
  valor neutro y se muestra como "sin dato de sensor" en el desglose.
- **Fotos**: la foto opcional se guarda solo como evidencia visible para el PMU; nunca se publica.
  Para la demo basta registrar que el reporte trae evidencia y mostrar la imagen al operador.
- **Canales simulados**: WhatsApp, llamada 123 y entidades oficiales se simulan inyectando
  mensajes con su canal; no hay integración real con esos servicios en P0.
- **Velocidad de reproducción**: por defecto 1 h del evento = 1 min real (12 min para todo el
  escenario); configurable para demos más cortas.
- **Código previo del equipo**: si existe el triaje 0–100 del estudio SIRA, se evalúa en el plan
  para integrarlo en lugar de reescribirlo.
