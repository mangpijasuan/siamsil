"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { IconArrow, IconBook, IconCross, IconLibrary, IconSearch } from "./Icons";

type LibraryItem = {
  id: string;
  title: string;
  zomiTitle: string;
  description: string;
  category: "Scripture" | "Language" | "Culture";
  format: string;
  href?: string;
  accent: "navy" | "gold" | "sage" | "plum";
};

const LIBRARY_ITEMS: LibraryItem[] = [
  {
    id: "zomi-bible",
    title: "Zomi Holy Bible",
    zomiTitle: "Laisiangtho",
    description: "Read all 66 books with Zomi and English display options.",
    category: "Scripture",
    format: "Digital text",
    href: "/bible",
    accent: "navy",
  },
  {
    id: "dictionary",
    title: "Zomi–English Dictionary",
    zomiTitle: "Zomi Kamkhenna",
    description: "Search the 20k English–Zomi dictionary. Unreviewed entries are labeled.",
    category: "Language",
    format: "Reference",
    href: "/zomidictionary",
    accent: "gold",
  },
  {
    id: "learning",
    title: "Grammar & Daily Phrases",
    zomiTitle: "Zomi Pau Sinna",
    description: "Browse practical phrases, grammar notes, and learning collections.",
    category: "Language",
    format: "Learning collection",
    href: "/learning",
    accent: "sage",
  },
  {
    id: "proverbs",
    title: "Zomi Proverbs Collection",
    zomiTitle: "Zomi Paunak",
    description: "Traditional sayings with explanations and cultural context.",
    category: "Culture",
    format: "Planned collection",
    accent: "plum",
  },
  {
    id: "hymns",
    title: "Hymns & Songs Archive",
    zomiTitle: "La leh Phatna Late",
    description: "A future home for lyrics, notation, recordings, and history.",
    category: "Culture",
    format: "Planned collection",
    accent: "navy",
  },
  {
    id: "heritage",
    title: "Language & Culture Archive",
    zomiTitle: "Zomi Ngeina",
    description: "Preserving community writing, oral history, and heritage documents.",
    category: "Culture",
    format: "Planned collection",
    accent: "gold",
  },
];

const CATEGORIES = ["All", "Scripture", "Language", "Culture"] as const;

export default function LibraryClient() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<(typeof CATEGORIES)[number]>("All");

  const results = useMemo(() => {
    const term = query.trim().toLowerCase();
    return LIBRARY_ITEMS.filter((item) => {
      const matchesCategory = category === "All" || item.category === category;
      const matchesTerm = !term || `${item.title} ${item.zomiTitle} ${item.description}`.toLowerCase().includes(term);
      return matchesCategory && matchesTerm;
    });
  }, [category, query]);

  return (
    <div className="library-page">
      <section className="library-hero">
        <div className="library-hero-copy">
          <span className="library-kicker"><IconLibrary size={15} /> Siamsil Library</span>
          <h1 className="font-playfair">Zomi Library</h1>
          <p>Read, learn, and help preserve the literature and living memory of the Zomi people.</p>
        </div>
        <div className="library-hero-mark" aria-hidden="true"><IconLibrary size={46} filled /></div>
        <label className="library-search">
          <IconSearch size={17} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} type="search" placeholder="Search books, collections, or topics…" />
          {query && <button type="button" onClick={() => setQuery("")} aria-label="Clear library search">×</button>}
        </label>
      </section>

      <section className="library-content">
        <div className="library-summary">
          <div>
            <span className="library-summary-number">3</span>
            <span className="library-summary-label">Available collections</span>
          </div>
          <div>
            <span className="library-summary-number">3</span>
            <span className="library-summary-label">Planned collections</span>
          </div>
          <div>
            <span className="library-summary-number">66</span>
            <span className="library-summary-label">Bible books</span>
          </div>
        </div>

        <div className="library-section-head">
          <div>
            <span className="gold-label">Browse the collection</span>
            <h2 className="font-playfair">Library shelves</h2>
          </div>
          <span className="library-result-count">{results.length} collections</span>
        </div>

        <div className="library-filters" role="group" aria-label="Filter library by category">
          {CATEGORIES.map((item) => (
            <button key={item} type="button" className={category === item ? "active" : ""} onClick={() => setCategory(item)}>
              {item}
            </button>
          ))}
        </div>

        {results.length ? (
          <div className="library-grid">
            {results.map((item) => {
              const card = (
                <>
                  <div className={`library-cover ${item.accent}`}>
                    <span className="library-cover-icon">
                      {item.category === "Scripture" ? <IconCross size={27} /> : <IconBook size={27} />}
                    </span>
                    <span className="library-cover-category">{item.category}</span>
                    <span className="font-playfair library-cover-title">{item.zomiTitle}</span>
                  </div>
                  <div className="library-card-copy">
                    <div className="library-card-meta">
                      <span>{item.category}</span>
                      <span className={item.href ? "available" : "soon"}>{item.format}</span>
                    </div>
                    <h3 className="font-playfair">{item.title}</h3>
                    <p>{item.description}</p>
                    <span className="library-card-action">
                      {item.href ? "Open collection" : "Planned — not yet available"}
                      {item.href && <IconArrow size={14} />}
                    </span>
                  </div>
                </>
              );

              return item.href ? (
                <Link key={item.id} href={item.href} className="library-card">{card}</Link>
              ) : (
                <article key={item.id} className="library-card library-card-disabled">{card}</article>
              );
            })}
          </div>
        ) : (
          <div className="library-empty">
            <IconSearch size={28} />
            <h3 className="font-playfair">No collections found</h3>
            <p>Try another search or browse a different shelf.</p>
            <button type="button" onClick={() => { setQuery(""); setCategory("All"); }}>Clear filters</button>
          </div>
        )}
      </section>
      <div className="screen-pad" />
    </div>
  );
}
