// Rehydrate the session from the HttpOnly cookie before the first route renders,
// so global middleware sees the real auth state on a hard refresh.
export default defineNuxtPlugin(async () => {
  await useAuthStore().fetchMe();
});
