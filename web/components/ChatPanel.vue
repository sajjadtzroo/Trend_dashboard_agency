<script setup lang="ts">
// Floating bilingual assistant. Every message bubble uses dir="auto" so Persian
// picks up RTL and English LTR from its own content; inline citations/SQL are
// wrapped in <bdi> so numbers and Latin tokens don't scramble mixed text (plan §5.5).
const open = ref(false);
const draft = ref("");
const { messages, streaming, send } = useChat();
const scroller = ref<HTMLElement | null>(null);

async function submit() {
  const t = draft.value;
  draft.value = "";
  await send(t);
}
watch(messages, async () => {
  await nextTick();
  scroller.value?.scrollTo({ top: scroller.value.scrollHeight });
}, { deep: true });
</script>

<template>
  <div class="chat">
    <button v-if="!open" class="fab" @click="open = true" aria-label="Open assistant">
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor"
        stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    </button>

    <div v-else class="panel">
      <header>
        <span>Assistant</span>
        <button class="x" @click="open = false" aria-label="Close">✕</button>
      </header>

      <div ref="scroller" class="log">
        <p v-if="!messages.length" class="hint">
          Ask about finances or documents — Persian or English. مثلاً: «درآمد سه‌ماهه اول ۱۴۰۴؟»
        </p>
        <div v-for="(m, i) in messages" :key="i" class="turn" :class="m.role">
          <div class="bubble" dir="auto">{{ m.text }}<span v-if="streaming && m.role === 'assistant' && i === messages.length - 1" class="caret">▍</span></div>
          <ul v-if="m.citations.length" class="cites">
            <li v-for="(c, ci) in m.citations" :key="ci">
              <bdi v-if="c.sql"><code>{{ c.sql }}</code></bdi>
              <bdi v-else>[{{ c.n }}] {{ c.title || c.source }}</bdi>
            </li>
          </ul>
        </div>
      </div>

      <form class="entry" @submit.prevent="submit">
        <input v-model="draft" dir="auto" :disabled="streaming"
          placeholder="Ask a question…" />
        <button type="submit" :disabled="streaming || !draft.trim()">→</button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.chat { position: fixed; bottom: 20px; right: 20px; z-index: 50; }
.fab {
  width: 52px; height: 52px; border-radius: 50%; border: none; cursor: pointer;
  background: #16a34a; color: #fff; display: grid; place-items: center;
  box-shadow: 0 6px 20px rgba(22, 163, 74, 0.35);
}
.panel {
  width: 360px; max-width: calc(100vw - 40px); height: 520px; max-height: calc(100vh - 40px);
  display: flex; flex-direction: column; background: #fff; border: 1px solid #e5e7eb;
  border-radius: 14px; box-shadow: 0 12px 40px rgba(0, 0, 0, 0.18); overflow: hidden;
}
header { display: flex; justify-content: space-between; align-items: center;
  padding: 12px 14px; background: #16a34a; color: #fff; font-weight: 600; }
.x { background: none; border: none; color: #fff; cursor: pointer; font-size: 15px; }
.log { flex: 1; overflow-y: auto; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
.hint { color: #6b7280; font-size: 13px; line-height: 1.6; }
.turn { display: flex; flex-direction: column; gap: 4px; max-width: 90%; }
.turn.user { align-self: flex-end; align-items: flex-end; }
.turn.assistant { align-self: flex-start; }
.bubble { padding: 9px 12px; border-radius: 12px; font-size: 14px; line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
.user .bubble { background: #16a34a; color: #fff; }
.assistant .bubble { background: #f3f4f6; color: #111827; }
.caret { opacity: 0.5; animation: blink 1s steps(2) infinite; }
@keyframes blink { 50% { opacity: 0; } }
.cites { list-style: none; margin: 0; padding: 0 4px; display: flex; flex-direction: column; gap: 3px; }
.cites li { font-size: 11px; color: #6b7280; }
.cites code { font-size: 10.5px; background: #f9fafb; padding: 1px 4px; border-radius: 4px; white-space: pre-wrap; }
.entry { display: flex; gap: 6px; padding: 10px; border-top: 1px solid #eef0f2; }
.entry input { flex: 1; padding: 9px 11px; border: 1px solid #d1d5db; border-radius: 9px; font-size: 14px; outline: none; }
.entry input:focus { border-color: #16a34a; }
.entry button { width: 40px; border: none; border-radius: 9px; background: #16a34a; color: #fff; cursor: pointer; font-size: 16px; }
.entry button:disabled { opacity: 0.5; cursor: default; }
</style>
