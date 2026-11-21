"""Informe de los escenarios SIMULADOS de acceso a datos (mejor y peor caso).

Corre el Monte Carlo de app/core/scenarios.py en varios días de la recuperación y escribe
docs/escenarios_recuperacion.md con la confianza del sistema (media e IC del 90 %) y sus
componentes. Determinista: misma semilla, mismo informe.

Uso (desde la raíz del repo):
    uv run --project services/api python scripts/simulate_recovery_scenarios.py
    uv run --project services/api python scripts/simulate_recovery_scenarios.py --runs 5000
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.core.scenarios import SCENARIOS, Simulation, simulate  # noqa: E402

OUT = ROOT / "docs" / "escenarios_recuperacion.md"
DAYS = (1, 7, 15, 30, 60, 90)


def _fmt(x: float, unit: str) -> str:
    text = f"{x:.1f}".replace(".", ",")
    return f"{text} %" if unit == "%" else f"{text} pts"


def _ci(s: object) -> str:
    unit = s.unit  # type: ignore[attr-defined]
    return (
        f"**{_fmt(s.mean, unit)}** "  # type: ignore[attr-defined]
        f"({_fmt(s.p5, unit)} a {_fmt(s.p95, unit)})"  # type: ignore[attr-defined]
    )


def _table(best: Simulation, worst: Simulation) -> list[str]:
    header = "| Métrica | Mejor caso: media (IC 90 %) | Peor caso: media (IC 90 %) |"
    lines = [header, "|---|---|---|"]
    w = {s.key: s for s in worst.stats}
    for s in best.stats:
        if s.key in w:
            lines.append(f"| {s.label} | {_ci(s)} | {_ci(w[s.key])} |")
    lines.append(
        f"| Corridas con confianza ≥ 75 % | **{best.p_high_confidence:.1f} %** | "
        f"**{worst.p_high_confidence:.1f} %** |".replace(".", ",")
    )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=2000)
    parser.add_argument("--day", type=int, default=None, help="Día actual (por defecto: hoy)")
    args = parser.parse_args()
    event = datetime(2026, 8, 10, 12, 34, tzinfo=UTC)  # USGS us6000tjl2
    today = args.day if args.day is not None else (datetime.now(UTC) - event).days
    days = sorted({*DAYS, today})

    md = [
        "# Escenarios de acceso a datos: confianza del tablero de recuperación (SIMULADO)",
        "",
        f"> Generado con `scripts/simulate_recovery_scenarios.py` el "
        f"{datetime.now(UTC):%Y-%m-%d %H:%M} UTC · {args.runs} corridas por escenario y día · "
        "semilla fija. **Todas las cifras son SIMULADAS**: miden cuánto se acercaría el tablero a "
        "la realidad según cómo le lleguen los datos, no son cifras del evento.",
        "",
        "## Método",
        "",
        "1. **Una sola verdad simulada** del sismo del 10 ago 2026 en Manizales: ~2.000 "
        "predios con daño, ~2.700 familias damnificadas, cobertura de agua, energía, gas, "
        "telecomunicaciones y vías, negocios y empleo, pérdida, recursos y pagos, recaudo, "
        "turismo y café, "
        "evolucionando con una curva de recuperación por días.",
        "2. **Dos procesos de observación** sobre esa misma verdad: qué fuentes entregan dato "
        "en cada corte, cuánto se subregistra, cuánto ruido trae cada cifra, cuántos "
        "duplicados quedan sin unir y con qué retraso llega frente a la cadencia de la EMRE "
        "(6 h los 3 primeros días, "
        "12 h hasta el día 5 y 24 h después). Los primeros días son más caóticos (red y energía "
        "inestables) y ese efecto decae con el tiempo.",
        "3. **Monte Carlo**: en cada corrida se compara lo que vería el tablero con la verdad. Se "
        "reporta la media y el intervalo del 90 % (percentiles 5 y 95).",
        "",
        "**Confianza global (0–100)** = 30 % cobertura + 20 % frescura + 35 % exactitud + 15 % "
        "duplicados detectados.",
        "",
        "- *Cobertura*: cifras del tablero con dato.",
        "- *Frescura*: cifras con dato dentro de la cadencia EMRE.",
        "- *Exactitud*: cifras dentro de ±10 % de la realidad (±5 puntos en porcentajes); las "
        "cifras sin dato cuentan como no exactas.",
        "- *Error del índice*: puntos de diferencia entre el índice de recuperación que ve el "
        "tablero y el real.",
        "",
        "## Supuestos de cada escenario",
        "",
    ]
    for key in ("mejor", "peor"):
        p = SCENARIOS[key]
        md += [f"### {p.title}", "", p.description, ""]
        md += [f"- {a}" for a in p.assumptions]
        md += [
            "- Disponibilidad por fuente: "
            + ", ".join(f"{k} {v:.0%}" for k, v in p.availability.items()),
            "",
        ]

    sims = {(k, d): simulate(k, d, runs=args.runs) for k in ("mejor", "peor") for d in days}
    md += [f"## Resultado hoy (día {today})", ""]
    md += _table(sims[("mejor", today)], sims[("peor", today)])
    md += ["", "## Confianza global a lo largo de la recuperación", ""]
    md += ["| Día | Mejor caso: media (IC 90 %) | Peor caso: media (IC 90 %) | Diferencia |"]
    md += ["|---|---|---|---|"]
    for d in days:
        b = {s.key: s for s in sims[("mejor", d)].stats}["confianza"]
        w = {s.key: s for s in sims[("peor", d)].stats}["confianza"]
        md.append(f"| {d} | {_ci(b)} | {_ci(w)} | {_fmt(b.mean - w.mean, 'pts')} |")
    md += [
        "",
        "## Cómo leerlo",
        "",
        "- Con colaboración institucional, el tablero refleja la realidad casi siempre: las "
        "decisiones del COE se pueden tomar sobre sus cifras.",
        "- Sin ella, el tablero ve una fracción de la realidad, desactualizada y con duplicados: "
        "sirve para alertar, pero cada cifra necesita verificación en terreno. Es lo que pasó en "
        "2026 (1.449 → 2.700 → 1.512 viviendas) y en 1999 (35.000 estimadas frente a 79.500 "
        "censadas).",
        "- La brecha entre ambos escenarios es el valor de los convenios del plan de 30–90 días.",
        "",
    ]
    OUT.write_text("\n".join(md), encoding="utf-8")
    print(f"Informe escrito en {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
