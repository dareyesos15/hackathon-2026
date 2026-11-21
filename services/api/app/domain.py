"""Enumeraciones de dominio (data-model.md §Enumeraciones). Sin dependencias de ORM ni web."""

from enum import StrEnum


class Channel(StrEnum):
    pwa = "pwa"
    sms = "sms"
    whatsapp = "whatsapp"
    call_123 = "call_123"
    entity = "entity"
    lora = "lora"


class Category(StrEnum):
    personas_atrapadas = "personas_atrapadas"
    heridos = "heridos"
    colapso_estructura = "colapso_estructura"
    dano_estructural = "dano_estructural"
    incendio = "incendio"
    fuga_gas = "fuga_gas"
    deslizamiento = "deslizamiento"
    via_bloqueada = "via_bloqueada"
    servicios_caidos = "servicios_caidos"
    necesidad_albergue = "necesidad_albergue"
    necesidad_ayuda = "necesidad_ayuda"
    persona_desaparecida = "persona_desaparecida"
    sismo_sentido = "sismo_sentido"
    rumor_informacion = "rumor_informacion"
    sin_clasificar = "sin_clasificar"


class TriageLevel(StrEnum):
    critico = "critico"
    alto = "alto"
    medio = "medio"
    bajo = "bajo"


TRIAGE_RANK: dict[TriageLevel, int] = {
    TriageLevel.critico: 4,
    TriageLevel.alto: 3,
    TriageLevel.medio: 2,
    TriageLevel.bajo: 1,
}


class GeoPrecision(StrEnum):
    gps = "gps"
    address = "address"
    barrio = "barrio"
    none = "none"


class ReportStatus(StrEnum):
    nuevo = "nuevo"
    en_revision = "en_revision"
    verificado = "verificado"
    descartado = "descartado"
    duplicado = "duplicado"
    atendido = "atendido"


class IncidentStatus(StrEnum):
    abierto = "abierto"
    en_revision = "en_revision"
    verificado = "verificado"
    descartado = "descartado"
    atendido = "atendido"


class TrustLabel(StrEnum):
    verificado = "verificado"
    probable = "probable"
    sin_verificar = "sin_verificar"
    posible_falso = "posible_falso"


class Role(StrEnum):
    ciudadano = "ciudadano"
    operador_pmu = "operador_pmu"
    publico = "publico"
    coe = "coe"
    inspector = "inspector"
    agencia = "agencia"
    sistema = "sistema"
    # Simulaciones de la demo (reiniciar, reproducir el escenario). Nunca queda en la bitácora.
    admin = "admin"


class ReportAction(StrEnum):
    ingerido = "ingerido"
    agrupado = "agrupado"
    confirmar = "confirmar"
    descartar = "descartar"
    marcar_duplicado = "marcar_duplicado"
    reabrir = "reabrir"
    # Despacho (specs/002, research R6).
    despachar = "despachar"
    reforzar = "reforzar"
    despacho_estado = "despacho_estado"
    cancelar_despacho = "cancelar_despacho"
    despacho_doble_bloqueado = "despacho_doble_bloqueado"
    cerrar_atendido = "cerrar_atendido"
    # Gestión de incidentes (PMU/COE): creación manual y sesión de alerta masiva.
    crear_manual = "crear_manual"
    asignar_alerta = "asignar_alerta"
    desacoplar_alerta = "desacoplar_alerta"


class PlaceKind(StrEnum):
    barrio = "barrio"
    comuna = "comuna"
    via = "via"
    referencia = "referencia"


class MetricUnit(StrEnum):
    percent = "%"
    conteo = "conteo"
    minutes = "min"
    ms = "ms"


# --- Despacho, alertas y cascada (specs/002-dispatch-alerts-prediction/data-model.md) ---


class EmreFunction(StrEnum):
    """Seis funciones de respuesta de la EMRE Manizales 2024."""

    salvamento_seguridad = "salvamento_seguridad"
    salud_saneamiento = "salud_saneamiento"
    asistencia_social = "asistencia_social"
    infraestructura_servicios = "infraestructura_servicios"
    manejo_coordinacion = "manejo_coordinacion"
    logistica = "logistica"


EMRE_FUNCTION_LABEL: dict[EmreFunction, str] = {
    EmreFunction.salvamento_seguridad: "1. Salvamento y seguridad",
    EmreFunction.salud_saneamiento: "2. Salud y saneamiento",
    EmreFunction.asistencia_social: "3. Asistencia social",
    EmreFunction.infraestructura_servicios: "4. Infraestructura, servicios y ambiente",
    EmreFunction.manejo_coordinacion: "5. Manejo y coordinación",
    EmreFunction.logistica: "6. Logística",
}


class ResourceType(StrEnum):
    cuadrilla_rescate = "cuadrilla_rescate"
    maquina_extincion = "maquina_extincion"
    ambulancia = "ambulancia"
    patrulla = "patrulla"
    cuadrilla_tecnica = "cuadrilla_tecnica"
    vehiculo_logistico = "vehiculo_logistico"


class ResourceStatus(StrEnum):
    disponible = "disponible"
    en_camino = "en_camino"
    en_sitio = "en_sitio"
    fuera_de_servicio = "fuera_de_servicio"


class DispatchStatus(StrEnum):
    en_camino = "en_camino"
    en_sitio = "en_sitio"
    finalizado = "finalizado"
    cancelado = "cancelado"


class RecipientRole(StrEnum):
    """Papel de una agencia frente a un incidente (app/core/recipients.py)."""

    lider = "lider"
    apoyo = "apoyo"
    informada = "informada"


ACTIVE_DISPATCH: frozenset[DispatchStatus] = frozenset(
    {DispatchStatus.en_camino, DispatchStatus.en_sitio}
)


class TrackKind(StrEnum):
    salida = "salida"
    control = "control"
    llegada = "llegada"
    regreso = "regreso"
    manual = "manual"


class TrackOrigin(StrEnum):
    rfid_simulado = "rfid_simulado"
    manual = "manual"


class AlertType(StrEnum):
    evacuacion = "evacuacion"
    deslizamiento = "deslizamiento"
    sismo_replica = "sismo_replica"
    servicios_publicos = "servicios_publicos"
    informacion_general = "informacion_general"


class AlertStatus(StrEnum):
    borrador = "borrador"
    emitida = "emitida"
    rechazada = "rechazada"
    anulada = "anulada"


class AlertChannel(StrEnum):
    tablero = "tablero"
    mapa_publico = "mapa_publico"
    sms_cuadrillas = "sms_cuadrillas"


class AlertAction(StrEnum):
    crear = "crear"
    editar = "editar"
    confirmar_desinformacion = "confirmar_desinformacion"
    aprobar = "aprobar"
    rechazar = "rechazar"
    anular = "anular"
    aprobacion_conflicto = "aprobacion_conflicto"


class CascadeLevel(StrEnum):
    bajo = "bajo"
    medio = "medio"
    alto = "alto"
    muy_alto = "muy_alto"


# ---------------------------------------------------------------- recuperación (specs/003)


class InspectionColor(StrEnum):
    verde = "verde"
    amarillo = "amarillo"
    rojo = "rojo"


class DamageLevel(StrEnum):
    menor = "menor"
    mediano_uso_restringido = "mediano_uso_restringido"
    mayor = "mayor"
    colapso = "colapso"


class RudStatus(StrEnum):
    pendiente = "pendiente"
    inscrito = "inscrito"


class AidType(StrEnum):
    subsidio_arriendo = "subsidio_arriendo"
    kit = "kit"
    mercado = "mercado"
    albergue = "albergue"


# --- Revisión a predio: formato GUE-RPD-FR-02 v4 de la Alcaldía de Manizales -----------------


class RespondentRelation(StrEnum):
    """Sección 2: calidad del encuestado frente al predio."""

    propietario = "propietario"
    arrendatario = "arrendatario"
    sucesion = "sucesion"
    otro = "otro"


class EventStatus(StrEnum):
    """Sección 4: el evento es inminente o ya sucedió."""

    inminente = "inminente"
    sucedido = "sucedido"


class EventType(StrEnum):
    """Sección 4: tipo de evento (el formato no trae sismo; se agrega para este evento)."""

    sismo = "sismo"
    deslizamiento = "deslizamiento"
    incendio = "incendio"
    vendaval = "vendaval"
    avalancha = "avalancha"
    inundacion = "inundacion"
    otro = "otro"


class StructuralCause(StrEnum):
    """Sección 4: deterioro estructural, posible causa."""

    falta_mantenimiento = "falta_mantenimiento"
    intervencion_antropica = "intervencion_antropica"
    evento_natural = "evento_natural"


class Affectation(StrEnum):
    """Sección 5: afectación del predio."""

    total = "total"
    parcial = "parcial"
    ninguna = "ninguna"


class AffectedInfrastructure(StrEnum):
    """Sección 5: infraestructura afectada (con área en m²)."""

    vivienda = "vivienda"
    vial = "vial"
    educativa = "educativa"
    comunitaria = "comunitaria"


class ReferralEntity(StrEnum):
    """Sección 6: entidades que deben visitar el predio."""

    ugr = "ugr"
    corpocaldas = "corpocaldas"
    aguas_de_manizales = "aguas_de_manizales"
    obras_publicas = "obras_publicas"
    invias = "invias"
    chec = "chec"
    invama = "invama"
    planeacion = "planeacion"
    infraestructura_depto = "infraestructura_depto"
    inspeccion_policia = "inspeccion_policia"
    otro = "otro"


# ------------------------------------------- sensor de zonas inseguras (specs/004, NC2025/0015763)


class ZoneEventKind(StrEnum):
    intrusion = "intrusion"
    acceso_autorizado = "acceso_autorizado"
    bateria_baja = "bateria_baja"
    manipulacion = "manipulacion"


class ZoneDetector(StrEnum):
    ultrasonido = "ultrasonido"
    infrarrojo = "infrarrojo"
    ambos = "ambos"


class ZoneSensorStatus(StrEnum):
    armado = "armado"
    desarmado = "desarmado"


# ------------------------------------------------------------- alerta masiva (toda la ciudad)


class MassAlertStatus(StrEnum):
    activa = "activa"
    resuelta = "resuelta"


class MassAlertEvent(StrEnum):
    """Tipo de evento que dispara la alerta masiva (EMRE Manizales 2024: amenazas principales)."""

    sismo = "sismo"
    deslizamientos = "deslizamientos"
    inundacion = "inundacion"
    ceniza_volcanica = "ceniza_volcanica"
    incendio_estructural = "incendio_estructural"
    otro = "otro"


# --- Censo (RUD · UNGRD), ayudas (acta de entrega) y albergues (EMRE 3.1–3.3) ------------------


class Tenure(StrEnum):
    """Régimen de tenencia de la vivienda (RUD)."""

    propietario = "propietario"
    arrendatario = "arrendatario"
    poseedor = "poseedor"
    ocupante = "ocupante"
    otro = "otro"


class HousingStatus(StrEnum):
    """Estado de la vivienda (RUD), alineado con el semáforo NSR-10."""

    habitable = "habitable"
    no_habitable = "no_habitable"
    destruida = "destruida"


class HouseholdLoss(StrEnum):
    """Pérdidas del hogar (RUD)."""

    enseres = "enseres"
    herramientas_trabajo = "herramientas_trabajo"
    animales = "animales"
    cultivos = "cultivos"
    vehiculo = "vehiculo"


class ShelterStatus(StrEnum):
    abierto = "abierto"
    cerrado = "cerrado"


class ShelterService(StrEnum):
    """Servicios del alojamiento temporal (EMRE 3.2)."""

    agua = "agua"
    energia = "energia"
    banos = "banos"
    cocina = "cocina"
    atencion_salud = "atencion_salud"
    zona_mascotas = "zona_mascotas"
    zona_infantil = "zona_infantil"
