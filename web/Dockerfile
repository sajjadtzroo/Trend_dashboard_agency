FROM node:20-slim AS build
WORKDIR /web
# SPA (ssr:false) bakes public runtimeConfig at build time, so the API base must
# be present when `npm run build` runs. Pass at deploy: --build-arg NUXT_PUBLIC_API_BASE=...
ARG NUXT_PUBLIC_API_BASE=http://localhost:8000
ARG NUXT_API_INTERNAL=http://localhost:8000
ENV NUXT_PUBLIC_API_BASE=$NUXT_PUBLIC_API_BASE
ENV NUXT_API_INTERNAL=$NUXT_API_INTERNAL
COPY package.json ./
# --legacy-peer-deps sidesteps an npm arborist bug on the nuxt dep tree
RUN npm install --legacy-peer-deps --no-audit --no-fund
COPY . .
RUN npm run build

FROM node:20-slim
WORKDIR /web
COPY --from=build /web/.output ./.output
ENV NUXT_PORT=3000 NUXT_HOST=0.0.0.0
EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
