# Servicio principal `web`: exportación estática de Next.js servida por Nginx.
# Nginx solo sirve archivos y hace proxy inverso de /api/ → api (sin lógica; principio X).
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# Marcas "SIMULADO" en la interfaz (principio IV): true en la demo, false con datos reales.
ARG NEXT_PUBLIC_DEMO_MODE=true
ENV NEXT_PUBLIC_DEMO_MODE=$NEXT_PUBLIC_DEMO_MODE
RUN npm run build

FROM nginx:1.27-alpine
# Certificado autofirmado para HTTPS (:8443): sin contexto seguro el celular no entrega el GPS.
# Es solo para la demo en red local; en producción va un certificado real.
RUN apk add --no-cache openssl  && mkdir -p /etc/nginx/certs  && openssl req -x509 -nodes -newkey rsa:2048 -days 825       -subj "/CN=dacora.local" -addext "subjectAltName=DNS:dacora.local,DNS:localhost"       -keyout /etc/nginx/certs/dacora.key -out /etc/nginx/certs/dacora.crt
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY nginx-locations.conf /etc/nginx/dacora-locations.conf
COPY --from=build /app/out /usr/share/nginx/html
EXPOSE 8080 8443
HEALTHCHECK --interval=5s --timeout=3s --retries=12 CMD wget -qO- http://127.0.0.1:8080/ >/dev/null || exit 1
