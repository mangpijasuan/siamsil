"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

type Song = { id: string; title: string; lyrics: string; number?: string | number; author?: string; source?: string };
type SongsResponse = { songs: Song[] };

export default function SongsClient() {
  const [songs, setSongs] = useState<Song[]>([]);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "unavailable">("loading");
  const [fontSize, setFontSize] = useState(19);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/songs", { signal: controller.signal, cache: "no-store" })
      .then(async response => {
        if (!response.ok) throw new Error("Song catalog unavailable");
        return response.json() as Promise<SongsResponse>;
      })
      .then(data => {
        if (!Array.isArray(data.songs)) throw new Error("Invalid song catalog");
        setSongs(data.songs.filter(song => typeof song.id === "string" && typeof song.title === "string" && typeof song.lyrics === "string"));
        setStatus("ready");
      })
      .catch(() => { if (!controller.signal.aborted) setStatus("unavailable"); });
    return () => controller.abort();
  }, []);

  const filtered = useMemo(() => songs.filter(song =>
    [song.title, song.number, song.author, song.lyrics].some(value => String(value ?? "").toLowerCase().includes(query.trim().toLowerCase()))
  ), [songs, query]);
  const active = songs.find(song => song.id === selected);

  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: "32px 20px 100px", color: "var(--navy)" }}>
      <Link href="/library" style={{ color: "var(--navy)", fontSize: 14 }}>← Zomi Library</Link>
      <header style={{ margin: "28px 0", padding: 28, borderRadius: 20, background: "linear-gradient(125deg,#14233e,#243d60)", color: "white" }}>
        <p style={{ color: "#d5b66c", fontWeight: 700, letterSpacing: 2, fontSize: 12 }}>SIAMSIL LIBRARY · FREE</p>
        <h1 className="font-playfair" style={{ fontSize: "clamp(28px,5vw,42px)", margin: "10px 0" }}>Zomi Songs & Hymns</h1>
        <p style={{ opacity: .8 }}>La leh Phatna Late — preserve and read Zomi worship songs.</p>
      </header>
      {active ? (
        <article style={{ background: "var(--surface)", borderRadius: 18, padding: "24px 22px" }}>
          <button type="button" onClick={() => setSelected(null)} style={{ marginBottom: 20 }}>← All songs</button>
          <h2 className="font-playfair" style={{ fontSize: 28 }}>{active.title}</h2>
          <p style={{ opacity: .7, margin: "8px 0 20px" }}>{[active.number && `No. ${active.number}`, active.author].filter(Boolean).join(" · ")}</p>
          <div style={{ display: "flex", gap: 12, marginBottom: 22 }}>
            <button type="button" onClick={() => setFontSize(n => Math.max(15, n - 2))} aria-label="Decrease lyrics font size">A−</button>
            <button type="button" onClick={() => setFontSize(n => Math.min(32, n + 2))} aria-label="Increase lyrics font size">A+</button>
          </div>
          <div style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", lineHeight: 1.95, fontSize }}>{active.lyrics}</div>
          {active.source && <p style={{ opacity: .65, marginTop: 32, fontSize: 12 }}>Source: {active.source}</p>}
        </article>
      ) : (
        <section>
          <label htmlFor="song-search" style={{ display: "block", fontWeight: 600, marginBottom: 8 }}>Search songs</label>
          <input id="song-search" type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Song title, number, or lyrics…" style={{ width: "100%", padding: 15, border: "1px solid #b5bdc8", borderRadius: 12, background: "var(--surface)", color: "var(--navy)" }} />
          {status === "loading" && <p role="status" style={{ marginTop: 24 }}>Loading song catalog…</p>}
          {status === "unavailable" && <p role="status" style={{ marginTop: 24 }}>The song catalog is not connected yet. Please try again later.</p>}
          {status === "ready" && <p style={{ margin: "18px 0" }}>{filtered.length} songs</p>}
          {status === "ready" && songs.length === 0 && <p>Song lyrics are awaiting import from the authorized songbook.</p>}
          <div style={{ display: "grid", gap: 10 }}>
            {filtered.map(song => (
              <button key={song.id} type="button" onClick={() => setSelected(song.id)} style={{ textAlign: "left", background: "var(--surface)", color: "var(--navy)", border: "1px solid #d7dce3", borderRadius: 12, padding: 18, cursor: "pointer" }}>
                <strong>{song.number ? `${song.number}. ` : ""}{song.title}</strong>
                {song.author && <div style={{ fontSize: 13, opacity: .65, marginTop: 5 }}>{song.author}</div>}
              </button>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
