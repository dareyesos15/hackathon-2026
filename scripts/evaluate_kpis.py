"""Evalúa el motor contra la verdad del escenario SIMULADO y publica los KPI (research R8).

Es el ÚNICO componente que lee data/seed/ground_truth.json (principio IV). Consulta la API
REST (GET /reports, GET /incidents) y publica instantáneas en POST /metrics/snapshots.

Uso (dentro del contenedor api, después de replay_scenario.py):
    docker compose exec api python scripts/evaluate_kpis.py [--no-publish] [--no-fail]
Código de salida ≠ 0 si no se cumplen las metas (CLAUDE.md §14).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from _client import api_client

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
MAP_PATH = Path(os.environ.get("REPLAY_MAP", "/tmp/dacora_replay_map.json"))
SOURCE = "evaluate_kpis.py"

TARGETS = {
    "duplicate_detection_rate": (90.0, ">"),
    "fake_detection_rate": (90.0, ">"),
    "critical_recall": (98.0, ">="),
    "critical_auto_discarded": (0, "=="),
}


@dataclass
class Result:
    values: dict[str, float | None]
    details: dict[str, dict[str, Any]]
    cutoff: datetime
    processed: int


def load_truth() -> dict[str, Any]:
    return json.loads((DATA_DIR / "seed" / "ground_truth.json").read_text(encoding="utf-8"))


def fetch_all(client: Any) -> tuple[dict[str, dict], dict[str, dict]]:
    reports: dict[str, dict] = {}
    cursor: str | None = None
    while True:
        params: dict[str, Any] = {"limit": 500}
        if cursor:
            params["cursor"] = cursor
        page = client.get("/reports", params=params).raise_for_status().json()
        reports.update({r["id"]: r for r in page["items"]})
        cursor = page["next_cursor"]
        if not cursor:
            break
    incidents = client.get("/incidents", params={"limit": 2000}).raise_for_status().json()
    return reports, {i["id"]: i for i in incidents["items"]}


def human_discards(client: Any, incident_ids: set[str]) -> set[str]:
    """Reportes con una acción humana de descarte en la bitácora."""
    done: set[str] = set()
    for incident_id in incident_ids:
        detail = client.get(f"/incidents/{incident_id}").raise_for_status().json()
        for event in detail["events"]:
            if event["action"] == "descartar" and event["actor_role"] != "sistema":
                done.add(event["report_id"])
    return done


def pct(num: int, den: int) -> float | None:
    return round(100.0 * num / den, 1) if den else None


def evaluate(client: Any, mapping: dict[str, str], truth: dict[str, Any]) -> Result:
    reports, incidents = fetch_all(client)
    gt: dict[str, dict] = truth["reports"]
    by_seq = {str(v["seq"]): v for v in gt.values()}
    seq_of_key = {k: str(v["seq"]) for k, v in gt.items()}
    start = datetime.fromisoformat(truth["event_start"])

    def report_for(seq: str) -> dict | None:
        rid = mapping.get(seq)
        return reports.get(rid) if rid else None

    def incident_for(rep: dict) -> dict | None:
        return incidents.get(rep["incident_id"]) if rep.get("incident_id") else None

    def flagged_fake(rep: dict) -> bool:
        inc = incident_for(rep)
        return rep["category"] == "rumor_informacion" or bool(
            inc
            and (inc["trust_label"] == "posible_falso" or inc["category"] == "rumor_informacion")
        )

    processed = [seq for seq in by_seq if report_for(seq)]
    dup_total = dup_ok = fake_total = fake_ok = legit_total = legit_flagged = 0
    crit_total = crit_ok = 0
    missed_dups: list[int] = []
    missed_fakes: list[int] = []
    event_first_map: dict[str, float] = {}
    event_first_report: dict[str, float] = {}
    event_incidents: dict[str, set[str]] = defaultdict(set)
    incident_events: dict[str, set[str]] = defaultdict(set)
    max_minute = 0.0
    minutes = {str(v["seq"]): v.get("minute") for v in gt.values()}

    for seq in processed:
        t = by_seq[seq]
        rep = report_for(seq)
        assert rep is not None
        occurred = datetime.fromisoformat(rep["occurred_at"])
        minute = (occurred - start).total_seconds() / 60
        max_minute = max(max_minute, minute)
        if t["label"] in ("unique", "duplicate"):
            legit_total += 1
            legit_flagged += flagged_fake(rep)
            if rep.get("incident_id"):
                event_incidents[t["event_id"]].add(rep["incident_id"])
                incident_events[rep["incident_id"]].add(t["event_id"])
            prev_first = event_first_report.get(t["event_id"])
            event_first_report[t["event_id"]] = (
                minute if prev_first is None else min(prev_first, minute)
            )
            if rep.get("lat") is not None:
                prev = event_first_map.get(t["event_id"])
                event_first_map[t["event_id"]] = minute if prev is None else min(prev, minute)
        if t["label"] == "duplicate":
            original = report_for(seq_of_key[t["duplicate_of"]])
            if original:
                dup_total += 1
                if original["incident_id"] == rep["incident_id"]:
                    dup_ok += 1
                else:
                    missed_dups.append(int(seq))
        if t["label"] == "fake":
            fake_total += 1
            if flagged_fake(rep):
                fake_ok += 1
            else:
                missed_fakes.append(int(seq))
        if t["is_critical"]:
            crit_total += 1
            crit_ok += bool(rep["is_life_threat"])

    discarded_life = {
        r["id"]: r for r in reports.values() if r["is_life_threat"] and r["status"] == "descartado"
    }
    human = human_discards(client, {r["incident_id"] for r in discarded_life.values()})
    auto_discarded = sum(1 for rid in discarded_life if rid not in human)

    events = {t["event_id"] for t in gt.values() if t["label"] != "fake"}
    seen_events = {by_seq[s]["event_id"] for s in processed if by_seq[s]["label"] != "fake"}
    # Latencia por hecho: desde su primer reporte hasta que tiene un incidente ubicado en el mapa.
    latencies = sorted(
        event_first_map[e] - event_first_report[e]
        for e in event_first_map
        if e in event_first_report
    )
    unmapped = len(seen_events) - len(latencies)
    needed = int(0.9 * len(seen_events) + 0.999) if seen_events else 0
    time_to_map = round(latencies[needed - 1], 1) if needed and len(latencies) >= needed else None
    merged_events = sum(1 for evs in incident_events.values() if len(evs) > 1)
    split_events = sum(1 for incs in event_incidents.values() if len(incs) > 1)

    values: dict[str, float | None] = {
        "duplicate_detection_rate": pct(dup_ok, dup_total),
        "fake_detection_rate": pct(fake_ok, fake_total),
        "false_positive_rate": pct(legit_flagged, legit_total),
        "critical_auto_discarded": float(auto_discarded),
        "critical_recall": pct(crit_ok, crit_total),
        "time_to_consolidated_map_min": float(time_to_map) if time_to_map is not None else None,
    }
    details = {
        "duplicate_detection_rate": {
            "detectados": dup_ok,
            "total": dup_total,
            "no_detectados_seq": missed_dups[:30],
        },
        "fake_detection_rate": {
            "detectados": fake_ok,
            "total": fake_total,
            "no_detectados_seq": missed_fakes[:30],
        },
        "false_positive_rate": {"marcados": legit_flagged, "total": legit_total},
        "critical_auto_discarded": {"riesgo_vital_descartados": len(discarded_life)},
        "critical_recall": {"identificados": crit_ok, "total": crit_total},
        "time_to_consolidated_map_min": {
            "hechos_reales": len(events),
            "hechos_vistos": len(seen_events),
            "hechos_en_mapa": len(latencies),
            "hechos_sin_ubicar": unmapped,
            "definicion": "p90 de minutos entre el primer reporte de un hecho y verlo en el mapa",
        },
        "_calidad_agrupacion": {
            "incidentes_que_mezclan_hechos": merged_events,
            "hechos_partidos_en_varios_incidentes": split_events,
        },
    }
    _ = minutes
    return Result(values, details, start + timedelta(minutes=max_minute), len(processed))


UNITS = {
    "duplicate_detection_rate": "%",
    "fake_detection_rate": "%",
    "false_positive_rate": "%",
    "critical_auto_discarded": "conteo",
    "critical_recall": "%",
    "time_to_consolidated_map_min": "min",
}


def publish(client: Any, result: Result) -> None:
    items = [
        {
            "indicator": k,
            "value": v,
            "unit": UNITS[k],
            "source": SOURCE,
            "cutoff_at": result.cutoff.isoformat(),
            "details": result.details.get(k, {}),
        }
        for k, v in result.values.items()
        if v is not None
    ]
    if items:
        client.post("/metrics/snapshots", json={"items": items}).raise_for_status()


def meets_targets(values: dict[str, float | None]) -> list[str]:
    failures = []
    for key, (target, op) in TARGETS.items():
        v = values.get(key)
        ok = v is not None and {">": v > target, ">=": v >= target, "==": v == target}[op]
        if not ok:
            failures.append(f"{key} = {v} (meta {op} {target})")
    return failures


def print_table(result: Result) -> None:
    print(
        f"\nKPI Dacora · {result.processed} reportes evaluados · corte simulado "
        f"{result.cutoff.isoformat()} · fuente {SOURCE} (datos SIMULADOS)"
    )
    for key, value in result.values.items():
        shown = "—" if value is None else f"{value:g} {UNITS[key]}"
        print(f"  {key:32s} {shown}")
    q = result.details["_calidad_agrupacion"]
    print(
        f"  agrupación: {q['incidentes_que_mezclan_hechos']} incidentes mezclan hechos, "
        f"{q['hechos_partidos_en_varios_incidentes']} hechos partidos"
    )


def load_mapping() -> dict[str, str]:
    if not MAP_PATH.exists():
        sys.exit(f"No existe {MAP_PATH}: ejecute primero scripts/replay_scenario.py")
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


def run(publish_snapshot: bool = True, verbose: bool = True) -> Result:
    truth = load_truth()
    with api_client(timeout=60) as client:
        result = evaluate(client, load_mapping(), truth)
        if publish_snapshot:
            publish(client, result)
    if verbose:
        print_table(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-publish", action="store_true")
    parser.add_argument("--no-fail", action="store_true")
    parser.add_argument("--details", action="store_true", help="Imprime el detalle en JSON")
    args = parser.parse_args()
    result = run(publish_snapshot=not args.no_publish)
    if args.details:
        print(json.dumps(result.details, ensure_ascii=False, indent=2))
    failures = meets_targets(result.values)
    if failures:
        print("\nMetas NO cumplidas:\n  " + "\n  ".join(failures))
        return 0 if args.no_fail else 1
    print("\nTodas las metas P0 cumplidas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
