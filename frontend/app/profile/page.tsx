"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { IconBook, IconSearch } from "@/components/Icons";
import { readHistory, useSavedWords } from "@/lib/localData";

export default function ProfilePage() {
  const { saved } = useSavedWords();
  const [history, setHistory] = useState<Array<{ kind: string; query: string; at: number }>>([]);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setHistory(readHistory()));
    return () => window.cancelAnimationFrame(frame);
  }, []);

  return (
    <>
      <header className="page-header page-header-compact">
        <div className="font-playfair" style={{ color: "var(--white)", fontSize: 20, fontWeight: 700 }}>Profile</div>
        <div style={{ color: "rgba(255,255,255,0.5)", fontSize: 12, marginTop: 4 }}>Saved on this device · Siamsil ID is not enabled yet</div>
      </header>

      <div style={{ padding: "16px 16px 40px", display: "flex", flexDirection: "column", gap: 14 }}>
        <div style={{ background: "var(--white)", borderRadius: "var(--radius-lg)", padding: 18, border: "1px solid var(--border)" }}>
          <div className="gold-label" style={{ marginBottom: 8 }}>Siamsil ID</div>
          <p className="font-playfair" style={{ fontSize: 18, color: "var(--navy)", margin: "0 0 8px" }}>Guest on this browser</p>
          <p style={{ fontSize: 13, color: "var(--gray)", margin: 0, lineHeight: 1.6 }}>
            Accounts, cloud sync, and sign-in with Apple/Google are not shipping in Release 1. Favorites and search history stay in this browser only.
          </p>
        </div>

        <div style={{ display: "flex", gap: 10 }}>
          <div style={{ flex: 1, background: "var(--white)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", padding: "14px 12px", textAlign: "center" }}>
            <div style={{ display: "flex", justifyContent: "center", color: "var(--navy)", marginBottom: 6 }}><IconBook size={16} /></div>
            <div className="font-playfair" style={{ fontSize: 20, fontWeight: 700, color: "var(--navy)" }}>{saved.length}</div>
            <div style={{ fontSize: 9, color: "var(--gray)", marginTop: 4, fontWeight: 600, textTransform: "uppercase" }}>Saved words</div>
          </div>
          <div style={{ flex: 1, background: "var(--white)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", padding: "14px 12px", textAlign: "center" }}>
            <div style={{ display: "flex", justifyContent: "center", color: "var(--navy)", marginBottom: 6 }}><IconSearch size={16} /></div>
            <div className="font-playfair" style={{ fontSize: 20, fontWeight: 700, color: "var(--navy)" }}>{history.length}</div>
            <div style={{ fontSize: 9, color: "var(--gray)", marginTop: 4, fontWeight: 600, textTransform: "uppercase" }}>Recent searches</div>
          </div>
        </div>

        <div style={{ background: "var(--white)", borderRadius: "var(--radius-lg)", border: "1px solid var(--border)", overflow: "hidden" }}>
          <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)" }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: "var(--navy)" }}>Saved words</span>
          </div>
          {saved.length === 0 && (
            <div style={{ padding: 16, fontSize: 13, color: "var(--gray)" }}>Save words from the dictionary. They are stored only on this device.</div>
          )}
          {saved.map((word) => (
            <Link key={word.id} href={`/zomidictionary?q=${encodeURIComponent(word.english)}`} style={{ padding: "12px 16px", borderTop: "1px solid var(--border)", display: "flex", textDecoration: "none" }}>
              <div style={{ flex: 1 }}>
                <div className="font-playfair" style={{ fontSize: 15, fontWeight: 700, color: "var(--navy)" }}>{word.english}</div>
                {word.zomi && <div style={{ fontSize: 12, color: "var(--gray)", marginTop: 2 }}>{word.zomi}</div>}
              </div>
            </Link>
          ))}
        </div>

        <div style={{ background: "var(--white)", borderRadius: "var(--radius-lg)", border: "1px solid var(--border)", overflow: "hidden" }}>
          <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)" }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: "var(--navy)" }}>Recent searches</span>
          </div>
          {history.length === 0 && (
            <div style={{ padding: 16, fontSize: 13, color: "var(--gray)" }}>Dictionary and translate lookups will appear here.</div>
          )}
          {history.slice(0, 12).map((item) => (
            <Link
              key={`${item.kind}-${item.at}`}
              href={item.kind === "translate" ? `/zomitranslate?q=${encodeURIComponent(item.query)}` : `/zomidictionary?q=${encodeURIComponent(item.query)}`}
              style={{ padding: "12px 16px", borderTop: "1px solid var(--border)", display: "block", textDecoration: "none" }}
            >
              <div style={{ fontSize: 13, color: "var(--navy)", fontWeight: 600 }}>{item.query}</div>
              <div style={{ fontSize: 11, color: "var(--gray)", marginTop: 2 }}>{item.kind}</div>
            </Link>
          ))}
        </div>
      </div>
    </>
  );
}
