FROM node:20-slim AS build
WORKDIR /web
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
