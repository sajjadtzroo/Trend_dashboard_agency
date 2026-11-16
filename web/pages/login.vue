<script setup lang="ts">
definePageMeta({ layout: false });
const auth = useAuthStore();
const route = useRoute();

const username = ref("");
const password = ref("");
const error = ref("");
const busy = ref(false);

async function submit() {
  error.value = "";
  busy.value = true;
  try {
    await auth.login(username.value, password.value);
    await navigateTo((route.query.redirect as string) || "/");
  } catch (e: any) {
    const s = e?.response?.status;
    error.value = s === 429 ? "Too many attempts. Please wait a few minutes."
      : s === 401 ? "Invalid username or password."
      : `Server unavailable (${s ?? "network error"}). Try again shortly.`;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="login-wrap">
    <form class="login-card panel" @submit.prevent="submit">
      <div class="login-brand">
        <img src="/debrief.svg" alt="Debrief" class="login-logo" />
        <p class="muted">Finance Dashboard · IRR</p>
      </div>

      <label class="fld">Username
        <input v-model="username" type="text" autocomplete="username" required autofocus />
      </label>
      <label class="fld">Password
        <input v-model="password" type="password" autocomplete="current-password" required />
      </label>

      <p v-if="error" class="login-error" role="alert">{{ error }}</p>

      <button class="login-btn" type="submit" :disabled="busy || !username || !password">
        {{ busy ? "Signing in…" : "Sign in" }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.login-wrap{min-height:100vh;display:grid;place-items:center;padding:24px;
  background:radial-gradient(70% 50% at 50% 0%, var(--wash) 0%, rgba(250,250,250,0) 60%), var(--bg)}
.login-card{width:100%;max-width:380px;display:flex;flex-direction:column;gap:16px;margin:0}
.login-brand{display:flex;flex-direction:column;align-items:flex-start;gap:6px;margin-bottom:8px}
.login-logo{height:34px;width:auto}
.login-brand p{margin:0;font-size:12px}
.fld{display:flex;flex-direction:column;gap:6px;font-size:12px;color:var(--muted)}
.fld input{padding:10px 12px;border:1px solid var(--border);border-radius:var(--radius-sm);background:#fff;
  color:var(--text);font-size:14px}
.fld input:focus-visible{outline:2px solid var(--primary);outline-offset:1px}
.login-error{margin:0;color:var(--danger);font-size:13px}
.login-btn{padding:11px 16px;border:none;border-radius:var(--radius-sm);background:var(--primary);color:#fff;
  font-weight:600;font-size:14px;cursor:pointer;transition:opacity .15s ease}
.login-btn:disabled{opacity:.55;cursor:not-allowed}
</style>
