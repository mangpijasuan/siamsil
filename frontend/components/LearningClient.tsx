"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { LearningEntry } from "@/lib/api";

type Props = { groups: Record<string, LearningEntry[]>; error: string | null };

const CATEGORIES = [
  { key: "Alphabet",    icon: "🔤", label: "Alphabet",       desc: "Letters & tones" },
  { key: "Phrases",     icon: "🗣️", label: "Phrases",        desc: "Common expressions" },
  { key: "Grammar",     icon: "📖", label: "Grammar",        desc: "Verb tones & sentences" },
  { key: "Songs",       icon: "🎵", label: "Songs & Hymns",  desc: "Traditional Zomi songs" },
];

export default function LearningClient({ groups, error }: Props) {
  const [streak, setStreak] = useState(0);
  const [xp, setXp] = useState(0);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      setStreak(Number(localStorage.getItem("siamsil_streak") ?? 0));
      setXp(Number(localStorage.getItem("siamsil_xp") ?? 0));
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const allCategories = Object.keys(groups);
  const activeGroup = activeCategory ? (groups[activeCategory] ?? []) : [];
  const xpMax = 500;
  const xpPct = Math.min((xp / xpMax) * 100, 100);

  return (
    <>
      {/* ── Header ── */}
      <header className="page-header">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 }}>
          <span className="font-playfair" style={{ color: "var(--white)", fontSize: 20, fontWeight: 700 }}>Learning Hub</span>
          <span style={{ fontSize: 20 }}>🔥</span>
        </div>

        {/* Streak + XP */}
        <div style={{ background: "rgba(255,255,255,0.1)", borderRadius: 12, padding: "12px 14px", display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ textAlign: "center" }}>
            <div className="font-playfair" style={{ color: "var(--gold)", fontSize: 22, fontWeight: 700 }}>{streak}</div>
            <div style={{ color: "rgba(255,255,255,0.5)", fontSize: 9, fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase" }}>Day Streak</div>
          </div>
          <div style={{ width: 1, height: 36, background: "rgba(255,255,255,0.15)" }} />
          <div style={{ flex: 1 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
              <span style={{ color: "rgba(255,255,255,0.7)", fontSize: 10 }}>Daily XP</span>
              <span style={{ color: "var(--gold)", fontSize: 10, fontWeight: 700 }}>{xp} / {xpMax}</span>
            </div>
            <div className="progress-bar-bg">
              <div className="progress-bar-fill" style={{ width: `${xpPct}%` }} />
            </div>
          </div>
        </div>
      </header>

      {/* ── Continue card ── */}
      <div style={{ margin: "-18px 16px 12px", background: "linear-gradient(135deg,var(--navy2),var(--navy))", borderRadius: 16, padding: 16, boxShadow: "0 4px 20px rgba(27,42,74,0.2)" }}>
        <div className="gold-label" style={{ marginBottom: 8 }}>Continue Learning</div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 32 }}>📝</span>
          <div style={{ flex: 1 }}>
            <div className="font-playfair" style={{ color: "var(--white)", fontSize: 15, fontWeight: 700, marginBottom: 3 }}>Reviewed phrases</div>
            <div style={{ color: "rgba(255,255,255,0.5)", fontSize: 11 }}>Only teacher-checked daily-use items are published</div>
          </div>
        </div>
      </div>

      {error && (
        <div style={{ margin: "0 16px 12px", padding: "12px 16px", borderRadius: 12, background: "#FEE2E2", color: "#B91C1C", fontSize: 13 }}>{error}</div>
      )}

      {/* ── Category view ── */}
      {activeCategory ? (
        <>
          <div className="section-header">
            <span className="section-title">{activeCategory}</span>
            <button onClick={() => setActiveCategory(null)} className="section-link" style={{ background: "none", border: "none" }}>← Back</button>
          </div>
          <div style={{ padding: "0 16px", display: "flex", flexDirection: "column", gap: 8 }}>
            {activeGroup.map(entry => (
              <div key={entry.id} style={{ background: "var(--white)", borderRadius: 12, overflow: "hidden", display: "grid", gridTemplateColumns: "1fr 1fr" }}>
                <div style={{ padding: "12px 14px", borderRight: "1px solid var(--gray2)" }}>
                  {entry.sub_category && <div style={{ fontSize: 9, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--gray)", marginBottom: 4 }}>{entry.sub_category}</div>}
                  <p style={{ fontSize: 13, lineHeight: 1.5, color: "var(--navy)", margin: 0 }}>{entry.english}</p>
                </div>
                <div style={{ padding: "12px 14px", background: "rgba(201,168,76,0.06)" }}>
                  <p style={{ fontSize: 13, lineHeight: 1.5, color: "var(--navy)", margin: 0 }}>{entry.zomi}</p>
                  {entry.notes && <p style={{ fontSize: 11, color: "var(--gray)", marginTop: 4 }}>{entry.notes}</p>}
                </div>
              </div>
            ))}
          </div>
        </>
      ) : (
        <>
          <div className="section-header">
            <span className="section-title">Categories</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, padding: "0 16px" }}>
            <Link href="/learning/citizenship" className="citizenship-learning-card">
              <span className="citizenship-learning-flag" aria-hidden="true">🇺🇸</span>
              <span className="citizenship-learning-copy">
                <span className="gold-label">10-question preview</span>
                <span className="font-playfair citizenship-learning-title">U.S. Citizenship Test</span>
                <span className="citizenship-learning-desc">Study government, history, rights, and responsibilities.</span>
              </span>
              <span className="citizenship-learning-action">Start →</span>
            </Link>

            {CATEGORIES.map(cat => {
              const count = (groups[cat.key] ?? []).length;
              return (
                <button key={cat.key} className="cat-card" style={{ textAlign: "left", background: "var(--white)", border: "1px solid var(--gray2)", cursor: "pointer" }} onClick={() => setActiveCategory(cat.key)}>
                  <div style={{ fontSize: 24, marginBottom: 8 }}>{cat.icon}</div>
                  <div className="font-playfair" style={{ fontSize: 13, fontWeight: 700, color: "var(--navy)", marginBottom: 3 }}>{cat.label}</div>
                  <div style={{ fontSize: 10, color: "var(--gray)" }}>{count > 0 ? `${count} phrases` : cat.desc}</div>
                </button>
              );
            })}

            {/* API categories */}
            {allCategories.filter(k => !CATEGORIES.find(c => c.key === k)).map(cat => (
              <button key={cat} className="cat-card" style={{ textAlign: "left", background: "var(--white)", border: "1px solid var(--gray2)", cursor: "pointer" }} onClick={() => setActiveCategory(cat)}>
                <div style={{ fontSize: 24, marginBottom: 8 }}>📚</div>
                <div className="font-playfair" style={{ fontSize: 13, fontWeight: 700, color: "var(--navy)", marginBottom: 3 }}>{cat}</div>
                <div style={{ fontSize: 10, color: "var(--gray)" }}>{groups[cat].length} phrases</div>
              </button>
            ))}

            {/* Coming soon */}
            <div style={{ gridColumn: "span 2", background: "var(--navy)", borderRadius: 14, padding: 14, display: "flex", alignItems: "center", gap: 14 }}>
              <span style={{ fontSize: 28 }}>📜</span>
              <div>
                <div className="font-playfair" style={{ fontSize: 14, fontWeight: 700, color: "white", marginBottom: 3 }}>Zomi History & Culture</div>
                <div style={{ fontSize: 10, color: "rgba(255,255,255,0.5)" }}>Stories, proverbs, and heritage</div>
              </div>
              <div style={{ marginLeft: "auto", background: "rgba(255,255,255,0.1)", padding: "6px 12px", borderRadius: 20, fontSize: 10, color: "var(--gold)", fontWeight: 600 }}>Planned</div>
            </div>
          </div>
        </>
      )}

      <div className="screen-pad" />
    </>
  );
}
