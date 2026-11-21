# Contrato: SMS compacto (y mensajes LoRa en P2)

```text
DACORA <CÓDIGO> <LUGAR> <N_PERSONAS> <texto libre>
```

| Campo | Regla |
|---|---|
| Prefijo | `DACORA` (insensible a mayúsculas). Sin prefijo → se ingiere como texto libre |
| `CÓDIGO` | uno de la tabla; desconocido → se clasifica por el texto |
| `LUGAR` | nombre de barrio/referencia del gazetteer sin espacios o con `_` (`MILAN`, `LA_ENEA`, `AV_SANTANDER`) **o** `lat,lon` decimal (`5.0561,-75.4842`) |
| `N_PERSONAS` | entero ≥ 0; si falta o no es número, se trata como parte del texto |
| texto libre | resto del mensaje; se redacta |
| Longitud | ≤ 160 caracteres; si excede, se procesa igual, `sin_clasificar` + revisión |

| Código | Categoría |
|---|---|
| ATR | personas_atrapadas |
| HER | heridos |
| COL | colapso_estructura |
| DAN | dano_estructural |
| INC | incendio |
| GAS | fuga_gas |
| DES | deslizamiento |
| VIA | via_bloqueada |
| SER | servicios_caidos |
| ALB | necesidad_albergue |
| AYU | necesidad_ayuda |
| DSP | persona_desaparecida |

Resultado de precisión geográfica: `lat,lon` → `gps`; lugar reconocido → `barrio`;
lugar no reconocido → `none`.

Ejemplos:

| SMS | Resultado esperado |
|---|---|
| `DACORA ATR MILAN 3 edificio caido cra 23` | personas_atrapadas, crítico, Milán (barrio), 3 personas |
| `dacora gas 5.0689,-75.5174 0 huele mucho a gas` | fuga_gas, crítico, gps, 0 personas |
| `DACORA XYZ CHIPRE se cayo una pared` | código desconocido → por texto: dano_estructural, Chipre |
| `ayuda en la enea` | sin prefijo → texto libre; necesidad_ayuda; La Enea por gazetteer |

El número del remitente solo se usa para calcular `reporter_hash` (nunca se guarda).
