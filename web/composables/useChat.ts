// Chat client: POSTs to /chat and reads the SSE token/message/citation stream.
// Mirrors useApi.ts's apiBase usage; one thread_id per browser session.
type Citation = { n?: number; source?: string; title?: string; sql?: string };
type Msg = { role: "user" | "assistant"; text: string; citations: Citation[] };

export function useChat() {
  const cfg = useRuntimeConfig();
  const messages = useState<Msg[]>("chat-messages", () => []);
  const threadId = useState<string>("chat-thread", () => Math.random().toString(36).slice(2));
  const streaming = ref(false);

  async function send(text: string) {
    const q = text.trim();
    if (!q || streaming.value) return;
    messages.value.push({ role: "user", text: q, citations: [] });
    const asst = reactive<Msg>({ role: "assistant", text: "", citations: [] });
    messages.value.push(asst);
    streaming.value = true;
    try {
      const res = await fetch(`${cfg.public.apiBase}/chat`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ message: q, thread_id: threadId.value }),
      });
      if (!res.ok || !res.body) {
        asst.text = res.status === 429 ? "Too many requests — please slow down." : "Sorry, something went wrong.";
        return;
      }
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let i: number;
        while ((i = buf.indexOf("\n\n")) >= 0) {
          const line = buf.slice(0, i).trim();
          buf = buf.slice(i + 2);
          if (!line.startsWith("data:")) continue;
          const payload = line.slice(5).trim();
          if (payload === "[DONE]") continue;
          const ev = JSON.parse(payload);
          if (ev.token) asst.text += ev.token;         // data branch streams
          if (ev.message) asst.text = ev.message;      // doc branch: whole post-guard answer
          if (ev.citation) asst.citations.push(ev.citation);
          if (ev.error) asst.text = asst.text || "The assistant is temporarily unavailable.";
        }
      }
    } catch {
      asst.text = asst.text || "Sorry, something went wrong.";
    } finally {
      streaming.value = false;
    }
  }

  return { messages, streaming, send };
}
