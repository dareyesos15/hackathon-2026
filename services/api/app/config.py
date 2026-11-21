"""Configuración tipada de la API (pydantic-settings).

Umbrales de agrupación: research R1 (calibrados con scripts/evaluate_kpis.py).
Pesos del trust score: CLAUDE.md §7.4.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DedupSettings(BaseModel):
    """Parámetros de agrupación de reportes en incidentes (FR-014, FR-017)."""

    max_distance_m: float = 250.0
    max_distance_barrio_m: float = 600.0
    window_hours: float = 3.0
    # Mismo cruce de vías en el texto: tolera la imprecisión de ubicar por barrio o vía.
    address_match_distance_m: float = 1500.0
    # Umbrales de similitud para TF-IDF de caracteres (research R1).
    similarity_threshold: float = 0.15
    similarity_threshold_exact: float = 0.10


class TrustWeights(BaseModel):
    """Pesos máximos por señal del trust score (CLAUDE.md §7.4)."""

    channel: float = 30.0
    independent_sources: float = 25.0
    physical_consistency: float = 20.0
    geo_precision: float = 10.0
    misinformation_min: float = -15.0
    evidence: float = 5.0
    field_sensor: float = 10.0
    sources_saturation: int = 4


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_version: str = "0.1.0"
    database_url: str = "postgresql+asyncpg://dacora:dacora@localhost:5432/dacora"
    data_dir: Path = Path(__file__).resolve().parents[3] / "data"

    pii_salt: str = Field(default="demo-salt-cambiar-en-produccion", min_length=8)
    similarity_provider: str = "tfidf"

    token_operador_pmu: str = "pmu-demo"
    token_ciudadano: str = "ciudadano-demo"
    token_publico: str = "publico-demo"
    token_coe: str = "coe-demo"
    token_inspector: str = "inspector-demo"
    token_agencia: str = "agencia-demo"

    dedup: DedupSettings = DedupSettings()
    trust: TrustWeights = TrustWeights()

    # Habilita utilidades de demo (reinicio del escenario). Nunca en producción.
    demo_mode: bool = True

    # Agregación pública por manzana (principio I).
    k_anonymity: int = 5

    def role_tokens(self) -> dict[str, str]:
        """Mapa token → rol."""
        return {
            self.token_operador_pmu: "operador_pmu",
            self.token_ciudadano: "ciudadano",
            self.token_publico: "publico",
            self.token_coe: "coe",
            self.token_inspector: "inspector",
            self.token_agencia: "agencia",
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
