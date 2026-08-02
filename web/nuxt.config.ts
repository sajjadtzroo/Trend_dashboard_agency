export default defineNuxtConfig({
  compatibilityDate: "2025-01-01",
  // SPA: all API calls run in the browser (where localhost:8000 = the API).
  // Avoids SSR fetching the API from inside the web container.
  ssr: false,
  modules: ["@pinia/nuxt"],
  css: ["~/assets/main.css"],
  runtimeConfig: {
    public: {
      // Prod (single-origin): "/api" — the Nitro proxy below forwards to the API.
      // Local/direct: full URL to the API. Baked at build (SPA).
      apiBase: process.env.NUXT_PUBLIC_API_BASE || "http://localhost:8000",
    },
  },
  // Same-origin API: browser hits /api/** on this app, Nitro proxies to the private
  // API app. Keeps auth cookies first-party so one liara.run subdomain is enough.
  // Dormant unless the frontend calls /api (i.e. apiBase="/api"). Target baked at build.
  nitro: {
    routeRules: {
      "/api/**": { proxy: `${process.env.NUXT_API_INTERNAL || "http://localhost:8000"}/**` },
    },
  },
  app: {
    head: {
      htmlAttrs: { lang: "fa-IR" },
      title: "Debrief — Finance Dashboard",
      meta: [{ name: "viewport", content: "width=device-width, initial-scale=1" }],
    },
  },
});
