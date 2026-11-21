"use client";
/**
 * Albergues temporales (EMRE 3.2 alojamiento temporal). La ocupación sube y baja sola con las
 * entradas (Ayudas → cupo en albergue) y salidas de los hogares del censo; aquí se administra la
 * entidad responsable, el estado, los servicios y, si hace falta, se corrige el conteo de personas
 * no censadas. Solo agregados: ningún dato de personas.
 */
import { useCallback, useEffect, useState } from "react";
import { EtiquetaSimulado } from "@/components/EtiquetaSimulado";
import { api } from "@/lib/api/client";
import { DEMO_MODE } from "@/lib/env";
import { formatInt, formatTime } from "@/lib/format";
import {
  SERVICE_LABEL,
  errorText,
  type ShelterOut,
  type ShelterService,
  type ShelterStatus,
} from "@/lib/recovery";
import { Casillas } from "./FormatoRevision";
import { Card, Notice, input } from "./ui";

type Edit = {
  operator: string;
  status: ShelterStatus;
  services: ShelterService[];
  people: number;
  pets: number;
};

function editOf(s: ShelterOut): Edit {
  return {
    operator: s.operator ?? "",
    status: s.status ?? "abierto",
    services: s.services ?? [],
    people: s.people,
    pets: s.pets,
  };
}

export function Albergues({ tick }: { tick: number }) {
  const [items, setItems] = useState<ShelterOut[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [edit, setEdit] = useState<Edit | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    () => api.GET("/api/v1/recovery/shelters").then(({ data }) => data && setItems(data.items)),
    [],
  );

  useEffect(() => {
    void load();
  }, [load, tick]);

  async function save(s: ShelterOut) {
    if (!edit) return;
    setError(null);
    const { error: err } = await api.PATCH("/api/v1/recovery/shelters/{shelter_id}", {
      params: { path: { shelter_id: s.id } },
      body: {
        operator: edit.operator,
        status: edit.status,
        services: edit.services,
        people: edit.people !== s.people ? edit.people : null,
        pets: edit.pets !== s.pets ? edit.pets : null,
      },
    });
    if (err) {
      setError(errorText(err, "No se pudo actualizar el albergue"));
      return;
    }
    setOpen(null);
    setEdit(null);
    await load();
  }

  const people = items.reduce((n, s) => n + s.people, 0);
  const capacity = items.filter((s) => s.status === "abierto").reduce((n, s) => n + s.capacity, 0);

  return (
    <Card
      title="Albergues temporales"
      extra={
        <span className="text-xs text-tinta-suave">
          {formatInt(people)} personas alojadas · {formatInt(Math.max(capacity - people, 0))} cupos
          libres en albergues abiertos
        </span>
      }
    >
      <p className="text-xs text-tinta-suave">
        La ocupación cambia sola: sube al entregar un <strong>cupo en albergue</strong> en Ayudas y
        baja al registrar la salida del hogar.
      </p>
      <ul className="flex flex-col divide-y divide-linea">
        {items.map((s) => {
          const pct = s.capacity ? Math.round((s.people / s.capacity) * 100) : 0;
          const editing = open === s.id && edit;
          return (
            <li key={s.id} className="flex flex-col gap-2 py-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{s.name}</span>
                <span className="text-tinta-suave">{s.barrio}</span>
                {s.status === "cerrado" && (
                  <span className="rounded bg-linea px-1.5 text-xs font-semibold">Cerrado</span>
                )}
                {DEMO_MODE && s.source === "SIMULADO" && <EtiquetaSimulado />}
                <span className="ml-auto text-xs text-tinta-suave">
                  {formatInt(s.people)} / {formatInt(s.capacity)} personas · {formatInt(s.families)}{" "}
                  {s.families === 1 ? "hogar" : "hogares"} del censo · {formatInt(s.pets)} mascotas
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded bg-linea">
                <div
                  className="h-full"
                  style={{
                    width: `${pct}%`,
                    background: pct >= 90 ? "#d21f2b" : pct >= 70 ? "#e8a92a" : "#2f7d55",
                  }}
                />
              </div>
              <div className="flex flex-wrap items-center gap-2 text-xs text-tinta-suave">
                <span>
                  {s.operator ? `Administra: ${s.operator}` : "Sin entidad administradora"}
                </span>
                {(s.services ?? []).map((k) => (
                  <span key={k} className="rounded border border-linea px-1.5">
                    {SERVICE_LABEL[k]}
                  </span>
                ))}
                <span>Actualizado {formatTime(s.updated_at)}</span>
                <button
                  type="button"
                  className="ml-auto rounded border border-linea px-2 py-0.5 text-tinta"
                  onClick={() => {
                    setOpen(open === s.id ? null : s.id);
                    setEdit(editOf(s));
                  }}
                >
                  {open === s.id ? "Cancelar" : "Administrar"}
                </button>
              </div>
              {editing && (
                <div className="flex flex-col gap-2 rounded-md border border-linea p-3">
                  <div className="grid gap-2 sm:grid-cols-2">
                    <label className="flex flex-col gap-1 text-xs text-tinta-suave">
                      Entidad administradora
                      <input
                        className={input}
                        value={edit.operator}
                        onChange={(e) => setEdit({ ...edit, operator: e.target.value })}
                        placeholder="Secretaría de Desarrollo Social"
                      />
                    </label>
                    <label className="flex flex-col gap-1 text-xs text-tinta-suave">
                      Estado
                      <select
                        className={input}
                        value={edit.status}
                        onChange={(e) =>
                          setEdit({ ...edit, status: e.target.value as ShelterStatus })
                        }
                      >
                        <option value="abierto">Abierto</option>
                        <option value="cerrado">Cerrado</option>
                      </select>
                    </label>
                  </div>
                  <div className="flex flex-col gap-1 text-xs text-tinta-suave">
                    Servicios disponibles
                    <Casillas
                      options={SERVICE_LABEL}
                      value={edit.services}
                      onChange={(v) => setEdit({ ...edit, services: v })}
                    />
                  </div>
                  <details className="text-xs text-tinta-suave">
                    <summary className="cursor-pointer">
                      Corregir el conteo (personas no censadas)
                    </summary>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <label className="flex items-center gap-1">
                        Personas
                        <input
                          type="number"
                          min={0}
                          max={s.capacity}
                          className={`${input} w-24`}
                          value={edit.people}
                          onChange={(e) => setEdit({ ...edit, people: Number(e.target.value) })}
                        />
                      </label>
                      <label className="flex items-center gap-1">
                        Mascotas
                        <input
                          type="number"
                          min={0}
                          className={`${input} w-20`}
                          value={edit.pets}
                          onChange={(e) => setEdit({ ...edit, pets: Number(e.target.value) })}
                        />
                      </label>
                    </div>
                  </details>
                  <div>
                    <button
                      type="button"
                      onClick={() => save(s)}
                      className="rounded bg-sangre px-3 py-1.5 text-sm font-semibold text-white hover:bg-sangre-claro"
                    >
                      Guardar
                    </button>
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ul>
      {error && <Notice tone="error">{error}</Notice>}
    </Card>
  );
}
