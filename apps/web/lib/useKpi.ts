"use client";
/** KPI con fuente y fecha de corte (GET /metrics/kpi). Se refresca cuando llega `kpi.updated`. */
import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

export type Kpi = components["schemas"]["Kpi"];

export function useKpi(refreshKey: number) {
  const [items, setItems] = useState<Kpi[]>([]);
  useEffect(() => {
    let active = true;
    api.GET("/api/v1/metrics/kpi").then(({ data }) => {
      if (active && data) setItems(data.items);
    });
    return () => {
      active = false;
    };
  }, [refreshKey]);
  return items;
}

export function kpiMap(items: Kpi[]): Record<string, Kpi> {
  return Object.fromEntries(items.map((k) => [k.indicator, k]));
}
