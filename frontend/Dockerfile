# Frontend FrameForge — React 19 + craco, servito da nginx
#
# ATTENZIONE: REACT_APP_BACKEND_URL viene sostituita dentro il bundle durante
# la compilazione, non letta a runtime. Cambiarla richiede una nuova build:
# non basta riavviare il container con un'altra variabile.
#
# Build:
#   docker build -t forgefps-frontend \
#     --build-arg REACT_APP_BACKEND_URL=https://forgefps.dev ./frontend

# ---------- stage 1: build ----------
FROM node:20-alpine AS builder

WORKDIR /srv/app

# Nel repository non e' presente nessun lockfile (ne' yarn.lock ne'
# package-lock.json), quindi le versioni transitive vengono risolte a ogni
# build: due build a distanza di tempo possono non essere identiche.
# Conviene generare un lockfile e committarlo; da quel momento sostituire la
# riga sotto con `yarn install --frozen-lockfile`.
COPY package.json ./
RUN yarn install --network-timeout 600000

COPY . .

ARG REACT_APP_BACKEND_URL
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL

# create-react-app tratta i warning come errori quando CI=true, cosa che molte
# piattaforme impostano da sole: un warning di lint farebbe fallire il deploy.
# Impostarla a false esplicitamente rende la build indipendente dall'host.
ENV CI=false

RUN if [ -z "$REACT_APP_BACKEND_URL" ]; then \
        echo "ERRORE: REACT_APP_BACKEND_URL non passata come --build-arg." >&2; \
        echo "Il bundle finirebbe con l'URL del backend vuoto e l'app non" >&2; \
        echo "riuscirebbe a fare nessuna chiamata API." >&2; \
        exit 1; \
    fi \
    && yarn build

# ---------- stage 2: runtime ----------
FROM nginx:1.27-alpine

COPY --from=builder /srv/app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1/ || exit 1
