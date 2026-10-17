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

const SUGGESTED_PROMPTS = ["What does hope mean?", "Translate good morning", "Laisiangtho John 1"];

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
    setMessages((previous) => [...previous, { id: `u${Date.now()}`, role: "user", text }]);
    setInput("");
    setPending(true);
    setError(null);
    try {
      const data = await askSiamsil(text);
      setMessages((previous) => [...previous, {
        id: `a${Date.now()}`,
        role: "assistant",
        text: data.answer,
        confidence: data.confidence,
        note: data.note,
      }]);
    } catch {
      setError("Siamsil AI could not reach the language engine.");
    } finally {
      setPending(false);
      requestAnimationFrame(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }));
    }
  }

  return (
    <div className="chat-page">
      <div className="chat-shell">
        <header className="chat-intro">
          <span className="chat-kicker">Siamsil · Language tools</span>
          <h1 className="font-playfair">Ask Siamsil AI.</h1>
          <p>Explore words, phrases, and scripture through answers grounded in Siamsil’s sources.</p>
          <span className="chat-mode">Retrieval assistant · no generated Zomi</span>
        </header>

        <section className="chat-panel" aria-label="Siamsil AI conversation">
          <div className="chat-panel-head"><span className="chat-panel-icon"><IconChat size={17} /></span><div><strong>Language assistant</strong><span>Source-based answers</span></div></div>
          {messages.length === 0 && (
            <div className="chat-start">
              <span className="chat-start-icon"><IconChat size={25} /></span>
              <h2 className="font-playfair">What would you like to explore?</h2>
              <p>Ask for a word, phrase, or verse. Responses come from the dictionary, reviewed phrases, Bible text, or labeled corpus examples.</p>
              <div className="chat-prompts" aria-label="Suggested questions">
                {SUGGESTED_PROMPTS.map((prompt) => <button key={prompt} type="button" onClick={() => setInput(prompt)}>{prompt} <IconArrow size={13} /></button>)}
              </div>
            </div>
          )}

          {messages.length > 0 && (
            <div className="chat-thread" role="log" aria-live="polite">
              {messages.map((message) => (
                <div className={`chat-message-row ${message.role}`} key={message.id}>
                  <div className="chat-message">
                    {message.role === "assistant" && <span className="chat-message-source"><IconChat size={13} /> {message.confidence ?? "retrieval"}</span>}
                    <p>{message.text}</p>
                    {message.note && <small>{message.note}</small>}
                  </div>
                </div>
              ))}
              {pending && <div className="chat-pending" role="status">Checking Siamsil’s sources…</div>}
              <div ref={bottomRef} />
            </div>
          )}

          {error && <p className="chat-error" role="alert">{error}</p>}

          <form className="chat-composer" onSubmit={handleSend}>
            <label className="sr-only" htmlFor="chat-question">Ask a question</label>
            <input id="chat-question" value={input} onChange={(event) => setInput(event.target.value)} placeholder="Ask about a Zomi word, phrase, or verse…" />
            <button type="submit" disabled={!input.trim() || pending} aria-label="Send question"><IconArrow size={17} /></button>
          </form>
        </section>
      </div>
    </div>
  );
}
