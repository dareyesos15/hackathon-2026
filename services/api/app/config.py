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


class CascadeSettings(BaseModel):
    """Modelo de efectos en cascada por manzana (research R11). Valores SIMULADOS calibrables."""

    weight_slope: float = 35.0
    weight_rain: float = 30.0
    weight_seismic: float = 15.0
    weight_reports: float = 20.0
    slope_saturation_deg: float = 45.0
    rain_saturation_mm: float = 40.0
    reports_saturation: int = 3
    reports_radius_m: float = 300.0
    reports_window_hours: float = 6.0
    cut_medio: float = 25.0
    cut_alto: float = 50.0
    cut_muy_alto: float = 75.0


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
    token_admin: str = "admin-demo"

    dedup: DedupSettings = DedupSettings()
    trust: TrustWeights = TrustWeights()

    # Habilita utilidades de demo (reinicio del escenario). Nunca en producción.
    demo_mode: bool = True

    # Agregación pública por manzana (principio I).
    k_anonymity: int = 5

    # Despacho (specs/002, research R4, R5, R13).
    simulate_tracks: bool = True
    track_tick_s: float = 5.0
    track_speedup: float = 20.0
    routing_speed_kmh: float = 25.0
    routing_tortuosity: float = 1.4
    unattended_alert_min: float = 15.0

    cascade: CascadeSettings = CascadeSettings()

    def role_tokens(self) -> dict[str, str]:
        """Mapa token → rol."""
        return {
            self.token_operador_pmu: "operador_pmu",
            self.token_ciudadano: "ciudadano",
            self.token_publico: "publico",
            self.token_coe: "coe",
            self.token_inspector: "inspector",
            self.token_agencia: "agencia",
            self.token_admin: "admin",
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
