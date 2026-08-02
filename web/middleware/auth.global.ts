// UX gate only — real access control is enforced by FastAPI (get_current_user).
export default defineNuxtRouteMiddleware((to) => {
  const auth = useAuthStore();
  if (to.path === "/login") {
    if (auth.isAuthed) return navigateTo("/");
    return;
  }
  if (!auth.isAuthed) return navigateTo(`/login?redirect=${encodeURIComponent(to.fullPath)}`);
});
