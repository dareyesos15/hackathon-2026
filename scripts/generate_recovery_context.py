"""Genera data/seed/recovery_context.json: fuentes externas SIMULADAS del tablero de recuperación.

Representa lo que en producción llegaría por adaptadores (Aguas de Manizales, CHEC, Efigas,
Obras Públicas, Cámara de Comercio, DANE, Hacienda, UNGRD, SECOP, aseguradoras, SGC, Cotelco,
Comité de Cafeteros). Determinista (semilla fija) y coherente con data/geo/barrios.geojson.

Uso: python scripts/generate_recovery_context.py
"""

from __future__ import annotations

import json
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BARRIOS = ROOT / "data" / "geo" / "barrios.geojson"
OUT = ROOT / "data" / "seed" / "recovery_context.json"

COT = timezone(timedelta(hours=-5))
EVENT_AT = datetime(2026, 8, 10, 7, 34, tzinfo=COT)
CUTOFF = datetime(2026, 11, 21, 6, 0, tzinfo=COT)
# Barrios con más daño en el evento real (revisión edificio por edificio).
HARD_HIT = {"Centro", "Milán", "Los Agustinos", "Fundadores", "San José", "Galán", "Palermo"}
SERVICES = ("agua", "energia", "gas", "telecom", "vias")


def _source(name: str, version: int, hours_before: int = 0) -> dict[str, object]:
    return {
        "name": name,
        "version": version,
        "cutoff_at": (CUTOFF - timedelta(hours=hours_before)).isoformat(),
    }


def main() -> None:
    rng = random.Random(20260810)
    features = json.loads(BARRIOS.read_text(encoding="utf-8"))["features"]
    barrios = [(f["properties"]["name"], f["properties"]["comuna"]) for f in features]

    visit_requests: dict[str, int] = {}
    services: dict[str, dict[str, object]] = {}
    for name, _comuna in barrios:
        hard = name in HARD_HIT
        # Escala de la demo (decenas de predios), coherente con el censo y las inspecciones.
        visit_requests[name] = rng.randint(4, 8) if hard else rng.randint(0, 3)
        row: dict[str, object] = {}
        for svc in SERVICES:
            low, high = (62, 92) if hard else (88, 100)
            row[svc] = min(100, rng.randint(low, high))
        lagging = min(int(row[s]) for s in SERVICES)  # type: ignore[call-overload]
        eta_days = 0 if lagging >= 99 else rng.randint(3, 21)
        row["eta"] = (CUTOFF.date() + timedelta(days=eta_days)).isoformat()
        services[name] = row

    economy: dict[str, dict[str, int]] = {}
    for comuna in sorted({c for _, c in barrios}):
        hard = comuna in {"Cumanday", "Palogrande", "San José"}
        closed = rng.randint(180, 420) if hard else rng.randint(30, 120)
        reopened = int(closed * rng.uniform(0.45, 0.8))
        jobs_lost = closed * rng.randint(3, 6)
        economy[comuna] = {
            "businesses_closed": closed,
            "businesses_reopened": reopened,
            "jobs_lost": jobs_lost,
            "jobs_recovered": int(jobs_lost * rng.uniform(0.4, 0.75)),
        }

    aftershocks = []
    for _ in range(6):
        at = CUTOFF - timedelta(hours=rng.randint(2, 7 * 24))
        aftershocks.append(
            {
                "at": at.isoformat(),
                "magnitude": round(rng.uniform(2.6, 4.4), 1),
                "depth_km": rng.randint(90, 115),
            }
        )
    aftershocks.sort(key=lambda a: str(a["at"]), reverse=True)

    # Curva histórica del índice (día 0 a 90), forma logística con ruido: SIMULADA.
    history = []
    for day in range(0, 91, 3):
        base = 15 + 47 / (1 + 2.718 ** (-(day - 35) / 11))
        history.append({"day": day, "value": round(min(100.0, base + rng.uniform(-1.5, 1.5)), 1)})

    billion = 1_000_000_000
    context = {
        "note": "SIMULADO: fuentes externas sintéticas para la demo; no son cifras oficiales.",
        "version": 1,
        "event": {"at": EVENT_AT.isoformat(), "magnitude": 7.4, "date": date(2026, 8, 10).isoformat()},
        "sources": {
            "alcaldia": _source("Alcaldía de Manizales · solicitudes de visita (SIMULADO)", 7, 6),
            "catastro": _source("Catastro IGAC / Alcaldía (SIMULADO)", 2, 48),
            "servicios": _source(
                "Aguas de Manizales, CHEC, Efigas y Obras Públicas (SIMULADO)", 31, 3
            ),
            "economia": _source("Cámara de Comercio de Manizales y DANE (SIMULADO)", 9, 72),
            "finanzas": _source("Hacienda, UNGRD, SECOP y aseguradoras (SIMULADO)", 12, 24),
            "sgc": _source("Servicio Geológico Colombiano (SIMULADO)", 1, 1),
            "lluvia": _source("Estaciones UNAL y Corpocaldas (SIMULADO)", 1, 1),
            "estabilizacion": _source(
                "Hacienda (ICA), Cotelco y Comité de Cafeteros (SIMULADO)", 3, 168
            ),
            "indice": _source("Dacora · histórico del índice (SIMULADO)", 1, 24),
        },
        "visit_requests": visit_requests,
        "services": services,
        "economy": economy,
        "aftershocks": aftershocks,
        "rain": {"mm_3h": 18.0, "threshold_mm_3h": 25.0},
        "finance": {
            "estimated_loss_cop": 1_840 * billion,
            "funding_sources": [
                {"name": "Fondo Municipal de Gestión del Riesgo", "amount_cop": 120 * billion},
                {"name": "Gobernación de Caldas", "amount_cop": 180 * billion},
                {"name": "UNGRD · Fondo Nacional", "amount_cop": 520 * billion},
                {"name": "Aseguradoras", "amount_cop": 310 * billion},
                {"name": "Findeter / Bancóldex (crédito)", "amount_cop": 260 * billion},
            ],
            "funnel": {
                "committed_cop": 1_390 * billion,
                "contracted_cop": 905 * billion,
                "paid_cop": 512 * billion,
                "verified_cop": 298 * billion,
            },
            "avg_days_to_payment": 41,
            "benefits": {"requested": 9_420, "approved": 6_870, "paid": 4_310},
            "double_benefits_blocked": 312,
            "local_purchases_cop": 214 * billion,
        },
        "impact": {"commercial_zones_affected": 9},
        "stabilization": {
            "ica_vs_pre_pct": 86.0,
            "tourism_vs_pre_pct": 71.0,
            "coffee_vs_pre_pct": 94.0,
        },
        "index_history": history,
    }
    OUT.write_text(json.dumps(context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Escrito {OUT.relative_to(ROOT)}: {len(barrios)} barrios, {len(economy)} comunas")


if __name__ == "__main__":
    main()
