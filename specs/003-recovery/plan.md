# Plan: Recuperación inteligente post-sismo

**Spec**: [spec.md](spec.md) · Rama `feat/006-recovery`

## Decisiones
- Mismo stack: FastAPI + SQLAlchemy async + PostGIS (backend) y Next.js frontend puro con cliente
  tipado `openapi-fetch` (CLAUDE.md §4.1). Sin rutas en Next.js.
- **Migración Alembic `0004_recovery`** con tablas `building_inspections`, `households`,
  `household_vulnerability`, `aid_deliveries`, `shelters` (CLAUDE.md §6).
- **Lógica pura** en `app/core/recovery.py`: normalización de dirección/predio, hash de hogar
  (reusa la sal `pii_salt`), regla de consistencia color↔daño, ventana de duplicidad de ayudas.
- **Router** `app/routers/recovery.py` bajo `/api/v1/recovery`:
  | Método | Ruta | Roles |
  |---|---|---|
  | POST/GET | `/recovery/inspections` | inspector, operador_pmu, coe |
  | GET | `/recovery/properties` (estado vigente por predio) | inspector, operador_pmu, coe |
  | POST/GET | `/recovery/households` | operador_pmu, coe |
  | POST | `/recovery/households/lookup` | operador_pmu, coe |
  | GET | `/recovery/households/export.csv` | operador_pmu, coe |
  | POST/GET | `/recovery/aid` | operador_pmu, coe |
  | GET/PATCH | `/recovery/shelters` | operador_pmu, coe (GET también público) |
  | GET | `/recovery/summary` | todos (público con k ≥ 5) |
- Albergues SIMULADOS sembrados al arrancar (idempotente).
- `POST /demo/reset` trunca inspecciones, hogares, vulnerabilidad y ayudas; reinicia ocupación.
- **Frontend** `apps/web/app/recuperacion/` con pestañas Resumen · Habitabilidad · Censo ·
  Ayudas · Albergues; enlace desde el tablero PMU. El documento del hogar se envía solo por la API
  (que lo hashea) y nunca se guarda en el navegador.
- Tipos TS regenerados desde OpenAPI (`scripts/export_openapi.py` + `npm run gen:api`).

## Verificación
Bajo plazo (decisión del usuario): sin pruebas nuevas; solo `ruff`, `mypy`/compilación, `tsc` y
`eslint` al final. Commits atómicos al final de la implementación.
