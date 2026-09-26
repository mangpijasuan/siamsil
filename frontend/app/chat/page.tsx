"use client";

import { FormEvent, useRef, useState } from "react";
import { askSiamsil } from "@/lib/api";
import { IconArrow, IconChat } from "@/components/Icons";

type Message = {
  id: string;
  role: "user" | "assistant";
  text: string;
  confidence?: string;
  note?: string;
};

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  async function handleSend(event: FormEvent) {
    event.preventDefault();
    const text = input.trim();
    if (!text || pending) return;
    const userMsg: Message = { id: `u${Date.now()}`, role: "user", text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setPending(true);
    setError(null);
    try {
      const data = await askSiamsil(text);
      setMessages((prev) => [
        ...prev,
        {
          id: `a${Date.now()}`,
          role: "assistant",
          text: data.answer,
          confidence: data.confidence,
          note: data.note,
        },
      ]);
    } catch {
      setError("Siamsil AI could not reach the language engine.");
    } finally {
      setPending(false);
      requestAnimationFrame(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }));
    }
  }

  return (
    <>
      <header className="page-header page-header-compact" style={{ paddingBottom: 16 }}>
        <div className="font-playfair" style={{ color: "#fff", fontSize: 18, fontWeight: 700 }}>Siamsil AI</div>
        <div style={{ color: "var(--gold2)", fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", marginTop: 4 }}>
          Retrieval assistant · no generated Zomi
        </div>
      </header>

      <div style={{ display: "flex", flexDirection: "column", minHeight: "calc(100vh - 160px)" }}>
        <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--border)", background: "var(--white)", display: "flex", gap: 6, flexWrap: "wrap" }}>
          {["What does hope mean?", "Translate good morning", "Laisiangtho John 1"].map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => setInput(prompt)}
              style={{
                border: "1px solid var(--border)", background: "var(--white)", borderRadius: 20,
                padding: "5px 12px", fontSize: 11, fontWeight: 600, color: "var(--navy)", cursor: "pointer",
              }}
            >
              {prompt}
            </button>
          ))}
        </div>

        <div style={{ flex: 1, overflowY: "auto", padding: "16px 0 12px", display: "flex", flexDirection: "column", gap: 10 }}>
          {messages.length === 0 && (
            <div style={{ padding: "32px 20px", textAlign: "center", color: "var(--gray)", fontSize: 13, lineHeight: 1.6 }}>
              Ask for a word, phrase, or verse. Answers come only from Siamsil dictionary, reviewed phrases, the Bible, or unverified corpus examples.
            </div>
          )}
          {messages.map((msg) => (
            <div key={msg.id} style={{ display: "flex", justifyContent: msg.role === "user" ? "flex-end" : "flex-start", padding: "0 16px" }}>
              <div style={{
                maxWidth: "80%",
                background: msg.role === "user" ? "var(--navy)" : "var(--white)",
                color: msg.role === "user" ? "var(--white)" : "var(--text)",
                border: msg.role === "user" ? "none" : "1px solid var(--border)",
                borderRadius: 16,
                padding: "11px 15px",
                fontSize: 14,
                lineHeight: 1.65,
              }}>
                {msg.role === "assistant" && (
                  <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6, color: "var(--gold)" }}>
                    <IconChat size={14} />
                    <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase" }}>
                      {msg.confidence ?? "retrieval"}
                    </span>
                  </div>
                )}
                {msg.text}
                {msg.note && (
                  <div style={{ marginTop: 8, fontSize: 11, color: "var(--gray)" }}>{msg.note}</div>
                )}
              </div>
            </div>
          ))}
          {error && <div style={{ margin: "0 16px", color: "#B91C1C", fontSize: 13 }}>{error}</div>}
          <div ref={bottomRef} />
        </div>

        <form onSubmit={handleSend} style={{ borderTop: "1px solid var(--border)", background: "var(--white)", padding: "10px 14px", display: "flex", gap: 10 }}>
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask about a Zomi word, phrase, or verse…"
            style={{
              flex: 1, border: "1px solid var(--border)", borderRadius: 24,
              padding: "10px 16px", fontSize: 14, fontFamily: "inherit",
              background: "var(--cream)", outline: "none", color: "var(--text)",
            }}
          />
          <button type="submit" disabled={!input.trim() || pending} aria-label="Send" style={{
            width: 38, height: 38, borderRadius: "50%", border: "none",
            background: "var(--navy)", color: "var(--gold)", cursor: "pointer",
          }}>
            <IconArrow size={16} />
          </button>
        </form>
      </div>
    </>
  );
}
