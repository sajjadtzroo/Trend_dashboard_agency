import { defineStore } from "pinia";

type User = { id: number; username: string };

export const useAuthStore = defineStore("auth", {
  state: () => ({ user: null as User | null }),
  getters: {
    isAuthed: (s) => !!s.user,
  },
  actions: {
    async login(username: string, password: string) {
      this.user = await apiFetch<User>("/auth/login", { method: "POST", body: { username, password } });
    },
    // Rehydrate from the HttpOnly cookie on app load (SPA loses memory on refresh).
    async fetchMe() {
      try { this.user = await apiFetch<User>("/auth/me"); }
      catch { this.user = null; }
    },
    async logout(all = false) {
      try { await apiFetch(`/auth/logout${all ? "?all=1" : ""}`, { method: "POST" }); }
      finally { this.user = null; await navigateTo("/login"); }
    },
  },
});
