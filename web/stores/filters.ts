import { defineStore } from "pinia";

export const useFilters = defineStore("filters", {
  state: () => ({
    date_from: null as number | null,
    date_to: null as number | null,
    client: "" as string,
    service: "" as string,
    user: "" as string,
    meta: { clients: [], services: [], users: [], months: [] } as any,
  }),
  getters: {
    // strip empty values -> query params object
    params(state): Record<string, any> {
      const p: Record<string, any> = {};
      for (const k of ["date_from", "date_to", "client", "service", "user"] as const) {
        const v = (state as any)[k];
        if (v !== null && v !== "" && v !== undefined) p[k] = v;
      }
      return p;
    },
  },
  actions: {
    reset() {
      this.date_from = null; this.date_to = null;
      this.client = ""; this.service = ""; this.user = "";
    },
  },
});
