"use client";

import { useState } from "react";
import Link from "next/link";
import type { LearningEntry } from "@/lib/api";

type Props = { groups: Record<string, LearningEntry[]>; error: string | null };

const CATEGORY_ICONS: Record<string, string> = {
  Grammar: "📖",
  "Time Expressions": "🕰️",
  "Home & Furniture": "🏠",
  "Food & Kitchen": "🍽️",
};

export default function LearningClient({ groups, error }: Props) {
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const categories = Object.entries(groups).filter(([, entries]) => entries.length > 0);
  const total = categories.reduce((count, [, entries]) => count + entries.length, 0);
  const activeGroup = activeCategory ? groups[activeCategory] ?? [] : [];

  return (
    <div className="learning-root">
      <header className="learning-hero">
        <span className="learning-kicker">Siamsil · Learning</span>
        <h1 className="font-playfair">Learning Hub</h1>
        <p>Explore practical Zomi with phrases checked by a teacher. More courses are being prepared.</p>
        <div className="learning-count"><strong>{total}</strong><span>reviewed phrases available</span></div>
      </header>

      <div className="learning-content">
        {error && (
          <div className="learning-error" role="alert">
            {error} <a href="/learning">Retry</a>
          </div>
        )}

        {activeCategory ? (
          <>
            <div className="learning-section-heading">
              <div>
                <span className="learning-kicker">Reviewed collection</span>
                <h2 className="font-playfair">{activeCategory}</h2>
                <p>{activeGroup.length} phrases</p>
              </div>
              <button type="button" className="learning-back" onClick={() => setActiveCategory(null)}>← All categories</button>
            </div>
            <div className="learning-phrases">
              {activeGroup.map((entry) => (
                <article className="learning-pair" key={entry.id}>
                  <div>
                    <span>English</span>
                    <p>{entry.english}</p>
                  </div>
                  <div>
                    <span>Zomi</span>
                    <p>{entry.zomi}</p>
                    {entry.notes && <small>{entry.notes}</small>}
                  </div>
                </article>
              ))}
            </div>
          </>
        ) : (
          <>
            {categories.length > 0 && (
              <section className="learning-start" aria-label="Start learning">
                <div>
                  <span className="learning-kicker">Start with real content</span>
                  <h2 className="font-playfair">Reviewed Zomi phrases</h2>
                  <p>Begin with {categories[0][0]}, then browse the other available collections.</p>
                </div>
                <button type="button" onClick={() => setActiveCategory(categories[0][0])}>Start learning →</button>
              </section>
            )}

            <div className="learning-section-heading">
              <div>
                <span className="learning-kicker">Browse what is available</span>
                <h2 className="font-playfair">Collections</h2>
              </div>
            </div>
            <div className="learning-grid">
              <Link href="/learning/citizenship" className="learning-citizenship">
                <span aria-hidden="true">🇺🇸</span>
                <div>
                  <small>10-question preview · 3 languages</small>
                  <h3 className="font-playfair">U.S. Citizenship Test</h3>
                  <p>Study civics questions in English, Zomi, or Burmese.</p>
                </div>
                <b>Start →</b>
              </Link>
              {categories.map(([category, entries]) => (
                <button type="button" className="learning-category" key={category} onClick={() => setActiveCategory(category)}>
                  <span className="learning-category-icon" aria-hidden="true">{CATEGORY_ICONS[category] ?? "📚"}</span>
                  <span className="font-playfair learning-category-title">{category}</span>
                  <span>{entries.length} reviewed phrases</span>
                  <b aria-hidden="true">→</b>
                </button>
              ))}
            </div>
            {categories.length === 0 && !error && <p className="learning-empty">Reviewed phrase collections are not available yet. The citizenship preview is still open for study.</p>}
            <p className="learning-planned">Alphabet, songs, and broader courses are planned. They will appear here when reviewed content is ready.</p>
          </>
        )}
      </div>
    </div>
  );
}
