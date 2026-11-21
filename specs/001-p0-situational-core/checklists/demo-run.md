# Corrida de validación P0 · 2026-11-20 (noche) · Mac arm64, Docker 29.6

Ejecución de [quickstart.md](../quickstart.md) desde `docker compose down -v`.

| Paso | Resultado | Evidencia |
|---|---|---|
| 1. Arranque desde cero (imágenes ya construidas) | ✅ 11 s hasta `/health` = ok; `api`, `db`, `web` healthy | `docker compose up -d --build --pull never` |
| 2. SMS crítico + duplicado | ✅ crítico, riesgo vital, Milán, 3 personas; el segundo se une (+1 fuente, trust sube) | `simulate_sms.py`, `--sobre-critico` |
| 3. Redacción de datos personales | ✅ 0 coincidencias de PII tras reproducir todo el escenario; mismos 20 casos en Python y TS | `test_pii_scenario.py`, `redact.test.ts` |
| 4. Rumor detectado | ✅ `rumor_informacion`, `posible_falso`, señales `reenvia`, `dicen que`, `replica de 9` | prueba de integración y escenario |
| 5. Tablero en vivo y decisión humana | ✅ mapa, matriz, detalle con desglose de 7 señales, nota obligatoria para descartar riesgo vital, bitácora; SSE a través de Nginx | revisión manual en Chrome + `test_review.py` |
| 6. Reproducción y KPI | ✅ duplicados 100 %, falsos 94,7 %, falsos positivos 0 %, recall de críticos 100 %, 0 críticos descartados por la IA, p90 hecho→mapa 0 min | `replay_scenario.py --speed 0` |
| 7. PWA | ✅ en línea: consentimiento, vista previa redactada, envío, llega redactado al servidor. Sin conexión: cubierto por `outbox.test.ts` | revisión manual en Chrome (localhost) |
| 8. Calidad | ✅ ruff, black, mypy estricto en `app/core`, 129 pruebas API, ESLint, Prettier, typecheck, 28 pruebas web | |

Robustez del motor en otros escenarios generados (semillas 7 y 2024): duplicados 98,7 % / 94,7 %,
falsos 97,4 % / 100 %, falsos positivos 0 %.

## Pendiente (requiere a una persona del equipo)

- [ ] Repetir el paso 1 con el **Wi-Fi apagado** (las imágenes ya construidas no necesitan red; el
      frontend no hace peticiones externas: estilo de mapa local, sin fuentes web).
- [ ] Probar el **modo avión en un celular real** contra `http://<IP>:8080/reportar/` con la página
      abierta.
- [ ] Grabar el **video de respaldo** (T071) y anotar su ubicación en `docs/guion_demo.md`.
