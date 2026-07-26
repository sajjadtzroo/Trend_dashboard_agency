export default defineNuxtConfig({
  compatibilityDate: "2025-01-01",
  // SPA: all API calls run in the browser (where localhost:8000 = the API).
  // Avoids SSR fetching the API from inside the web container.
  ssr: false,
  modules: ["@pinia/nuxt"],
  css: ["~/assets/main.css"],
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || "http://localhost:8000",
    },
  },
  app: {
    head: {
      htmlAttrs: { lang: "fa-IR" },
      title: "Creative Lab — Finance Dashboard",
      meta: [{ name: "viewport", content: "width=device-width, initial-scale=1" }],
    },
  },
});
