"use client";

import Link from "next/link";
import { useRecentSearches } from "@/lib/localData";
import { IconArrow } from "./Icons";

/** Words this device looked up in the dictionary, newest first. */
export default function RecentSearches() {
  const recent = useRecentSearches("dictionary", 5);

  return (
    <section className="hx-card" aria-labelledby="hx-recent-title">
      <div className="hx-card-head">
        <h2 className="font-playfair hx-card-title" id="hx-recent-title">Recent Words</h2>
        <Link href="/zomidictionary" className="hx-link">Dictionary <IconArrow size={12} /></Link>
      </div>
      {recent.length > 0 ? (
        <ul className="hx-list">
          {recent.map((query) => (
            <li key={query}>
              <Link href={`/zomidictionary?q=${encodeURIComponent(query)}`} className="hx-list-row">
                <span className="hx-list-word">{query}</span>
                <IconArrow size={12} />
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="hx-empty">Words you look up in the dictionary appear here.</p>
      )}
    </section>
  );
}
