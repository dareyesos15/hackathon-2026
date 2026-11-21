#!/usr/bin/env bash
# Prepara la pasarela SMS de Dacora con un celular Android por USB, en macOS o Linux.
# Equivalente de scripts/preparar_pasarela_sms.ps1 (Windows). Guía: docs/pasarela_sms.md.
#
# Uso, desde la raíz del repositorio:
#   bash scripts/preparar_pasarela_sms.sh [usuario] [clave]
#
# Hace, en orden: verifica Docker, crea la clave de firma en .env si falta (y la muestra para
# escribirla en el celular), reconstruye la API, comprueba la pasarela, instala adb si falta
# (Homebrew en macOS), espera el celular por USB y lo conecta. Se puede repetir sin problema.
# Variables opcionales: ADB (ruta a adb), ESPERA_S (segundos esperando el celular, 120).

set -uo pipefail

USUARIO="${1:-}"
CLAVE="${2:-}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

paso() { printf '\n\033[36m[%s] %s\033[0m\n' "$1" "$2"; }
ok() { printf '    \033[32mOK\033[0m  %s\n' "$1"; }
falla() { printf '    \033[31m!!\033[0m  %s\n' "$1"; exit 1; }

# 1. Docker ------------------------------------------------------------------------------------
paso 1 "Docker"
docker info >/dev/null 2>&1 || falla "Docker no responde: abra Docker Desktop y espere a que inicie."
# Proyecto de Compose de ESTE repositorio con más contenedores corriendo (la demo en uso).
# Se compara por el nombre de la carpeta (las rutas de Docker cambian de formato según el sistema).
PROYECTO="$(docker compose ls 2>/dev/null | awk -v carpeta="$(basename "$REPO")" '
  NR > 1 && index($0, carpeta) && index($0, "docker-compose.yml") && $2 ~ /^running/ {
    n = $2; gsub(/[^0-9]/, "", n); if (n + 0 > best) { best = n + 0; name = $1 }
  } END { print name }')"
PROYECTO="${PROYECTO:-dacora}"
ok "Docker activo · proyecto de Compose: $PROYECTO"

# 2. Clave de firma ----------------------------------------------------------------------------
paso 2 "Clave de firma de la pasarela (.env)"
CLAVE_FIRMA="$( [ -f .env ] && grep -E '^SMS_GATEWAY_SIGNING_KEY=.+' .env | head -1 | cut -d= -f2- | tr -d '[:space:]' || true)"
if [ -n "$CLAVE_FIRMA" ]; then
  ok "Ya existe una clave en .env"
else
  CLAVE_FIRMA="$(openssl rand -hex 16 2>/dev/null || od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
  if [ -f .env ]; then
    grep -v '^SMS_GATEWAY_SIGNING_KEY=' .env > .env.tmp || true
    mv .env.tmp .env
  fi
  echo "SMS_GATEWAY_SIGNING_KEY=$CLAVE_FIRMA" >> .env
  ok "Clave nueva creada en .env (no se sube a git)"
fi
printf '\n    \033[33mEscriba esta clave en el celular, en Ajustes > Webhooks > Signing Key (sin espacios):\033[0m\n'
printf '        \033[33m%s\033[0m\n' "$CLAVE_FIRMA"

# 3. API ---------------------------------------------------------------------------------------
paso 3 "API de Dacora con la pasarela"
docker compose -p "$PROYECTO" up -d --build api || falla "No se pudo levantar la API (docker compose)."
SANA=""
for _ in $(seq 1 40); do
  if curl -sf http://localhost:8000/api/v1/health >/dev/null; then SANA=1; break; fi
  sleep 3
done
[ -n "$SANA" ] || falla "La API no respondió en http://localhost:8000. Revise: docker compose -p $PROYECTO logs api"
CODIGO="$(curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8000/api/v1/ingest/sms-gateway \
  -H 'X-Timestamp: 1' -H 'X-Signature: x' -d '{}')"
case "$CODIGO" in
  401) ok "Pasarela activa y protegida por la clave" ;;
  503) falla "La API no tomó la clave. Revise que .env tenga SMS_GATEWAY_SIGNING_KEY y repita." ;;
  404) falla "Esta versión de la API no tiene la pasarela: actualice el repositorio (git pull)." ;;
  *) falla "Respuesta inesperada de la pasarela: HTTP $CODIGO" ;;
esac

# 4. adb ---------------------------------------------------------------------------------------
paso 4 "adb (Android Platform-Tools)"
ADB="${ADB:-$(command -v adb || true)}"
if [ -z "$ADB" ]; then
  if command -v brew >/dev/null 2>&1; then
    echo "    Instalando adb con Homebrew..."
    brew install --cask android-platform-tools >/dev/null || true
    ADB="$(command -v adb || true)"
  fi
fi
[ -n "$ADB" ] || falla "No hay adb. En macOS: brew install --cask android-platform-tools · en Linux: sudo apt install adb"
export PATH="$(dirname "$ADB"):$PATH"
ok "adb: $ADB"

# 5. Celular por USB ---------------------------------------------------------------------------
paso 5 "Celular conectado por USB con depuración USB"
echo "    Conecte el celular con un cable de datos y acepte 'Permitir depuración USB' en la pantalla."
ESPERA_S="${ESPERA_S:-120}"
LISTO=""
for i in $(seq 1 $((ESPERA_S / 2))); do
  ESTADO="$("$ADB" devices | tail -n +2)"
  if printf '%s\n' "$ESTADO" | grep -qE $'\tdevice$'; then LISTO=1; break; fi
  if printf '%s' "$ESTADO" | grep -q unauthorized && [ $((i % 5)) -eq 1 ]; then
    echo "    El celular pide autorización: acepte en su pantalla."
  fi
  sleep 2
done
[ -n "$LISTO" ] || falla "No se detectó el celular en $ESPERA_S s. Revise el cable y la depuración USB, y repita."
ok "Celular detectado"

# 6. Conectar la pasarela ----------------------------------------------------------------------
paso 6 "Conectar la app del celular con Dacora"
[ -n "$USUARIO" ] || read -r -p "    Usuario del 'Local Server' de la app: " USUARIO
[ -n "$CLAVE" ] || read -r -p "    Clave del 'Local Server' de la app: " CLAVE
if ! uv run --project services/api python scripts/conectar_pasarela_sms.py --usuario "$USUARIO" --clave "$CLAVE"; then
  printf '\n    \033[33mSi el registro automático falló, agregue el webhook a mano en la app:\033[0m\n'
  printf '      evento sms:received · URL http://127.0.0.1:9876/api/v1/ingest/sms-gateway\n'
  exit 1
fi

printf '\n\033[32mListo. Envíe un SMS al número de la SIM y mírelo en http://localhost:8080/pmu/\033[0m\n'
