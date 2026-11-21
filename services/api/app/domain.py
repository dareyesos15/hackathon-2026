"""Enumeraciones de dominio (data-model.md §Enumeraciones). Sin dependencias de ORM ni web."""

from enum import StrEnum


class Channel(StrEnum):
    pwa = "pwa"
    sms = "sms"
    whatsapp = "whatsapp"
    call_123 = "call_123"
    scraping = "scraping"
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


class ReportAction(StrEnum):
    ingerido = "ingerido"
    agrupado = "agrupado"
    confirmar = "confirmar"
    descartar = "descartar"
    marcar_duplicado = "marcar_duplicado"
    reabrir = "reabrir"


class PlaceKind(StrEnum):
    barrio = "barrio"
    comuna = "comuna"
    via = "via"
    referencia = "referencia"


class MetricUnit(StrEnum):
    percent = "%"
    count = "conteo"
    minutes = "min"
    ms = "ms"
